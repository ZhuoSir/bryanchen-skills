#!/usr/bin/env python3
"""web-search: 零依赖网页搜索（Python 标准库，免 API Key）。

引擎降级链：Bing（cn.bing.com，国内稳定）→ DuckDuckGo Lite。支持时间过滤，输出统一 JSON。
适用于无内置搜索工具的 agent 环境，让任何环境都具备真实搜索能力。

用法:
    python3 search.py --query "人形机器人" [--max 5] [--time day|week|month]
输出:
    stdout JSON: {"query", "engine", "note"?, "results": [{title, url, snippet}]}
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# DDG Lite 时间过滤参数
DF_MAP = {"day": "d", "week": "w", "month": "m"}
# Bing 时间过滤：过去24小时/一周/一月
BING_FILTER = {"day": 'ex1:"ez1"', "week": 'ex1:"ez2"', "month": 'ex1:"ez3"'}

MIN_RESPONSE = 500  # 响应小于该字节数视为被风控/失败


def fetch(url, tries=3, timeout=12, interval=1.5):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", errors="replace")
            if len(body) < MIN_RESPONSE:
                raise RuntimeError(f"响应过短({len(body)}B)，疑似被风控")
            return body
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < tries - 1:
                time.sleep(interval)
    raise last


def clean(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def search_ddg(query, max_results, time_range):
    """DuckDuckGo Lite HTML 版。"""
    params = {"q": query}
    if time_range in DF_MAP:
        params["df"] = DF_MAP[time_range]
    url = "https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode(params)
    body = fetch(url)

    # 结果链接：<a class="result-link" href="//duckduckgo.com/l/?uddg=...">标题</a>
    results = []
    for m in re.finditer(r"<a[^>]*class=\"result-link\"[^>]*>(.*?)</a>", body, re.S):
        tag = m.group(0)
        href_m = re.search(r'href="([^"]+)"', tag)
        if not href_m:
            continue
        href = href_m.group(1)
        uddg = re.search(r"uddg=([^&\"]+)", href)  # 还原跳转链接
        if uddg:
            href = urllib.parse.unquote(uddg.group(1))
        elif href.startswith("//"):
            continue  # 无法还原的跳转链接跳过
        title = clean(m.group(1))
        if title and href.startswith("http"):
            results.append({"title": title, "url": href})

    # 摘要：<td class="result-snippet">...</td>
    snippets = re.findall(r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', body, re.S)
    for i, sn in enumerate(snippets[: len(results)]):
        results[i]["snippet"] = clean(sn)

    if not results:
        raise RuntimeError("DDG Lite 无结果（可能被风控）")
    return results[:max_results]


def search_bing(query, max_results, time_range):
    """Bing 网页版。"""
    params = {"q": query, "setlang": "zh-CN", "count": str(max_results * 2)}
    if time_range in BING_FILTER:
        params["filters"] = BING_FILTER[time_range]
    url = "https://www.bing.com/search?" + urllib.parse.urlencode(params)
    body = fetch(url)

    results = []
    for block in re.findall(r'<li class="b_algo".*?</li>', body, re.S):
        # h2 和 a 都可能带属性（如 class="" / target="_blank"），正则须容忍
        m = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not m:
            continue
        entry = {"title": clean(m.group(2)), "url": m.group(1)}
        p = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
        if p:
            entry["snippet"] = clean(p.group(1))
        if entry["title"]:
            results.append(entry)

    if not results:
        raise RuntimeError("Bing 无结果（可能被风控）")
    return results[:max_results]


CHAIN = [("bing", search_bing), ("ddg-lite", search_ddg)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", "-q", required=True, help="搜索关键词")
    ap.add_argument("--max", type=int, default=5, help="最多返回条数（默认 5）")
    ap.add_argument("--time", choices=["day", "week", "month"], default="",
                    help="时间过滤：day=24小时内 / week=一周内 / month=一月内")
    args = ap.parse_args()

    errors = []
    for name, fn in CHAIN:
        try:
            results = fn(args.query, args.max, args.time)
            out = {"query": args.query, "engine": name, "results": results}
            if args.time:
                out["time_filter"] = args.time
            if errors:
                out["note"] = "降级链生效: " + "; ".join(errors)
            json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
            print()
            return
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    json.dump({"query": args.query, "engine": None, "results": [],
               "error": "; ".join(errors)}, sys.stdout, ensure_ascii=False)
    print()
    sys.exit(1)


if __name__ == "__main__":
    main()
