#!/usr/bin/env python3
"""rss-skill: 导出本地文章库。

用法:
    python3 export.py                              # 导出全部 → JSON（默认到 /tmp/rss-skill/export_<日期>.json）
    python3 export.py --format markdown            # 导出为 Markdown（含全文，按订阅源分组）
    python3 export.py --format text                # 纯文本
    python3 export.py --format jsonl               # JSON Lines（每行一条，适合导入数据库/大数据工具）
    python3 export.py --feed 量子位                 # 只导出某个订阅源
    python3 export.py --days 7                     # 只导出最近 7 天发布的
    python3 export.py --no-content                 # 不含正文（只要标题/链接等元数据，文件更小）
    python3 export.py --out /path/to/file.json     # 指定输出路径
输出: stdout 打印导出结果摘要（文件路径、条数、大小）
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rss_lib  # noqa: E402

FIELDS_META = ["id", "guid", "url", "title", "author", "published",
               "feed_name", "source", "fetched_at"]
FIELDS_FULL = FIELDS_META + ["content_text", "content_html"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=["json", "jsonl", "markdown", "text"],
                    default="json")
    ap.add_argument("--feed", help="按订阅源名过滤")
    ap.add_argument("--days", type=int, help="只导出最近 N 天发布")
    ap.add_argument("--no-content", action="store_true", help="不含正文")
    ap.add_argument("--out", help="输出文件路径（默认 /tmp/rss-skill/export_<日期>.<后缀>）")
    args = ap.parse_args()

    cfg = rss_lib.load_config()
    conn, _ = rss_lib.open_db(cfg)

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
    fields = FIELDS_META if args.no_content else FIELDS_FULL
    rows = conn.execute(
        f"SELECT {','.join(fields)} FROM articles {cond} "
        f"ORDER BY feed_name, published DESC", params).fetchall()
    articles = [dict(r) for r in rows]

    suffix = {"json": "json", "jsonl": "jsonl",
              "markdown": "md", "text": "txt"}[args.format]
    out_path = args.out or os.path.join(
        "/tmp/rss-skill",
        f"export_{datetime.now().strftime('%Y%m%d_%H%M')}.{suffix}")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if args.format == "json":
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "exported_at": datetime.now().isoformat(timespec="seconds"),
                "count": len(articles),
                "with_content": not args.no_content,
                "articles": articles,
            }, f, ensure_ascii=False, indent=2)
    elif args.format == "jsonl":
        with open(out_path, "w", encoding="utf-8") as f:
            for a in articles:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
    else:  # markdown / text
        lines = []
        if args.format == "markdown":
            lines.append(f"# RSS 订阅文章导出（{len(articles)} 篇）\n")
            lines.append(f"> 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        cur_feed = None
        for a in articles:
            if a["feed_name"] != cur_feed:
                cur_feed = a["feed_name"]
                lines.append(f"\n## 📰 {cur_feed}\n" if args.format == "markdown"
                             else f"\n===== {cur_feed} =====\n")
            lines.append(f"### {a['title']}" if args.format == "markdown"
                         else f"【{a['title']}】")
            lines.append(f"时间：{rss_lib.fmt_local(a['published'])}  "
                         f"链接：{a['url']}")
            if not args.no_content and a.get("content_text"):
                lines.append("")
                lines.append(a["content_text"])
            lines.append("\n---\n" if args.format == "markdown" else "\n")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    size_kb = os.path.getsize(out_path) // 1024
    rss_lib.out({"ok": True, "file": out_path, "format": args.format,
                 "count": len(articles), "size_kb": size_kb,
                 "with_content": not args.no_content})


if __name__ == "__main__":
    main()
