#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""天气新闻（中国天气网新闻频道，纯标准库，免 Key）。

用途：在晨报/晚报的「天气」面板里，天气表下面配 5 条天气相关新闻
（全国天气形势、预警、以及和 CITIES 相关的城市天气消息）。

用法：
  python3 scripts/weather_news.py --limit 5
  python3 scripts/weather_news.py --limit 5 --cities "北京,深圳,上海,杭州,通辽,崇礼"

排序口径：① 命中指定城市的条目 → ② 预警类 → ③ 其余（保持源站顺序）
输出 JSON：{"items": [{title, url, source, tag}], "sources": {"weather.com.cn": {"ok", "count"}}}
"""
import argparse
import html as html_mod
import json
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
LIST_URL = "http://news.weather.com.cn/"
ART_RE = re.compile(r'<a[^>]+href="(https?://news\.weather\.com\.cn/\d{4}/\d{2}/\d+\.shtml)"[^>]*>(.*?)</a>', re.S)
NOISE = ("首页", "更多", "English", "客户端", "注册", "登录", "关于我们", "广告", "招聘")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


LABEL_RE = re.compile(r"^(推荐|热点|聚焦|视频|图集|专题|直播|图解)\s*")


def norm_title(t):
    return LABEL_RE.sub("", t).strip()


def clean(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    t = html_mod.unescape(t)
    return re.sub(r"\s+", " ", t).strip(" ·|>-—")


def tag_of(title, cities):
    for c in cities:
        if c and c in title:
            return f"{c}"
    if "预警" in title or "警报" in title:
        return "预警"
    return "全国"


def main():
    ap = argparse.ArgumentParser(description="天气新闻（中国天气网）")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--cities", default="", help="优先城市，逗号分隔")
    args = ap.parse_args()
    cities = [c.strip() for c in args.cities.split(",") if c.strip()]

    try:
        page = fetch(LIST_URL)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)[:150], "items": []}, ensure_ascii=False))
        sys.exit(1)

    items, seen = [], set()
    for url, raw_title in ART_RE.findall(page):
        title = clean(raw_title)
        if not title or len(title) < 8 or any(n in title for n in NOISE):
            continue
        key = norm_title(title)          # 去掉「推荐/热点」等前缀后再去重
        if key in seen:
            continue
        seen.add(key)
        title = key
        items.append({"title": title, "url": url, "source": "中国天气网",
                      "tag": tag_of(title, cities)})

    rank = {c: i for i, c in enumerate(cities)}
    items.sort(key=lambda x: (0 if x["tag"] in rank else (1 if x["tag"] == "预警" else 2),
                              rank.get(x["tag"], 0)))
    out = items[:args.limit]
    print(json.dumps({"ok": True, "total": len(items), "items": out,
                      "sources": {"news.weather.com.cn": {"ok": True, "count": len(items)}}},
                     ensure_ascii=False, indent=2))
    if not out:
        sys.exit(1)


if __name__ == "__main__":
    main()
