#!/usr/bin/env python3
"""rss-skill: 订阅源管理（wewe-rss）。

用法:
    python3 feeds.py --list                      # 列出 wewe-rss 全部订阅源 + 本地已入库文章数
    python3 feeds.py --update MP_WXS_123         # 触发指定源立即更新（服务端异步，约 30s）
    python3 feeds.py --update all                # 逐个触发所有源更新（慢，慎用）
输出: JSON
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rss_lib  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="列出订阅源")
    ap.add_argument("--update", metavar="FEED_ID", help="触发更新：feed_id 或 all")
    args = ap.parse_args()

    cfg = rss_lib.load_config(require_base=True)
    base = cfg["base_url"]

    try:
        feeds = rss_lib.wewe_list_feeds(base)
    except Exception as e:  # noqa: BLE001
        rss_lib.fail(f"无法连接 wewe-rss 服务 {base}：{e}")

    if args.update:
        targets = [f["id"] for f in feeds] if args.update == "all" else [args.update]
        results = []
        for fid in targets:
            try:
                rss_lib.wewe_trigger_update(base, fid)
                results.append({"feed_id": fid, "ok": True})
            except Exception as e:  # noqa: BLE001
                results.append({"feed_id": fid, "ok": False, "error": str(e)})
        rss_lib.out({"ok": True, "updated": results,
                     "note": "更新在服务端异步执行（每源约 30s+），稍后运行 sync.py 入库新文章。"})
        return

    # 默认 --list
    conn, _ = rss_lib.open_db(cfg)
    counts = dict(conn.execute(
        "SELECT source, COUNT(*) FROM articles GROUP BY source").fetchall())
    rows = []
    for f in feeds:
        rows.append({
            "feed_id": f["id"],
            "name": f.get("name"),
            "intro": (f.get("intro") or "")[:80],
            "local_articles": counts.get(f"wewe:{f['id']}", 0),
            "sync_time": f.get("syncTime"),
        })
    custom = [{"name": f.get("name"), "url": f.get("url"),
               "local_articles": counts.get(f"custom:{f.get('name')}", 0)}
              for f in cfg["feeds"]]
    rss_lib.out({"ok": True, "base_url": base, "total": len(rows),
                 "wewe_feeds": rows, "custom_feeds": custom})


if __name__ == "__main__":
    main()
