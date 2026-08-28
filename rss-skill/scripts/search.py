#!/usr/bin/env python3
"""rss-skill: 本地文章全文搜索（中文友好：CJK bigram + FTS5）。

用法:
    python3 search.py 世界模型                     # 全文搜索（标题+正文+源名）
    python3 search.py "世界模型 具身智能"           # 多段 = AND（段内保持词序）
    python3 search.py 大模型 --feed 量子位          # 限定订阅源
    python3 search.py 机器人 --days 30             # 只搜最近 30 天
    python3 search.py 世界模型 --limit 10          # 返回条数（默认 20）
    python3 search.py 'title:世界模型'              # 只搜标题（FTS5 语法透传）
输出: JSON（含 id / 标题 / 源 / 发布时间 / 链接 / 命中片段；id 用于 articles.py --read）
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rss_lib  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="搜索关键词（空格分隔多段为 AND）")
    ap.add_argument("--feed", help="按订阅源名过滤")
    ap.add_argument("--days", type=int, help="只搜最近 N 天")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    cfg = rss_lib.load_config()
    conn, has_fts = rss_lib.open_db(cfg)

    where, params = [], []
    if args.feed:
        where.append("a.feed_name LIKE ?")
        params.append(f"%{args.feed}%")
    if args.days:
        cutoff = rss_lib.datetime.now(rss_lib.timezone.utc) \
            - rss_lib.timedelta(days=args.days)
        where.append("a.published >= ?")
        params.append(cutoff.isoformat())
    cond = (" AND " + " AND ".join(where)) if where else ""

    rows, engine = None, None
    if has_fts:
        q = rss_lib.fts_query(args.query)
        if q:
            try:
                rows = conn.execute(
                    f"""
                    SELECT a.id, a.title, a.feed_name, a.author, a.published,
                           a.url, a.content_text,
                           bm25(articles_fts, 10.0, 1.0, 2.0) AS rank
                    FROM articles_fts f JOIN articles a ON a.id = f.rowid
                    WHERE articles_fts MATCH ?{cond}
                    ORDER BY rank LIMIT ?""", [q, *params, args.limit]).fetchall()
                engine = "fts5"
            except Exception:  # noqa: BLE001 — 手写语法错误等，走 LIKE 兜底
                rows = None
    if rows is None:
        terms = [t for t in args.query.split() if t]
        like = " AND ".join(
            ["(a.title LIKE ? OR a.content_text LIKE ?)"] * len(terms))
        like_params = []
        for t in terms:
            like_params += [f"%{t}%", f"%{t}%"]
        rows = conn.execute(
            f"""
            SELECT a.id, a.title, a.feed_name, a.author, a.published, a.url,
                   a.content_text, 0 AS rank
            FROM articles a
            WHERE {like}{cond}
            ORDER BY a.published DESC LIMIT ?""",
            [*like_params, *params, args.limit]).fetchall()
        engine = "like"

    items = [{
        "id": r["id"], "title": r["title"], "feed_name": r["feed_name"],
        "author": r["author"], "published": rss_lib.fmt_local(r["published"]),
        "url": r["url"],
        "snippet": rss_lib.make_snippet(r["title"], r["content_text"], args.query),
    } for r in rows]
    rss_lib.out({"ok": True, "query": args.query, "engine": engine,
                 "count": len(items), "results": items,
                 "note": "用 articles.py --read <id> 阅读全文"})


if __name__ == "__main__":
    main()
