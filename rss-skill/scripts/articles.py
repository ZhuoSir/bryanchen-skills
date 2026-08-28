#!/usr/bin/env python3
"""rss-skill: 本地文章列表 / 阅读全文 / 统计。

用法:
    python3 articles.py --recent                 # 最近入库的文章（默认 20 条）
    python3 articles.py --recent --feed 量子位 --limit 10
    python3 articles.py --recent --days 7        # 只看最近 7 天发布的
    python3 articles.py --read 123               # 阅读全文（id 来自 search.py / --recent）
    python3 articles.py --read 123 --html        # 输出原始 HTML（默认输出纯文本）
    python3 articles.py --stats                  # 库统计：总条数、各源分布、时间范围
输出: JSON
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rss_lib  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recent", action="store_true", help="列出最近文章")
    ap.add_argument("--read", type=int, metavar="ID", help="按 id 阅读全文")
    ap.add_argument("--html", action="store_true", help="--read 时输出 HTML 原文")
    ap.add_argument("--stats", action="store_true", help="库统计")
    ap.add_argument("--feed", help="按订阅源名过滤")
    ap.add_argument("--days", type=int, help="只看最近 N 天发布")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    cfg = rss_lib.load_config()
    conn, _ = rss_lib.open_db(cfg)

    if args.read is not None:
        r = conn.execute("SELECT * FROM articles WHERE id=?",
                         (args.read,)).fetchone()
        if not r:
            rss_lib.fail(f"没有找到 id={args.read} 的文章，"
                         "先用 search.py 或 --recent 查找")
        rss_lib.out({
            "ok": True, "id": r["id"], "title": r["title"],
            "feed_name": r["feed_name"], "author": r["author"],
            "published": rss_lib.fmt_local(r["published"]), "url": r["url"],
            "content": r["content_html"] if args.html else r["content_text"],
            "content_length": len(r["content_text"] or ""),
        })
        return

    if args.stats:
        total = conn.execute("SELECT COUNT(*) c FROM articles").fetchone()["c"]
        rows = conn.execute(
            "SELECT feed_name, COUNT(*) c, MAX(published) latest "
            "FROM articles GROUP BY feed_name ORDER BY c DESC").fetchall()
        rng = conn.execute(
            "SELECT MIN(published) lo, MAX(published) hi FROM articles").fetchone()
        rss_lib.out({
            "ok": True, "total": total,
            "earliest": rss_lib.fmt_local(rng["lo"]),
            "latest": rss_lib.fmt_local(rng["hi"]),
            "by_feed": [{"feed_name": r["feed_name"], "count": r["c"],
                         "latest": rss_lib.fmt_local(r["latest"])}
                        for r in rows],
            "db_path": cfg["db_path"],
        })
        return

    # 默认 --recent
    where, params = [], []
    if args.feed:
        where.append("feed_name LIKE ?")
        params.append(f"%{args.feed}%")
    if args.days:
        cutoff = rss_lib.datetime.now(rss_lib.timezone.utc) \
            - rss_lib.timedelta(days=args.days)
        where.append("published >= ?")
        params.append(cutoff.isoformat())
    cond = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT id, title, feed_name, author, published, url, "
        f"length(content_text) len FROM articles {cond} "
        f"ORDER BY published DESC LIMIT ?", (*params, args.limit)).fetchall()
    rss_lib.out({
        "ok": True, "count": len(rows),
        "articles": [{
            "id": r["id"], "title": r["title"], "feed_name": r["feed_name"],
            "author": r["author"], "published": rss_lib.fmt_local(r["published"]),
            "url": r["url"], "has_fulltext": (r["len"] or 0) > 50,
        } for r in rows],
        "note": "用 articles.py --read <id> 阅读全文",
    })


if __name__ == "__main__":
    main()
