#!/usr/bin/env python3
"""morning-report: 虎扑体育新闻抓取（足球/篮球，零依赖，Python 标准库）。

数据源为虎扑移动端频道页（静态 HTML，无需 API Key）：
    篮球: https://m.hupu.com/nba
    足球: https://m.hupu.com/soccer
页面按最新活跃排序；**不含发布时间**。置顶帖（块内含 class="news-top" 徽标）
全量保留并标注 `"pinned": true`，普通帖取前 N 条（--per-section，建议 5-10）。

用法:
    python3 hupu.py [--per-section 5]
输出:
    stdout JSON: {"date": null, "date_note": "...",
                  "sections": {"basketball": [...], "football": [...]}}
                  每条 {"title","url"}，置顶帖额外带 "pinned": true
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.request

# 移动端 UA：桌面 UA 可能被重定向到桌面版
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
      "Mobile/15E148 Safari/604.1")

# name -> 频道页 URL
CHANNELS = {
    "basketball": "https://m.hupu.com/nba",
    "football": "https://m.hupu.com/soccer",
}

ITEM_RE = re.compile(
    r'<a class="news-item"[^>]*href="([^"]+)"[\s\S]*?</a>')
TITLE_RE = re.compile(
    r'<div class="news-item-info-title">([\s\S]*?)</div>')
PINNED_RE = re.compile(r'class="news-top"')  # 置顶徽标


def fetch(url, tries=3, timeout=15):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < tries - 1:
                time.sleep(1.5)
    raise last


def scrape(url, per_section):
    page = fetch(url)
    pinned, latest, seen = [], [], set()
    for m in ITEM_RE.finditer(page):
        href, block = m.group(1), m.group(0)
        if "/bbs/" not in href:  # 跳过活动页等非帖子链接
            continue
        t = TITLE_RE.search(block)
        if not t:
            continue
        title = html.unescape(
            re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t.group(1)))).strip()
        if not title or href in seen:
            continue
        seen.add(href)
        item = {"title": title, "url": href}
        if PINNED_RE.search(block):  # 置顶帖单独收集并标注
            item["pinned"] = True
            pinned.append(item)
        else:
            latest.append(item)
    # 置顶帖全量保留 + 最新帖取前 per_section 条
    items = pinned + latest[:per_section]
    if not items:
        raise RuntimeError(f"{url}: no news items parsed")
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-section", type=int, default=5)
    args = ap.parse_args()

    sections, errors = {}, []
    for name, url in CHANNELS.items():
        try:
            sections[name] = scrape(url, args.per_section)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
            sections[name] = []

    out = {
        "date": None,
        "date_note": "虎扑频道页不含发布时间，条目按最新活跃排序",
        "sections": sections,
    }
    if errors:
        out["errors"] = errors
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()
    if not any(sections.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
