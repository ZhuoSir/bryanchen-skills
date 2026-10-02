#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docker_cleanup.py — 按盘点结果删除 Docker 镜像 / 构建缓存

默认是 dry-run：只打印将要执行的命令，不删任何东西。
必须由用户明确确认后，才加 --apply 真删。

安全设计：
  * 绝不使用 docker image prune -a / docker system prune / docker volume prune
  * 绝不使用 docker image rm -f（让 Docker 自己当安全网：被容器引用的镜像会删失败）
  * 删除前二次核对容器引用（防止 dry-run 到 apply 之间有人起了容器）
  * 删除后复验：保护区镜像仍在、运行中容器数量未减少

退出码：0 成功或 dry-run；1 有镜像删除失败；2 Docker 不可用。
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docker_inventory as inv  # noqa: E402


def _matches_only(entry, only_patterns):
    if not only_patterns:
        return True
    for pat in only_patterns:
        for tag in (entry["refs"] or [entry["id"]]):
            if inv.matcher(pat, tag, entry["repo"], entry["id"]):
                return True
    return False


def select_targets(report, include_orphans=True, include_dangling=True,
                   allow_stopped=False, only_patterns=None, min_size=0):
    targets = []
    for e in report["candidates"]:
        if e["category"] == "dangling" and include_dangling:
            targets.append(e)
        elif e["category"] == "orphan" and include_orphans:
            targets.append(e)
    if allow_stopped:
        for e in report["protected"]:
            if e["category"] != "stopped":
                continue
            if e["size_bytes"] < min_size or not _matches_only(e, only_patterns or []):
                continue
            targets.append(e)
    return targets


def rm_command(entry):
    if entry["refs"]:
        return ["image", "rm"] + entry["refs"]
    return ["image", "rm", entry["id"]]


