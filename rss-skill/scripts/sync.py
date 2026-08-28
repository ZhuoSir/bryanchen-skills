#!/usr/bin/env python3
"""rss-skill: 同步文章到本地全文索引库。

用法:
    python3 sync.py                          # 同步 wewe-rss 全部订阅源最新文章（全文模式，1 页）
    python3 sync.py --feed MP_WXS_123        # 只同步指定源
    python3 sync.py --deep --max-pages 5     # 翻页回溯历史文章（每源最多 5 页）
    python3 sync.py --no-fulltext            # 快速模式：只同步标题/摘要，不取全文（快很多）
    python3 sync.py --custom                 # 只同步配置文件里的自定义 RSS 源
    python3 sync.py --limit 50               # 每页条数（默认 30；fulltext 模式大值会很慢）
输出: JSON（每源新增/更新条数）
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rss_lib  # noqa: E402


def sync_wewe(cfg, conn, has_fts, feed_id, limit, max_pages, fulltext):
    base = cfg["base_url"]
    try:
        feed_names = {f["id"]: f.get("name") for f in rss_lib.wewe_list_feeds(base)}
    except Exception as e:  # noqa: BLE001
        rss_lib.fail(f"无法连接 wewe-rss 服务 {base}：{e}")
    targets = [feed_id] if feed_id else list(feed_names.keys())
    results = []
    for fid in targets:
        source = f"wewe:{fid}"
        added = updated = 0
        error = None
        try:
            for page in range(1, max_pages + 1):
                _, items = rss_lib.wewe_fetch_page(base, fid, page=page,
                                                   limit=limit, fulltext=fulltext)
                if not items:
                    break
                _, arts = rss_lib.parse_json_feed(
                    {"items": items}, source_name=fid,
                    feed_name=feed_names.get(fid) or fid)
                a, u = rss_lib.upsert_articles(conn, arts, source, has_fts)
                added, updated = added + a, updated + u
                if len(items) < limit:  # 最后一页
                    break
        except Exception as e:  # noqa: BLE001
            error = str(e)
        results.append({"feed_id": fid, "name": feed_names.get(fid),
                        "ok": error is None, "added": added, "updated": updated,
                        **({"error": error} if error else {})})
    return results


def sync_custom(cfg, conn, has_fts, limit):
    results = []
    for f in cfg["feeds"]:
        name, url = f.get("name") or f.get("url"), f.get("url")
        source = f"custom:{name}"
        try:
            data = rss_lib.fetch(url, timeout=30)
            feed_title, arts = rss_lib.parse_feed(data, name)
            for a in arts:
                a["feed_name"] = feed_title or name
            a_, u_ = rss_lib.upsert_articles(conn, arts[:limit], source, has_fts)
            results.append({"name": name, "ok": True, "added": a_, "updated": u_})
        except Exception as e:  # noqa: BLE001
            results.append({"name": name, "ok": False, "error": str(e)})
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feed", metavar="FEED_ID", help="只同步指定 wewe-rss 源")
    ap.add_argument("--limit", type=int, default=30, help="每页条数（默认 30）")
    ap.add_argument("--deep", action="store_true", help="翻页回溯历史")
    ap.add_argument("--max-pages", type=int, default=1, help="最大页数（--deep 时生效）")
    ap.add_argument("--no-fulltext", action="store_true",
                    help="不取全文（只同步标题/链接，速度快）")
    ap.add_argument("--custom", action="store_true", help="只同步自定义源")
    args = ap.parse_args()

    cfg = rss_lib.load_config()
    conn, has_fts = rss_lib.open_db(cfg)
    fulltext = not args.no_fulltext
    max_pages = max(1, args.max_pages) if args.deep else 1

    out = {"ok": True, "fulltext": fulltext}
    if not args.custom:
        c = rss_lib.load_config(require_base=True)
        try:
            out["wewe"] = sync_wewe(c, conn, has_fts, args.feed,
                                    args.limit, max_pages, fulltext)
        except Exception as e:  # noqa: BLE001
            rss_lib.fail(f"无法连接 wewe-rss 服务：{e}")
    if args.custom or not cfg["base_url"]:
        if cfg["feeds"]:
            out["custom"] = sync_custom(cfg, conn, has_fts, args.limit)
        elif args.custom:
            out["custom"] = []
            out["note"] = "配置文件中没有自定义 feeds"
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    out["total_articles_in_db"] = total
    rss_lib.out(out)


if __name__ == "__main__":
    main()
