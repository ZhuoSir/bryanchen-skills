#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""网页新闻补充源（纯标准库，零依赖，免 Key）。

用途：`news_api.py`（60s 聚合）每日只有 15 条，晨报+晚报去重后容易把池子榨干。
本脚本从**新闻频道页**抓当日头条，拿到**原文链接**（不像 60s 只给百度搜索链接），
用于晚报补量。抓来的条目同样要过 `sent_log.py filter`，避免与晨报重复。

用法：
  python3 scripts/news_web.py                          # 默认 中华网国际+国内
  python3 scripts/news_web.py --sources china-intl,china-dom,people --limit 20
  python3 scripts/news_web.py --sources all --limit 30
  python3 scripts/news_web.py --list                   # 列出可用站点

输出 JSON：
  {"items": [{title, url, site, outlet, time}], "sources": {"china-intl": {"ok", "count"}, ...}}
  site=站点名；outlet=该条标注的媒体来源（中华网页面自带，其他站点可能为空）

失败策略：单站点失败不阻塞，用其余站点补齐；全部失败才退出码 1。
"""
import argparse
import html as html_mod
import json
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

# 站点配置：key -> (站点名, 列表页, 解析模式, 文章 URL 正则)
SOURCES = {
    "china-intl": ("中华网·国际", "https://news.china.com/zh_cn/international/index.html",
                   "china", r"/\d{8}/\d+\.html"),
    "china-dom": ("中华网·国内", "https://news.china.com/zh_cn/domestic/index.html",
                  "china", r"/\d{8}/\d+\.html"),
    "people": ("人民网", "http://www.people.com.cn/", "generic", r"(people\.com\.cn|peopleapp\.com)"),
    "gmw": ("光明网", "https://www.gmw.cn/", "generic", r"gmw\.cn"),
    "chinanews": ("中新网", "https://www.chinanews.com.cn/", "generic", r"chinanews\.com\.cn"),
}

# 频道页里的导航/服务类噪声
NOISE = ("举报", "版权", "关于我们", "客户端", "广告", "招聘", "注册", "登录", "联系",
         "English", "手机版", "安卓", "Android", "iOS", "APP", "免责", "隐私", "合作",
         "网站地图", "RSS", "首页", "更多", "订阅")

ANCHOR_RE = re.compile(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.S)


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


def clean(text):
    t = re.sub(r"<[^>]+>", "", text or "")
    t = html_mod.unescape(t)
    return re.sub(r"\s+", " ", t).strip(" ·|>-—")


def good(title, url, urlpat):
    if not (8 <= len(title) <= 60):
        return False
    if any(n in title for n in NOISE):
        return False
    if urlpat and not re.search(urlpat, url):
        return False
    return True


def parse_china(page, urlpat, site):
    """中华网：<li><h3 class="item_title"><a>…</a></h3><em class="item_source">媒体</em><em class="item_time">日期</em>

    按 <li> 切块再逐块取三个字段 —— 比一条大正则可靠（媒体名/日期是可选字段）。
    """
    out = []
    for chunk in re.split(r"<li[ >]", page):
        m = re.search(r'<h3 class="item_title">\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', chunk, re.S)
        if not m:
            continue
        url, title = m.group(1), clean(m.group(2))
        if not good(title, url, urlpat):
            continue
        src = re.search(r'<em class="item_source">(.*?)</em>', chunk, re.S)
        tm = re.search(r'<em class="item_time">(.*?)</em>', chunk, re.S)
        out.append({"title": title, "url": url, "site": site,
                    "outlet": clean(src.group(1)) if src else "",
                    "time": clean(tm.group(1)) if tm else ""})
    return out


def parse_generic(page, urlpat, site):
    """通用：锚文本即标题，按文章 URL 正则过滤。"""
    out = []
    for m in ANCHOR_RE.finditer(page):
        url, title = m.group(1), clean(m.group(2))
        if good(title, url, urlpat):
            out.append({"title": title, "url": url, "site": site, "outlet": "", "time": ""})
    return out


def fetch_source(key, limit):
    name, url, mode, urlpat = SOURCES[key]
    try:
        page = fetch(url)
    except Exception as e:                      # 网络/HTTP 异常
        return {"ok": False, "name": name, "error": str(e)[:120], "items": []}
    items = parse_china(page, urlpat, name) if mode == "china" else parse_generic(page, urlpat, name)
    seen, uniq = set(), []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)
    return {"ok": True, "name": name, "count": len(uniq), "items": uniq[:limit]}


def main():
    ap = argparse.ArgumentParser(description="网页新闻补充源")
    ap.add_argument("--sources", default="china-intl,china-dom",
                    help="逗号分隔的站点 key，或 all")
    ap.add_argument("--limit", type=int, default=15, help="每个站点最多取几条（默认 15）")
    ap.add_argument("--list", action="store_true", help="列出可用站点")
    args = ap.parse_args()

    if args.list:
        print(json.dumps({k: {"name": v[0], "url": v[1]} for k, v in SOURCES.items()},
                         ensure_ascii=False, indent=2))
        return

    keys = list(SOURCES) if args.sources.strip() == "all" else \
        [k.strip() for k in args.sources.split(",") if k.strip() in SOURCES]
    if not keys:
        print(json.dumps({"error": f"无有效站点，可选: {','.join(SOURCES)}"}, ensure_ascii=False))
        sys.exit(1)

    results, merged, seen = {}, [], set()
    for k in keys:
        r = fetch_source(k, args.limit)
        results[k] = {"ok": r["ok"], "name": r["name"], "count": r.get("count", 0),
                      **({"error": r["error"]} if not r["ok"] else {})}
        for it in r["items"]:
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            merged.append(it)

    ok_count = sum(1 for v in results.values() if v["ok"])
    print(json.dumps({
        "date_note": "频道页当日头条，非全量；条目需再过 sent_log.py filter 去重",
        "ok_sources": ok_count, "total": len(merged),
        "sources": results, "items": merged,
    }, ensure_ascii=False, indent=2))
    if ok_count == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
