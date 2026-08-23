#!/usr/bin/env python3
"""morning-report: 虎扑体育新闻 + 当日赛程抓取（足球/篮球，零依赖，Python 标准库）。

数据源为虎扑移动端页面（静态 HTML / 内嵌 __NEXT_DATA__ JSON，无需 API Key）：
    篮球新闻: https://m.hupu.com/nba            赛程: /nba/schedule
    足球新闻: https://m.hupu.com/soccer         赛程: /soccer/schedule
新闻页按最新活跃排序，**不含发布时间**。置顶帖（块内含 class="news-top" 徽标）
全量保留并标注 `"pinned": true`，普通帖取前 N 条（--per-section，建议 5-10）。
赛程页内嵌 __NEXT_DATA__ JSON，按今天日期过滤；**今日无比赛时输出空列表**。

用法:
    python3 hupu.py [--per-section 5]
输出:
    stdout JSON: {"date": "...", "date_note": "...",
                  "sections": {"basketball": [...], "football": [...]},
                  "matches": {"basketball": [...], "football": [...]}}
                  新闻每条 {"title","url"}，置顶帖额外带 "pinned": true；
                  比赛每条 {"time","competition","home","away",
                            "home_score","away_score","status"}
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.request
from datetime import date

# 移动端 UA：桌面 UA 可能被重定向到桌面版
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
      "Mobile/15E148 Safari/604.1")

# name -> 频道页 URL
CHANNELS = {
    "basketball": "https://m.hupu.com/nba",
    "football": "https://m.hupu.com/soccer",
}

# name -> 赛程页 URL
SCHEDULES = {
    "basketball": "https://m.hupu.com/nba/schedule",
    "football": "https://m.hupu.com/soccer/schedule",
}

ITEM_RE = re.compile(
    r'<a class="news-item"[^>]*href="([^"]+)"[\s\S]*?</a>')
TITLE_RE = re.compile(
    r'<div class="news-item-info-title">([\s\S]*?)</div>')
PINNED_RE = re.compile(r'class="news-top"')  # 置顶徽标
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">([\s\S]*?)</script>')


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


def _next_data(page):
    m = NEXT_DATA_RE.search(page)
    if not m:
        raise RuntimeError("__NEXT_DATA__ not found")
    return json.loads(m.group(1))["props"]["pageProps"]


def today_matches_soccer(url, today):
    """足球赛程：pageProps.data.games 按 day 分组。"""
    pp = _next_data(fetch(url))
    matches = []
    for g in pp["data"]["games"]:
        if g.get("day") != today:
            continue
        for m in g["data"]:
            t = re.search(r"(\d+)点(\d+)分", m.get("dateTime") or "")
            matches.append({
                "time": f"{int(t.group(1)):02d}:{t.group(2)}" if t else None,
                "competition": m.get("title"),
                "home": m["home"]["name"], "away": m["away"]["name"],
                "home_score": m.get("home_score"),
                "away_score": m.get("away_score"),
                "status": (m.get("status") or {}).get("txt"),
            })
    return matches


def today_matches_nba(url, today):
    """篮球赛程：pageProps.gameList 按 day 分组（休赛期无今日条目 -> 空列表）。"""
    pp = _next_data(fetch(url))
    matches = []
    for g in pp["gameList"]:
        if g.get("day") != today:
            continue
        for m in g["matchList"]:
            t = (m.get("matchTime") or "").split(" ")
            stage = m.get("competitionStageDesc") or m.get("competitionTypeCn")
            matches.append({
                "time": t[1][:5] if len(t) > 1 else None,
                "competition": f"NBA{stage or ''}",
                "home": m.get("homeTeamName"), "away": m.get("awayTeamName"),
                "home_score": m.get("homeScore"),
                "away_score": m.get("awayScore"),
                "status": m.get("matchStatusChinese"),
            })
    return matches


SCHEDULE_PARSERS = {
    "football": today_matches_soccer,
    "basketball": today_matches_nba,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-section", type=int, default=5)
    args = ap.parse_args()

    today = date.today().strftime("%Y%m%d")
    sections, matches, errors = {}, {}, []
    for name, url in CHANNELS.items():
        try:
            sections[name] = scrape(url, args.per_section)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name} news: {e}")
            sections[name] = []
    for name, url in SCHEDULES.items():
        try:
            matches[name] = SCHEDULE_PARSERS[name](url, today)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name} schedule: {e}")
            matches[name] = []

    out = {
        "date": date.today().isoformat(),
        "date_note": "新闻为频道页实时热帖（无发布时间，按最新活跃排序）；"
                     "比赛为当日赛程，空列表表示今日无比赛",
        "sections": sections,
        "matches": matches,
    }
    if errors:
        out["errors"] = errors
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()
    if not any(sections.values()) and not any(matches.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
