#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""特别关注词条的全网新闻检索（纯标准库，免 Key）。

用法：
  # 单次检索（临时查一家公司）
  python3 scripts/watch_news.py --kw "电子城高科"

  # 多个词条
  python3 scripts/watch_news.py --kw "电子城高科,知鱼智联" --limit 8 --days 3

  # 持久观察名单（默认自动读取 <skill>/data/watchlist.json）
  python3 scripts/watch_news.py            # 用名单
  python3 scripts/watch_news.py --list     # 查看名单

数据源降级链：Google News RSS 搜索 → Bing News RSS 搜索
  - Google News 条目链接是跳转链接（点击仍可到达原文），来源名较全
  - Bing News 为直接链接，但条数少

输出 JSON：
  {"ok": true, "watches": [{"kw": "...", "count": n,
    "items": [{"title", "url", "source", "published"}]}],
   "sources": {"google-news": {"ok", "count"}, ...}}

【防幻觉纪律】本脚本只返回搜索源实际返回的条目；没搜到就是没搜到（count=0），
绝不允许模型自己补内容。
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WATCHLIST = os.path.join(ROOT, "data", "watchlist.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

GNEWS = ("https://news.google.com/rss/search?q={q}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans")
BNEWS = "https://www.bing.com/news/search?q={q}&format=rss"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "zh-CN,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def parse_pubdate(s):
    """RSS pubDate（如 'Wed, 16 Sep 2026 07:00:00 GMT'）→ 'YYYY-MM-DD HH:MM'（本地）。"""
    if not s:
        return ""
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone().strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    return ""


def gnews(kw):
    root = ET.fromstring(fetch(GNEWS.format(q=urllib.parse.quote(kw))))
    items = []
    for it in root.findall(".//item"):
        t = (it.findtext("title") or "").strip()
        if not t:
            continue
        items.append({"title": t,
                      "url": (it.findtext("link") or "").strip(),
                      "source": (it.findtext("source") or "").strip(),
                      "published": parse_pubdate(it.findtext("pubDate"))})
    if not items:
        raise RuntimeError("google-news empty")
    return items, "google-news"


def bnews(kw):
    root = ET.fromstring(fetch(BNEWS.format(q=urllib.parse.quote(kw))))
    items = []
    for it in root.findall(".//item"):
        t = (it.findtext("title") or "").strip()
        if not t:
            continue
        items.append({"title": t,
                      "url": (it.findtext("link") or "").strip(),
                      "source": (it.findtext("source") or "").strip(),
                      "published": parse_pubdate(it.findtext("pubDate"))})
    if not items:
        raise RuntimeError("bing-news empty")
    return items, "bing-news"


# 常见公司后缀 → 用于生成「相关性片段」
SUFFIXES = ("股份有限公司", "有限责任公司", "控股集团", "有限公司", "集团",
            "股份", "高科", "科技", "控股", "公司")


def fragments(kw):
    """词条的相关性片段：全称 → 去后缀 → 前 2 字（>=4 字时）。
    用于清掉「标题根本没提公司」的蹭词垃圾（搜索源偶尔返回）。"""
    parts = [kw]
    for s in SUFFIXES:
        if kw.endswith(s) and len(kw) > len(s) + 1:
            parts.append(kw[:-len(s)])
    if len(kw) >= 4:
        parts.append(kw[:2])
    return parts


def search_kw(kw, limit, days, strict=True):
    """单词条检索：降级链 + 去重 + 时间过滤 + 截断。"""
    items, src = None, ""
    for fn in (gnews, bnews):
        try:
            items, src = fn(kw)
            break
        except Exception:
            continue
    if items is None:
        return [], ""

    # 相关性过滤：标题必须至少含一个片段（默认开，清掉蹭词垃圾）
    if strict:
        frags = fragments(kw)
        items = [i for i in items if any(f in i["title"] for f in frags)]

    # 去重（标题归一化）
    seen, deduped = set(), []
    for i in items:
        k = re.sub(r"\s+", "", i["title"]).lower()
        if k in seen:
            continue
        seen.add(k)
        deduped.append(i)

    # 时间过滤（仅保留近 N 天；无日期的条目保留）
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        fresh = []
        for i in deduped:
            p = i.get("published") or ""
            if not p:
                fresh.append(i)
                continue
            try:
                dt = datetime.strptime(p, "%Y-%m-%d %H:%M").astimezone()
                if dt >= cutoff:
                    fresh.append(i)
            except (ValueError, TypeError):
                fresh.append(i)
        deduped = fresh

    deduped.sort(key=lambda x: x.get("published") or "", reverse=True)
    return deduped[:limit], src


def load_watchlist():
    if not os.path.exists(WATCHLIST):
        return []
    try:
        d = json.load(open(WATCHLIST, encoding="utf-8"))
        return [k.strip() for k in d.get("keywords", []) if str(k).strip()]
    except (OSError, json.JSONDecodeError):
        return []


def main():
    ap = argparse.ArgumentParser(description="特别关注词条全网新闻检索")
    ap.add_argument("--kw", default="", help="词条，多个用逗号分隔；不给则读 watchlist.json")
    ap.add_argument("--limit", type=int, default=8, help="每个词条最多几条")
    ap.add_argument("--days", type=int, default=3, help="只保留近 N 天的条目（0=不限）")
    ap.add_argument("--list", action="store_true", help="查看当前观察名单")
    ap.add_argument("--no-strict", action="store_true", help="关掉标题相关性过滤（词条很短/易歧义时慎用）")
    args = ap.parse_args()

    if args.list:
        print(json.dumps({"ok": True, "watchlist": load_watchlist(), "path": WATCHLIST},
                         ensure_ascii=False, indent=2))
        return

    kws = [k.strip() for k in args.kw.split(",") if k.strip()] or load_watchlist()
    if not kws:
        print(json.dumps({"ok": False,
                          "error": "没有词条：用 --kw 指定，或在 data/watchlist.json 里配 keywords"},
                         ensure_ascii=False))
        sys.exit(1)

    watches, sources = [], {}
    for kw in kws:
        items, src = search_kw(kw, args.limit, args.days, strict=not args.no_strict)
        watches.append({"kw": kw, "count": len(items), "items": items})
        sources[kw] = {"ok": bool(items), "source": src, "count": len(items)}

    print(json.dumps({"ok": True, "watches": watches, "sources": sources},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
