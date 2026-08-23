#!/usr/bin/env python3
"""morning-report: 综合新闻（国际 + 国内）抓取 —— 免费新闻 API 版（零依赖，Python 标准库）。

不使用搜索引擎、不需要任何 API Key。来源链按实测速度/稳定性排序，
**经常超时的来源放在最后**（见 CHAIN 注释）：

  1. 60s API 镜像（每天60秒读懂世界 JSON，免 Key，实测 ~1-2s）
  2. yyxw.com 每日早报页（HTML 抓取，实测 ~0.5s，与 60s 同源的备选页面）
  3. Google News 中文 RSS（免 Key，但国内网络环境经常超时，仅作最后兜底）

用法:
    python3 news_api.py [--max 15]
输出:
    stdout JSON: {"date": "...", "source": "...", "source_link": "...",
                  "items": [{"title","url"}, ...], "note"?: "..."}
说明:
    - 60s API 的条目本身无独立链接，脚本为每条生成"百度搜索"链接（与 yyxw 站
      内做法一致），digest 原文链接放在顶层 source_link。
    - 条目为国际/国内混合，由组装晨报的模型按内容归类到两个板块。
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

TIMEOUT = 10  # 每个源单次请求超时（秒）


def fetch(url, tries=2, timeout=TIMEOUT):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < tries - 1:
                time.sleep(1.0)
    raise last


def baidu_link(title):
    """为无独立链接的条目生成可点击的百度搜索链接（与 yyxw 站内做法一致）。"""
    q = re.sub(r"\s+", " ", title).strip()
    return "https://www.baidu.com/s?wd=" + urllib.parse.quote(q)


# ---------- 源 1：60s API（实测最快，~1-2s）----------

def from_60s_api(mirror):
    text = fetch(mirror)
    data = json.loads(text)
    if data.get("code") != 200 or not data.get("data", {}).get("news"):
        raise RuntimeError(f"60s api: bad response code={data.get('code')}")
    d = data["data"]
    items = [{"title": t.strip(), "url": baidu_link(t)}
             for t in d["news"] if t.strip()]
    return {
        "date": d.get("date"),
        "source": f"每天60秒读懂世界 API ({urllib.parse.urlparse(mirror).netloc})",
        "source_link": d.get("link") or mirror,
        "tip": d.get("tip"),  # 每日一句（可用于晨报末尾激励语）
        "items": items,
    }


# ---------- 源 2：yyxw.com 早报页（实测 ~0.5s）----------

def from_yyxw(_url):
    page = fetch("https://www.yyxw.com/")
    page = re.sub(r"<(script|style)[\s\S]*?</\1>", "", page)
    text = re.sub(r"<br\s*/?>", "\n", page)
    text = re.sub(r"</(p|div|li)>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    m = re.search(r"📅\s*(\d{4}-\d{2}-\d{2})", text)
    day = m.group(1) if m else None
    # 条目形如 "1  标题。 百度搜索 2  标题。 百度搜索 ..."
    items = []
    body = text.split("百度热搜")[0]  # 防御：只取正文区
    for num, title in re.findall(
            r"(?:^|\n|百度搜索)\s*(\d{1,2})\s+(.+?)(?=\s*百度搜索|\n)", body):
        title = re.sub(r"\s+", " ", title).strip(" 。;；")
        if len(title) >= 8:
            items.append({"title": title, "url": baidu_link(title)})
    if len(items) < 5:
        raise RuntimeError(f"yyxw: only {len(items)} items parsed")
    return {
        "date": day,
        "source": "每日60秒读懂世界 (yyxw.com)",
        "source_link": "https://www.yyxw.com/",
        "items": items,
    }


# ---------- 源 3：Google News 中文 RSS（经常超时，放最后兜底）----------

def from_google_news(_url):
    url = ("https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans")
    text = fetch(url, tries=1, timeout=8)  # 易超时：不重试、超时收紧
    root = ET.fromstring(text)
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if title and link:
            items.append({"title": title, "url": link})
    if len(items) < 5:
        raise RuntimeError(f"google news: only {len(items)} items parsed")
    today = date.today().isoformat()
    return {
        "date": today,
        "source": "Google News 中文 RSS",
        "source_link": "https://news.google.com/",
        "items": items,
    }


# 降级链：按实测速度/稳定性排序，经常超时的放最后
CHAIN = [
    ("60s-api#1", from_60s_api, "https://60s.viki.moe/v2/60s"),
    ("60s-api#2", from_60s_api, "https://60s-api.viki.moe/v2/60s"),
    ("yyxw", from_yyxw, "https://www.yyxw.com/"),
    ("google-news-rss", from_google_news,
     "https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),  # 易超时，最后
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=15, help="最多输出多少条")
    args = ap.parse_args()

    errors = []
    for name, fn, url in CHAIN:
        try:
            out = fn(url)
            out["items"] = out["items"][: args.max]
            out["chain_source"] = name
            if errors:
                out["note"] = "fallback used: " + "; ".join(errors)
            today = date.today().isoformat()
            if out.get("date") and out["date"] != today:
                out["warning"] = (f"数据日期 {out['date']} 不是今天 {today}，"
                                  "今日早报可能尚未更新")
            json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
            print()
            return
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    json.dump({"date": None, "source": None, "source_link": None,
               "items": [], "error": "; ".join(errors)},
              sys.stdout, ensure_ascii=False)
    print()
    sys.exit(1)


if __name__ == "__main__":
    main()