def explain_error(text):
    t = (text or "").lower()
    if "conflict" in t or "being used by" in t or "container" in t and "cannot be forced" in t:
        return "被容器占用，已跳过（Docker 安全网生效——先处理容器再删）"
    if "dependent child images" in t:
        return "有子镜像依赖这些层，已跳过（共享层，需先删依赖它的镜像）"
    if "no such image" in t:
        return "镜像已不存在"
    if "multiple repositories" in t:
        return "多 tag 引用，需逐个 tag 删除（脚本一般已按 tag 处理）"
    return (text or "").strip() or "未知错误"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="按盘点结果清理 Docker 镜像（默认 dry-run）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python3 scripts/docker_cleanup.py                      # dry-run，看方案\n"
               "  python3 scripts/docker_cleanup.py --scan-dir ~/work/myproj/docker\n"
               "  python3 scripts/docker_cleanup.py --apply              # 用户确认后才执行\n"
               "  python3 scripts/docker_cleanup.py --include-orphans --build-cache --apply\n")
    ap.add_argument("--apply", action="store_true", help="真正执行删除（缺省只打印方案）")
    ap.add_argument("--include-orphans", action="store_true",
                    help="除悬空镜像外，也删『有 tag 但无任何引用』的镜像")
    ap.add_argument("--no-dangling", action="store_true", help="不删悬空镜像")
    ap.add_argument("--allow-stopped-refs", action="store_true",
                    help="危险：连『只被已停止容器引用』的镜像一起删（compose 项目将无法离线重启）")
    ap.add_argument("--build-cache", action="store_true", help="同时清理构建缓存 docker builder prune -f")
    ap.add_argument("--build-cache-all", action="store_true",
                    help="清理全部构建缓存（-a，含仍可能被复用的缓存）")
    ap.add_argument("-p", "--protect", action="append", default=[], metavar="GLOB",
                    help="保护名单 glob，可重复")
    ap.add_argument("--protect-file", default=inv.DEFAULT_PROTECT_FILE,
                    help="保护名单文件（默认 %s）" % inv.DEFAULT_PROTECT_FILE)
    ap.add_argument("-s", "--scan-dir", action="append", default=[], metavar="DIR",
                    help="扫描 compose / Dockerfile，引用到的镜像一律保留")
    ap.add_argument("--only", action="append", default=[], metavar="GLOB",
                    help="只处理匹配的镜像，可重复（自检/精准清理用）")
    ap.add_argument("--min-size", type=float, default=0, metavar="MB", help="只处理 ≥ 该体积(MB) 的镜像")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出方案/结果")
    args = ap.parse_args(argv)

    patterns = list(args.protect) + inv.load_protect_file(args.protect_file)
    try:
        report = inv.build_report(
            protect_patterns=patterns, scan_dirs=args.scan_dir,
            only_patterns=args.only, min_size=int(args.min_size * 1000 ** 2))
    except inv.DockerError as exc:
        print("[错误] %s" % exc, file=sys.stderr)
        return 2

    targets = select_targets(
        report,
        include_orphans=args.include_orphans,
        include_dangling=not args.no_dangling,
        allow_stopped=args.allow_stopped_refs,
        only_patterns=args.only,
        min_size=int(args.min_size * 1000 ** 2),
    )
    bytes_total = sum(e["size_bytes"] for e in targets)
    before_df = report["system_df"]

    if args.json and not args.apply:
        print(inv.json.dumps({
            "mode": "dry-run",
            "targets": targets,
            "target_count": len(targets),
            "target_bytes": bytes_total,
            "protected_count": len(report["protected"]),
            "risky": report["risky"],
            "system_df": before_df,
        }, ensure_ascii=False, indent=2, default=str))
        return 0

    # ------------------------------------------------------------ 方案
    print("=" * 78)
    print(" Docker 镜像清理方案（%s）" % ("APPLY 真删" if args.apply else "dry-run 不删任何东西"))
    print("=" * 78)
    print(" 保护区镜像 %d 个（运行/停止容器引用、compose/Dockerfile 引用、白名单）"
          % len(report["protected"]))
    print(" 待删 %d 个，标称合计 %s" % (len(targets), inv.fmt_size(bytes_total)))
    if bytes_total >= 10 * 1000 ** 3 or len(targets) >= 10:
        print(" ⚠ 本次删除量较大，务必先把本方案给用户确认")
    print("")
    for e in targets:
        print("   %-58s %-10s %s" % (
            (e["refs"][0] if e["refs"] else "<none> " + e["short_id"])[:58],
            inv.fmt_size(e["size_bytes"]), e["created"]))
    if not targets:
        print("   （无）")
    if report["risky"]:
        print("")
        print(" [先问用户] 以下候选看着还需要，脚本不会自动删——除非用户明确说可以：")
        for e in report["risky"]:
            print("   ⚠ %-52s %s" % (
                (e["refs"][0] if e["refs"] else "<none> " + e["short_id"])[:52], e["reason"]))
    if args.build_cache or args.build_cache_all:
        cache = before_df.get("Build Cache")
        print("")
        print(" 另清理构建缓存：%s（%s）" % (
            cache["size"] if cache else "?", cache["reclaimable"] if cache else "?"))
    print("")
    print(" 将执行的命令：")
    for e in targets:
        print("   docker " + " ".join(rm_command(e)))
    if args.build_cache_all:
        print("   docker builder prune -a -f")
    elif args.build_cache:
        print("   docker builder prune -f")
    print("")

    if not args.apply:
        print("dry-run 结束。把上面的清单给用户看，确认后再加 --apply 重跑。")
        return 0

    # ------------------------------------------------------------ 执行
    live = inv.list_containers()
    live_refs = {}
    for c in live:
        live_refs.setdefault(c["image"], []).append(c["name"])
    running_before = sum(1 for c in live if c["state"] in inv.STATE_RUNNING)

    deleted, failed, skipped = [], [], []
    for e in targets:
        hit = [n for ref in (e["refs"] or [e["id"]]) for n in live_refs.get(ref, [])]
        if hit and not args.allow_stopped_refs:
            skipped.append((e, "刚刚又被容器引用：%s" % ", ".join(hit)))
            continue
        rc, out, err = inv.run(rm_command(e), timeout=180)
        if rc == 0:
            deleted.append(e)
            print("   ✔ 已删 %s" % (e["refs"][0] if e["refs"] else e["short_id"]))
        else:
            reason = explain_error(err or out)
            failed.append((e, reason))
            print("   ✘ 跳过 %s —— %s" % (
                (e["refs"][0] if e["refs"] else e["short_id"]), reason), file=sys.stderr)

    if args.build_cache or args.build_cache_all:
        cmd = ["builder", "prune", "-f"] + (["-a"] if args.build_cache_all else [])
        rc, out, err = inv.run(cmd, timeout=600)
        print("   %s 构建缓存清理%s" % ("✔" if rc == 0 else "✘",
                                        "" if rc == 0 else "：" + (err or out).strip()))

    # ------------------------------------------------------------ 复验
    try:
        after_report = inv.build_report(protect_patterns=patterns, scan_dirs=args.scan_dir)
        after = after_report
        after_running = after_report["summary"]["running_count"]
        missing = [e for e in report["protected"]
                   if e["id"] not in after_report["images"]]
        after_df = after_report["system_df"]
    except inv.DockerError as exc:
        print("[警告] 复验失败：%s" % exc, file=sys.stderr)
        after, missing, after_df, after_running = None, [], {}, running_before

    print("")
    print("=" * 78)
    print(" 结果：删除 %d 个，跳过 %d 个" % (len(deleted), len(failed) + len(skipped)))
    if before_df.get("Images") and after_df.get("Images"):
        print(" 镜像占用：%s → %s（回收 %s）" % (
            before_df["Images"]["size"], after_df["Images"]["size"],
            inv.fmt_size(max(0, before_df["Images"]["size_bytes"] - after_df["Images"]["size_bytes"]))))
    if before_df.get("Build Cache") and after_df.get("Build Cache"):
        print(" 构建缓存：%s → %s" % (before_df["Build Cache"]["size"], after_df["Build Cache"]["size"]))
    if after_df.get("Images"):
        print(" docker system df 口径剩余可回收：%s" % after_df["Images"]["reclaimable"])
    if missing:
        print(" ⚠ 保护区有 %d 个镜像消失（不该发生，请检查）：%s" % (
            len(missing), ", ".join(m["refs"][0] if m["refs"] else m["short_id"] for m in missing)))
    else:
        print(" 复验：保护区镜像全部健在 ✔")
    if after_running < running_before:
        print(" ⚠ 运行中容器从 %d 降到 %d，请检查其他项目" % (running_before, after_running))
    else:
        print(" 复验：运行中容器 %d 个未受影响 ✔" % after_running)
    if report["disk"] and after is not None:
        d = report["disk"]
        print(" 提示：本机 Docker.raw 实际占用 %s，删除镜像通常不会让 macOS 立刻多出空间（见 references/macos-reclaim.md）"
              % inv.fmt_size(d["allocated_bytes"]))
    print("=" * 78)

    if args.json:
        print(inv.json.dumps({
            "mode": "apply",
            "deleted": deleted, "failed": [{"image": e["refs"] or e["id"], "reason": r} for e, r in failed],
            "skipped": [{"image": e["refs"] or e["id"], "reason": r} for e, r in skipped],
            "before": before_df, "after": after_df,
        }, ensure_ascii=False, indent=2, default=str))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
