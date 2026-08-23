#!/usr/bin/env python3
"""morning-report: 全网热榜聚合（零依赖，Python 标准库，免 API Key）。

数据源：60s API 镜像（与 news_api.py 同源），聚合微博/知乎/抖音/头条热榜。
单源失败不阻塞，全部失败才退出码 1。B 站端点（/v2/bili）上游长期 500，不收录。

用法:
    python3 hot_rank.py [--top 5] [--sources weibo,zhihu,douyin,toutiao]
输出:
    stdout JSON: {"date", "boards": {"weibo": {"ok", "name", "items": [{title, link, hot}]}...}}
"""
import argparse
import json
import sys
import time
import urllib.request
from datetime import date

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 60s API 镜像（与 news_api.py 保持同一降级链）
MIRRORS = ["https://60s.viki.moe", "https://60s-api.viki.moe"]

# 榜单定义：标签 -> (中文名, 端点)
BOARDS = {
    "weibo": ("微博热搜", "/v2/weibo"),
    "zhihu": ("知乎热榜", "/v2/zhihu"),
    "douyin": ("抖音热点", "/v2/douyin"),
    "toutiao": ("头条热榜", "/v2/toutiao"),
}


def fetch(url, tries=2, timeout=10):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < tries - 1:
                time.sleep(1.0)
    raise last


def fetch_board(key, top):
    """按镜像降级链抓单个榜单，返回 (board_dict, error_or_None)。"""
    name, endpoint = BOARDS[key]
    last_err = None
    for mirror in MIRRORS:
        try:
            d = json.loads(fetch(mirror + endpoint))
            items = d.get("data") or []
            if not isinstance(items, list) or not items:
                raise RuntimeError("空数据")
            out = []
            for it in items[:top]:
                title = (it.get("title") or "").strip()
                link = it.get("link") or it.get("url") or ""
                if not title:
                    continue
                entry = {"title": title, "link": link}
                hot = it.get("hot_value") or it.get("hot_value_desc")
                if hot:
                    entry["hot"] = hot
                out.append(entry)
            return {"ok": True, "name": name, "items": out}, None
        except Exception as e:  # noqa: BLE001
            last_err = f"{mirror}: {e}"
            continue
    return {"ok": False, "name": name, "items": []}, last_err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5, help="每榜取前 N 条（默认 5）")
    ap.add_argument("--sources", default="weibo,zhihu,douyin,toutiao",
                    help="逗号分隔的榜单标签")
    args = ap.parse_args()

    keys = [k.strip() for k in args.sources.split(",") if k.strip() in BOARDS]
    if not keys:
        json.dump({"error": f"无有效榜单，可选: {','.join(BOARDS)}"},
                  sys.stdout, ensure_ascii=False)
        sys.exit(1)

    boards, errors = {}, []
    for key in keys:
        board, err = fetch_board(key, args.top)
        boards[key] = board
        if err:
            errors.append(f"{key}: {err}")

    ok_count = sum(1 for b in boards.values() if b["ok"])
    out = {"date": date.today().isoformat(), "boards": boards}
    if errors:
        out["note"] = "部分榜单失败: " + "; ".join(errors)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()
    if ok_count == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
