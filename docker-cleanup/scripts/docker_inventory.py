#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docker_inventory.py — Docker 镜像只读盘点（本脚本绝不删除任何东西）

把"哪些镜像绝对不能动、哪些可以删"算清楚，输出给人看的报告或 JSON。
docker_cleanup.py 复用本模块的分类逻辑。

用法示例：
    python3 scripts/docker_inventory.py
    python3 scripts/docker_inventory.py --protect 'phoenix-*' --scan-dir ~/work/myproj/docker
    python3 scripts/docker_inventory.py --json --disk
"""

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

# ---------------------------------------------------------------- Docker CLI

DOCKER_CANDIDATES = [
    os.environ.get("DOCKER_BIN", ""),
    "docker",
    "/usr/local/bin/docker",
    "/opt/homebrew/bin/docker",
    "/Applications/Docker.app/Contents/Resources/bin/docker",
]

# 默认保护名单文件（存在即自动加载，一行一个 glob，# 开头为注释）
DEFAULT_PROTECT_FILE = os.path.expanduser("~/.config/docker-cleanup/protect.txt")


class DockerError(Exception):
    pass


_DOCKER = None


def resolve_docker():
    """定位 docker 可执行文件（PATH 可能被 Agent 沙箱裁剪）。"""
    global _DOCKER
    if _DOCKER:
        return _DOCKER
    for cand in DOCKER_CANDIDATES:
        if not cand:
            continue
        path = None
        if os.path.sep in cand:
            path = cand if os.path.exists(cand) else None
        else:
            path = shutil.which(cand)
        if path:
            _DOCKER = path
            return path
    raise DockerError(
        "未找到 docker 命令。请确认 Docker Desktop / docker CLI 已安装；"
        "也可用环境变量 DOCKER_BIN 指定绝对路径。"
    )


def run(args, timeout=120):
    """执行 docker 命令，返回 (rc, stdout, stderr)。"""
    cmd = [resolve_docker()] + args
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, universal_newlines=True,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        raise DockerError(
            "docker %s 超时（%ss）——Docker 守护进程可能无响应。\n"
            "不要反复重试、更不要直接强杀 Docker：先看 references/safety-rules.md 的"
            "『守护进程无响应』一节。" % (" ".join(args), timeout)
        )
    except FileNotFoundError:
        raise DockerError("docker 可执行文件不存在：%s" % cmd[0])


def preflight(timeout=30):
    """确认守护进程可用，返回 server 版本。"""
    rc, out, err = run(["info", "--format", "{{.ServerVersion}}"], timeout=timeout)
    if rc != 0:
        raise DockerError(
            "docker info 失败（守护进程不可用）：%s\n"
            "先确认 Docker Desktop 是否已启动（GUI 图标稳定、不再显示 starting）。" %
            (err.strip() or out.strip() or "unknown")
        )
    return out.strip()


# ---------------------------------------------------------------- 解析工具

SIZE_RE = re.compile(r"^\s*([0-9.]+)\s*([kKmMgGtT]?[bB])\s*$")
_UNITS = {"b": 1, "kb": 1000, "mb": 1000 ** 2, "gb": 1000 ** 3, "tb": 1000 ** 4}


def parse_size(text):
    """'1.57GB' -> 字节数（Docker 用十进制单位）。解析失败返回 0。"""
    m = SIZE_RE.match(text or "")
    if not m:
        return 0
    return int(float(m.group(1)) * _UNITS[m.group(2).lower()])


def fmt_size(num):
    num = float(num or 0)
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if num < 1000 or unit == "TB":
            if unit == "B":
                return "%d B" % num
            return "%.2f %s" % (num, unit)
        num /= 1000.0


HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")
VAR_RE = re.compile(r"\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*")


def is_bare_id(ref):
    return bool(HEX_RE.match(ref.replace("sha256:", "")))


def strip_tag(ref):
    """redis:7 -> redis；registry:5000/a/b:tag -> registry:5000/a/b"""
    if ":" in ref.rsplit("/", 1)[-1]:
        return ref.rsplit(":", 1)[0]
    return ref


def matcher(pattern, ref, repo, image_id):
    """glob 匹配 tag / 去 tag 仓库名 / 短 ID。"""
    pat = pattern.strip()
    if not pat:
        return False
    short_id = image_id.replace("sha256:", "")[:12]
    return (fnmatch.fnmatch(ref, pat) or fnmatch.fnmatch(repo, pat)
            or fnmatch.fnmatch(short_id, pat) or fnmatch.fnmatch(image_id, pat))


def load_protect_file(path):
    patterns = []
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    return patterns


# ---------------------------------------------------------------- 采集

def list_images():
    rc, out, err = run([
        "image", "ls", "--no-trunc", "--format",
        "{{.ID}}\t{{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}",
    ])
    if rc != 0:
        raise DockerError("docker image ls 失败：%s" % (err.strip() or out.strip()))
    images = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        image_id, repo, tag, size, created = parts[:5]
        item = images.setdefault(image_id, {
            "id": image_id, "repo": repo, "size_bytes": 0,
            "tags": [], "created": created,
        })
        if repo == "<none>" and tag == "<none>":
            item["dangling"] = True
        else:
            ref = "%s:%s" % (repo, tag)
            item["tags"].append(ref)
            item["repo"] = repo
        # 同一 image id 的多行（多 tag）只累加一次尺寸
        item["size_bytes"] = max(item["size_bytes"], parse_size(size))
    for item in images.values():
        item.setdefault("dangling", False)
    return images


def list_containers():
    rc, out, err = run([
        "ps", "-a", "--no-trunc", "--format",
        "{{.ID}}\t{{.Image}}\t{{.Names}}\t{{.State}}\t{{.Status}}",
    ])
    if rc != 0:
        raise DockerError("docker ps -a 失败：%s" % (err.strip() or out.strip()))
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        rows.append({
            "id": parts[0], "image": parts[1], "name": parts[2],
            "state": parts[3], "status": parts[4],
        })
    return rows


def system_df():
    rc, out, _ = run(["system", "df"])
    rows = {}
    if rc != 0:
        return rows
    for line in out.splitlines()[1:]:
        m = re.match(r"^(Images|Containers|Local Volumes|Build Cache)\s+(.*)$", line.strip())
        if not m:
            continue
        tokens = m.group(2).split()
        if len(tokens) < 3:
            continue
        rows[m.group(1)] = {
            "total": tokens[0],
            "active": tokens[1],
            "size": tokens[2],
            "size_bytes": parse_size(tokens[2]),
            "reclaimable": tokens[3] if len(tokens) > 3 else "0B",
            "reclaimable_bytes": parse_size(tokens[3]) if len(tokens) > 3 else 0,
            "raw": line.strip(),
        }
    return rows


def docker_raw_info():
    """macOS：Docker.raw 稀疏文件的实际占用 vs 逻辑大小。"""
    candidates = [
        os.path.expanduser("~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw"),
        os.path.expanduser("~/Library/Containers/com.docker.docker/Data/vms/0/Docker.raw"),
        os.path.expanduser("~/Library/Group Containers/group.com.docker/Data/vms/0/data/Docker.raw"),
    ]
    for path in candidates:
        if os.path.exists(path):
            st = os.stat(path)
            allocated = getattr(st, "st_blocks", 0) * 512
            return {
                "path": path,
                "apparent_bytes": st.st_size,
                "allocated_bytes": allocated,
            }
    return None


# ---------------------------------------------------------------- 配置扫描

_COMPOSE_NAMES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".idea", ".vscode"}
_IMAGE_LINE = re.compile(r"^\s*image:\s*[\"']?([^\"'\s#]+)")
_FROM_LINE = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?([^\s]+)(?:\s+[aA][sS]\s+(\S+))?", re.I)
_DEFAULT_RE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*(?::-|-)([^}]*)\}")


def is_compose_file(name):
    return name in _COMPOSE_NAMES or (
        name.endswith((".yml", ".yaml"))
        and (name.startswith("compose") or name.startswith("docker-compose")))


def expand_ref(ref):
    """把 compose 变量展开成可匹配的 glob。

    ${VAR:-default} -> default；${VAR} -> *；整串只剩通配符则返回 None（无法解析）。
    """
    out = _DEFAULT_RE.sub(lambda m: m.group(1), ref)
    out = VAR_RE.sub("*", out)
    if not out.strip("*:/"):
        return None
    return out


def scan_refs(dirs):
    """扫描 compose / Dockerfile，返回 ({ref模型: [来源文件]}, [无法解析的变量引用])."""
    found = {}
    unresolved = []
    for root_dir in dirs:
        root_dir = os.path.expanduser(root_dir)
        if not os.path.isdir(root_dir):
            continue
        for base, subdirs, files in os.walk(root_dir):
            subdirs[:] = [d for d in subdirs if d not in _SKIP_DIRS]
            for name in files:
                path = os.path.join(base, name)
                if is_compose_file(name):
                    _scan_file(path, _IMAGE_LINE, found, unresolved)
                elif name == "Dockerfile" or name.startswith("Dockerfile.") or name.endswith(".Dockerfile"):
                    _scan_dockerfile(path, found, unresolved)
    return found, unresolved


def _scan_file(path, pattern, found, unresolved):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = pattern.match(line)
                if m:
                    _add_ref(found, unresolved, m.group(1), path)
    except OSError:
        pass


def _scan_dockerfile(path, found, unresolved):
    aliases = set()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = _FROM_LINE.match(line)
                if not m:
                    continue
                ref, alias = m.group(1), m.group(2)
                if alias:
                    aliases.add(alias.lower())
                if ref.lower() == "scratch" or ref.lower() in aliases:
                    continue
                _add_ref(found, unresolved, ref, path)
    except OSError:
        pass


def _add_ref(found, unresolved, ref, path):
    model = expand_ref(ref)
    if model is None:
        unresolved.append({"ref": ref, "file": path})
        return
    found.setdefault(model, [])
    if path not in found[model]:
        found[model].append(path)


# ---------------------------------------------------------------- 分类

STATE_RUNNING = {"running", "paused", "restarting", "removing"}


def build_report(protect_patterns=None, scan_dirs=None, only_patterns=None, min_size=0):
    """核心分类。返回 dict（inventory / docker_cleanup 共用）。"""
    protect_patterns = list(protect_patterns or [])
    only_patterns = list(only_patterns or [])
    server = preflight()
    images = list_images()
    containers = list_containers()
    df = system_df()
    refs, unresolved = scan_refs(scan_dirs or [])

    # 容器引用 → 镜像 ID
    inspect_cache = {}

    def resolve_id(ref):
        if is_bare_id(ref):
            key = ref.replace("sha256:", "").lower()
            for image_id in images:
                if image_id.replace("sha256:", "").startswith(key[:12]):
                    return image_id
            if ref in inspect_cache:
                return inspect_cache[ref]
            rc, out, _ = run(["image", "inspect", "--format", "{{.Id}}", ref], timeout=30)
            inspect_cache[ref] = out.strip() if rc == 0 else None
            return inspect_cache[ref]
        return None

    for c in containers:
        image_id = resolve_id(c["image"])
        if image_id is None:
            # 多数情况 .Image 就是 repo:tag，直接对 tag 匹配
            for iid, img in images.items():
                if c["image"] in img["tags"]:
                    image_id = iid
                    break
        c["image_id"] = image_id

    def refs_of(image_id, tags):
        running, stopped = [], []
        for c in containers:
            hit = c["image_id"] == image_id or c["image"] in tags
            if not hit:
                continue
            entry = {"name": c["name"], "state": c["state"], "image": c["image"]}
            (running if c["state"] in STATE_RUNNING else stopped).append(entry)
        return running, stopped

    def config_refs(tags, image_id, repo):
        hits = []
        for model, files in refs.items():
            if any(fnmatch.fnmatch(t, model) or fnmatch.fnmatch(strip_tag(t), model) for t in tags):
                hits.append({"ref": model, "files": files})
            elif fnmatch.fnmatch(image_id.replace("sha256:", "")[:12], model):
                hits.append({"ref": model, "files": files})
        return hits

    protect, candidates, risky = [], [], []
    for image_id, img in images.items():
        tags = sorted(img["tags"])
        ref = tags[0] if tags else "<none>:<none>"
        running, stopped = refs_of(image_id, tags)
        cfg = config_refs(tags, image_id, img["repo"])
        allow = sorted({p for p in protect_patterns
                        if matcher(p, ref, img["repo"], image_id)
                        or any(matcher(p, t, img["repo"], image_id) for t in tags)})
        only_ok = (not only_patterns) or any(
            matcher(p, t, img["repo"], image_id) for p in only_patterns for t in (tags or [image_id])
        )

        entry = {
            "id": image_id, "short_id": image_id.replace("sha256:", "")[:12],
            "refs": tags, "repo": img["repo"], "size_bytes": img["size_bytes"],
            "created": img["created"], "dangling": img["dangling"],
            "running_refs": running, "stopped_refs": stopped, "config_refs": cfg,
            "protect_patterns": allow,
        }
        if running:
            entry["category"] = "running"
            protect.append(entry)
        elif stopped:
            entry["category"] = "stopped"
            protect.append(entry)
        elif cfg or allow:
            entry["category"] = "reserved"
            protect.append(entry)
        else:
            entry["category"] = "dangling" if img["dangling"] else "orphan"
            if img["size_bytes"] >= min_size and only_ok:
                candidates.append(entry)
            elif img["size_bytes"] < min_size:
                entry["category"] = "skipped-small"
                protect.append(entry)
            else:
                entry["category"] = "skipped-filter"
                protect.append(entry)

    # 风险提示（只针对候选）：镜像站别名、同仓库旧版本
    active_repos = {e["repo"] for e in protect if e["repo"] != "<none>"}
    for entry in candidates:
        repo = entry["repo"]
        if "/" in repo and "." in repo.split("/")[0]:
            risky.append(dict(entry, reason="镜像站/私有仓库别名，可能被构建脚本 FROM 引用"))
        elif repo in active_repos:
            risky.append(dict(entry, reason="同仓库已有在用版本，可能是旧版本/回滚点"))
        elif entry["dangling"] and entry["size_bytes"] >= 1 * 1000 ** 3:
            risky.append(dict(entry, reason="大体积悬空层，可能是某项目构建残留（一般可删）"))

    candidates.sort(key=lambda e: -e["size_bytes"])
    protect.sort(key=lambda e: (e["category"], -e["size_bytes"]))
    content_bytes = sum(v["size_bytes"] for v in df.values())
    disk = docker_raw_info()
    if disk:
        disk["docker_content_bytes"] = content_bytes
        disk["gap_bytes"] = max(0, disk["allocated_bytes"] - content_bytes)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "server_version": server,
        "docker_bin": resolve_docker(),
        "images": images, "containers": containers, "system_df": df,
        "scanned_dirs": [os.path.expanduser(d) for d in (scan_dirs or [])],
        "scanned_refs": refs, "unresolved_refs": unresolved,
        "protect_patterns": protect_patterns, "only_patterns": only_patterns,
        "protected": protect, "candidates": candidates, "risky": risky,
        "disk": disk,
        "summary": {
            "image_count": len(images),
            "container_count": len(containers),
            "running_count": sum(1 for c in containers if c["state"] in STATE_RUNNING),
            "candidate_count": len(candidates),
            "candidate_bytes": sum(e["size_bytes"] for e in candidates),
            "dangling_count": sum(1 for e in candidates if e["category"] == "dangling"),
            "orphan_count": sum(1 for e in candidates if e["category"] == "orphan"),
        },
    }


# ---------------------------------------------------------------- 渲染

_CATEGORY_LABEL = {
    "running": "运行中容器引用",
    "stopped": "已停止容器引用（reserve：compose 项目可能随时重启）",
    "reserved": "配置/白名单保护（compose、Dockerfile、手工名单）",
    "dangling": "悬空镜像 <none>（无任何引用）",
    "orphan": "无引用镜像（有 tag 但没人用）",
    "skipped-filter": "被 --only 过滤，本次不处理",
    "skipped-small": "小于 --min-size，本次不处理",
}


def render_text(report):
    s = report["summary"]
    lines = []
    lines.append("=" * 78)
    lines.append(" Docker 镜像盘点 · %s" % report["generated_at"])
    lines.append(" server %s | 镜像 %d | 容器 %d（运行 %d）" % (
        report["server_version"], s["image_count"], s["container_count"], s["running_count"]))
    lines.append(" docker: %s" % report["docker_bin"])
    if report["scanned_dirs"]:
        lines.append(" 已扫描配置目录: %s" % ", ".join(report["scanned_dirs"]))
    if report["protect_patterns"]:
        lines.append(" 白名单: %s" % ", ".join(report["protect_patterns"]))
    if report["only_patterns"]:
        lines.append(" 只处理匹配: %s" % ", ".join(report["only_patterns"]))
    lines.append("=" * 78)

    if report["system_df"]:
        lines.append("")
        lines.append("[空间账目] docker system df（权威口径）")
        for key in ("Images", "Containers", "Local Volumes", "Build Cache"):
            row = report["system_df"].get(key)
            if row:
                lines.append("  %-14s %4s 个   占用 %-9s  可回收 %s" % (
                    key, row["total"], fmt_size(row["size_bytes"]), row["reclaimable"]))
        lines.append("  ※ 下方候选合计 %s 是标称上限（共享层会被重复计数），真实可回收以 RECLAIMABLE 为准"
                     % fmt_size(s["candidate_bytes"]))
        vols = report["system_df"].get("Local Volumes")
        if vols and vols["reclaimable_bytes"] > 0:
            lines.append("  ※ 卷可回收 %s，但卷里是数据库/对象存储等真实数据，本 skill 不删卷（见 references/safety-rules.md）"
                         % vols["reclaimable"])

    if report["disk"]:
        d = report["disk"]
        lines.append("")
        lines.append("[macOS 磁盘] Docker.raw 稀疏文件")
        lines.append("  路径        %s" % d["path"])
        lines.append("  实际占用    %s（stat 块数估算；du 可能因稀疏/克隆略有差异）" % fmt_size(d["allocated_bytes"]))
        lines.append("  逻辑大小    %s" % fmt_size(d["apparent_bytes"]))
        lines.append("  Docker 内容 %s" % fmt_size(d["docker_content_bytes"]))
        lines.append("  疑似未回收  %s —— 删镜像不会把它还给 macOS，见 references/macos-reclaim.md"
                     % fmt_size(d["gap_bytes"]))

    lines.append("")
    lines.append("[保护区] 共 %d 个镜像，不要删" % len(report["protected"]))
    by_cat = {}
    for e in report["protected"]:
        by_cat.setdefault(e["category"], []).append(e)
    for cat in ("running", "stopped", "reserved", "skipped-filter", "skipped-small"):
        group = by_cat.get(cat)
        if not group:
            continue
        label = _CATEGORY_LABEL.get(cat, cat)
        lines.append("  ● %s（%d）" % (label, len(group)))
        for e in group:
            who = ", ".join(c["name"] for c in (e["running_refs"] + e["stopped_refs"])) or \
                  ", ".join(r["ref"] for r in e["config_refs"]) or \
                  ("白名单 " + ",".join(e["protect_patterns"]) if e["protect_patterns"] else "")
            lines.append("      %-52s %-9s %s" % (
                (e["refs"][0] if e["refs"] else "<none> " + e["short_id"])[:52],
                fmt_size(e["size_bytes"]), ("← " + who) if who else ""))

    lines.append("")
    lines.append("[删除候选] 共 %d 个，标称合计 %s" % (s["candidate_count"], fmt_size(s["candidate_bytes"])))
    if not report["candidates"]:
        lines.append("  （无）")
    for cat in ("dangling", "orphan"):
        group = [e for e in report["candidates"] if e["category"] == cat]
        if not group:
            continue
        lines.append("  ○ %s（%d）" % (_CATEGORY_LABEL[cat], len(group)))
        for e in group:
            lines.append("      %-52s %-9s %s" % (
                (e["refs"][0] if e["refs"] else "<none> " + e["short_id"])[:52],
                fmt_size(e["size_bytes"]), e["created"]))

    if report.get("scanned_dirs"):
        lines.append("")
        lines.append("[配置扫描] 命中 %d 个镜像引用（来自 compose / Dockerfile）" % len(report.get("scanned_refs", {})))
        for ref, files in sorted(report.get("scanned_refs", {}).items()):
            lines.append("  · %-52s %s" % (ref[:52], ", ".join(f.split("/")[-1] for f in files)))
        for item in report.get("unresolved_refs", []):
            lines.append("  ⚠ 无法解析的变量引用 %s（%s）——请人工确认该镜像是哪个"
                         % (item["ref"], item["file"]))

    if report["risky"]:
        lines.append("")
        lines.append("[需人工确认] %d 个（脚本不会自动删，先问用户）" % len(report["risky"]))
        for e in report["risky"]:
            lines.append("  ⚠ %-46s %-9s %s" % (
                (e["refs"][0] if e["refs"] else "<none> " + e["short_id"])[:46],
                fmt_size(e["size_bytes"]), e["reason"]))

    lines.append("")
    lines.append("下一步：把 [删除候选] 给用户看，确认后执行")
    lines.append("  python3 scripts/docker_cleanup.py %s        # dry-run，只打印命令" % (
        "--scan-dir <项目目录> " if report["scanned_dirs"] else ""))
    lines.append("  python3 scripts/docker_cleanup.py --apply ...  # 用户确认后才加 --apply")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Docker 镜像只读盘点（不删除任何东西）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-p", "--protect", action="append", default=[],
                    metavar="GLOB", help="保护名单 glob，可重复，如 'phoenix-*'")
    ap.add_argument("--protect-file", default=DEFAULT_PROTECT_FILE,
                    help="保护名单文件（一行一个 glob，默认 %s）" % DEFAULT_PROTECT_FILE)
    ap.add_argument("-s", "--scan-dir", action="append", default=[],
                    metavar="DIR", help="扫描该目录下的 compose / Dockerfile，引用的镜像视为保留")
    ap.add_argument("--only", action="append", default=[], metavar="GLOB",
                    help="只把匹配的镜像算作候选，可重复")
    ap.add_argument("--min-size", type=float, default=0, metavar="MB",
                    help="只把 ≥ 该体积(MB) 的镜像算作候选")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--disk", action="store_true", help="附 Docker.raw 磁盘账目（macOS）")
    args = ap.parse_args(argv)

    patterns = list(args.protect) + load_protect_file(args.protect_file)
    try:
        report = build_report(
            protect_patterns=patterns, scan_dirs=args.scan_dir,
            only_patterns=args.only, min_size=int(args.min_size * 1000 ** 2))
    except DockerError as exc:
        print("[错误] %s" % exc, file=sys.stderr)
        return 2

    if args.json:
        if not args.disk:
            report.pop("disk", None)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
