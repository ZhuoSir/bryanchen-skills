#!/usr/bin/env python3
"""morning-report: AI 行业新闻抓取（RSS/Atom，零依赖，Python 标准库）。

源：量子位、TechCrunch AI、InfoQ 中文（均为公开 RSS）。
用法:
    python3 fetch_rss.py [--days 2] [--per-source 3]
输出:
    stdout JSON: {"sources": {name: {"ok": bool, "items": [...], "error"?}}, "items": [...]}
"""
import argparse
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

FEEDS = {
    "量子位": "https://www.qbitai.com/feed",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "InfoQ中文": "https://www.infoq.cn/feed",
}

ATOM = "{http://www.w3.org/2005/Atom}"


def fetch(url, tries=2, timeout=15):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < tries - 1:
                time.sleep(1.5)
    raise last


def parse_date(raw):
    if not raw:
        return None
    raw = raw.strip()
    try:
        dt = parsedate_to_datetime(raw)  # RFC 822 (RSS pubDate)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        pass
    try:  # ISO 8601 (Atom)
        dt = datetime.fromisoformat(re.sub(r"Z$", "+00:00", raw))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def parse_feed(data, cutoff):
    """兼容 RSS 2.0 与 Atom，返回 [{title,url,published}]。"""
    root = ET.fromstring(data)
    items = []
    if root.tag == f"{ATOM}feed":  # Atom
        for e in root.findall(f"{ATOM}entry"):
            title = e.findtext(f"{ATOM}title")
            link_el = e.find(f"{ATOM}link[@rel='alternate']") or e.find(f"{ATOM}link")
            url = link_el.get("href") if link_el is not None else ""
            pub = (e.findtext(f"{ATOM}published")
                   or e.findtext(f"{ATOM}updated"))
            dt = parse_date(pub)
            if dt and dt >= cutoff and url:
                items.append({"title": clean(title), "url": url,
                              "published": dt.isoformat()})
    else:  # RSS 2.0
        for it in root.iter("item"):
            title = it.findtext("title")
            url = it.findtext("link")
            dt = parse_date(it.findtext("pubDate"))
            if url and (dt is None or dt >= cutoff):
                items.append({"title": clean(title), "url": clean(url),
                              "published": dt.isoformat() if dt else None})
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=2,
                    help="取最近 N 天的条目（AI 源日更量不稳，默认 2）")
    ap.add_argument("--per-source", type=int, default=3)
    args = ap.parse_args()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    sources, merged = {}, []
    for name, url in FEEDS.items():
        try:
            items = parse_feed(fetch(url), cutoff)[: args.per_source]
            for it in items:
                it["source"] = name
            sources[name] = {"ok": True, "count": len(items), "items": items}
            merged.extend(items)
        except Exception as e:  # noqa: BLE001
            sources[name] = {"ok": False, "error": str(e), "items": []}

    json.dump({"cutoff": cutoff.isoformat(), "sources": sources,
               "items": merged}, sys.stdout, ensure_ascii=False, indent=2)
    print()
    if not merged:
        sys.exit(1)


if __name__ == "__main__":
    main()
