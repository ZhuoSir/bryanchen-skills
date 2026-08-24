#!/usr/bin/env python3
"""web-search: 多引擎联网搜索（Python 标准库零依赖），完整复刻 DSH free-search 插件逻辑。

引擎与降级链（与 DSH web_search 工具一致）：
  首选引擎 → 其他付费引擎（exa/tavily/keenable 无 Key 也走免费通道）→ 免费引擎（bing/anysearch/ddg/ddg-lite/searxng）
- 带 --time 时，支持时间过滤的引擎（tavily/exa/keenable/searxng/ddg/ddg-lite）排在前面；
  首选引擎不支持时间过滤则直接跳过（Note 说明 "does not support time filtering"，而非"失败"）
- 整条链共享 30s 总预算；首选引擎失败原因记入 Note
- API Key 从环境变量读取：EXA_API_KEY / TAVILY_API_KEY / KEENABLE_API_KEY / PERPLEXITY_API_KEY / DEEPSEEK_API_KEY

用法:
    python3 search.py --query "关键词" [--max 5] [--engine bing] [--time day|week|month|year|12h|3d|2mo|1y|YYYY-MM-DD]
输出:
    stdout JSON: {"query", "engine", "note"?, "answer"?, "results": [{title, url, snippet, publishedAt?}]}
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
ACCEPT_LANG = "zh-CN,zh;q=0.9,en;q=0.8"

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"
BING_URL = "https://www.bing.com/search"
ANYSEARCH_URL = "https://api.anysearch.com/v1/search"
TAVILY_URL = "https://api.tavily.com/search"
EXA_URL = "https://api.exa.ai/search"
EXA_MCP_URL = "https://mcp.exa.ai/mcp"
KEENABLE_URL = "https://api.keenable.ai/v1/search"
KEENABLE_MCP_URL = "https://api.keenable.ai/mcp"
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
DEEPSEEK_URL = "https://api.deepseek.com/anthropic/v1/messages"

SEARXNG_INSTANCES = [
    "https://opnxng.com",
    "https://priv.au",
    "https://searx.be",
    "https://searx.tiekoetter.com",
    "https://search.inetol.net",
    "https://paulgo.io",
]

PAID_ENGINES = ["exa", "tavily", "keenable", "perplexity", "deepseek-official"]
FREE_ENGINES = ["bing", "anysearch", "ddg", "ddg-lite", "searxng"]
# 支持时间过滤的引擎
TIME_ENGINES = ["tavily", "exa", "keenable", "searxng", "ddg", "ddg-lite"]
ALL_ENGINES = PAID_ENGINES + FREE_ENGINES

BUDGET_S = 30  # 整条引擎链总预算（与 DSH 一致）
MIN_RESPONSE = 500

DAYS_BY_RANGE = {"day": 1, "week": 7, "month": 30, "year": 365}
SEARXNG_TIME = {"day": "day", "week": "week", "month": "month", "year": "year"}
DDG_DF = {"day": "d", "week": "w", "month": "m", "year": "y"}

# snippet 噪音短语（登录/付费墙/订阅等），与 DSH cleanSnippet 一致
SNIPPET_NOISE = re.compile(
    r"\b(sign up|sign in|log in|login|subscribe( to| for)?|member[- ]?only|"
    r"become a member|create (a )?free account|read more|continue reading|"
    r"story continues|get started|install (the )?app|view on|medium membership|"
    r"join \w+ for free|get updates from this writer|stories in your inbox|"
    r"remember me for|unlock this|free to read|become a patron)\b", re.I)


class EngineError(Exception):
    pass


# ---------- 工具函数 ----------

def clean_snippet(text):
    if not text:
        return text
    t = SNIPPET_NOISE.sub(" ", str(text))
    t = re.sub(r"^\s*(#{1,6}\s*|\[\s*x?\s*\]\s*|-\s*\[\s*x?\s*\]\s*|>\s*)", " ", t, flags=re.M)
    return re.sub(r"\s+", " ", t).strip()[:300]


def strip_tags(raw):
    import html as html_mod
    t = re.sub(r"<[^>]+>", " ", str(raw))
    return html_mod.unescape(re.sub(r"\s+", " ", t)).strip()


def extract_ddg_url(rel):
    if not rel:
        return None
    m = re.search(r"uddg=([^&]+)", rel)
    if m:
        return urllib.parse.unquote(m.group(1))
    if rel.startswith("//"):
        return "https:" + rel
    return rel


def unique_sources(sources, limit):
    seen, out = set(), []
    for s in sources:
        if s.get("url") and s["url"] not in seen:
            seen.add(s["url"])
            out.append(s)
        if len(out) >= limit:
            break
    return out


def parse_time_range(s):
    """day/week/month/year、12h/3d/2mo/1y、YYYY-MM-DD → {"days": N} 或 {"after": date}"""
    if not s:
        return None
    s = str(s).strip().lower()
    if not s:
        return None
    if s in DAYS_BY_RANGE:
        return {"days": DAYS_BY_RANGE[s]}
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return {"after": s}
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(h|hours?|d|days?|w|weeks?|mo|months?|y|years?)$", s)
    if m:
        n, unit = float(m.group(1)), m.group(2)[0]
        days = n / 24 if unit == "h" else n if unit == "d" else n * 7 if unit == "w" else (
            n * 30 if unit == "m" else n * 365)
        return {"days": days}
    raise EngineError(f"无法解析时间范围: {s}")


def approximate_time_range(days):
    """自定义天数 → 固定档（Tavily/SearXNG/DDG 用）"""
    if days <= 2:
        return "day"
    if days <= 14:
        return "week"
    if days <= 90:
        return "month"
    return "year"


def iso_days_ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def format_keenable_relative(days):
    if days <= 0.5:
        return "12h"
    if days < 1:
        return f"{round(days * 24)}h"
    if days < 30:
        return f"{round(days)}d"
    if days < 365:
        return f"{round(days / 30)}mo"
    return f"{round(days / 365)}y"


def http_request(url, timeout=12, method="GET", body=None, headers=None, tries=1, interval=1.5):
    """带重试的 HTTP 请求，返回文本。重试仅用于 GET（HTML 抓取）。"""
    hdrs = {"User-Agent": USER_AGENT, "Accept-Language": ACCEPT_LANG}
    if headers:
        hdrs.update(headers)
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                text = r.read().decode("utf-8", errors="replace")
                status = r.status
            if status == 202 or re.search(r"anomaly|captcha|unusual traffic|robot check",
                                          text[:4000], re.I):
                raise EngineError("DuckDuckGo 触发反爬验证（通常暂时性），Bing 可用")
            if method == "GET" and len(text) < MIN_RESPONSE:
                raise EngineError(f"响应过短({len(text)}B)")
            return text
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            if e.code == 401:
                raise EngineError(f"API key 无效 (HTTP 401) - {url.split('/')[2]}")
            last = EngineError(f"HTTP {e.code} from {url.split('?')[0]}: {detail}".strip(": "))
        except EngineError as e:
            last = e
        except Exception as e:  # noqa: BLE001
            last = EngineError(f"connection error: {e}")
        if attempt < tries - 1:
            time.sleep(interval)
    raise last or EngineError("fetch failed")


def http_json(url, timeout, body, headers=None):
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    text = http_request(url, timeout=timeout, method="POST", body=body, headers=hdrs)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise EngineError(f"invalid JSON from {url.split('/')[2]}")


def mcp_call(url, tool, arguments, timeout):
    """JSON-RPC tools/call；兼容 SSE（Exa）与纯 JSON（Keenable）响应。"""
    text = http_request(url, timeout=timeout, method="POST", headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }, body={"jsonrpc": "2.0", "id": int(time.time() * 1000),
             "method": "tools/call",
             "params": {"name": tool, "arguments": arguments}})
    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        for line in text.splitlines():  # SSE: data: {...}
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    break
                except json.JSONDecodeError:
                    continue
    if not data:
        raise EngineError("MCP 无数据")
    if data.get("error"):
        raise EngineError(f"MCP error: {data['error'].get('message', 'unknown')}")
    result = data.get("result") or {}
    content = result.get("content") or []
    text_out = "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
    if result.get("isError"):
        raise EngineError(f"MCP error: {text_out[:200]}")
    return text_out


def parse_title_url_blocks(text, max_results):
    """解析 'Title: X\nURL: Y\n...' 格式（Exa/Keenable MCP 共用）。"""
    sources = []
    for block in re.split(r"\n(?=Title:)", text or ""):
        title = (re.search(r"^Title: (.+)$", block, re.M) or [None, None])[1]
        url = (re.search(r"^URL: (\S+)$", block, re.M) or [None, None])[1]
        published = ((re.search(r"^(?:Published|Acquired): (.+)$", block, re.M) or [None, None])[1])
        hl = re.split(r"^(?:Highlights|Snippets):$", block, flags=re.M)
        snippet = ""
        if len(hl) > 1:
            lines = [l for l in hl[1].splitlines() if l.strip() and not l.strip().startswith("...")]
            snippet = " ".join(lines[:3])
        if not url:
            continue
        s = {"url": url}
        if title:
            s["title"] = title
        if snippet:
            s["snippet"] = snippet[:300]
        if published and re.match(r"^\d{4}-\d{2}-\d{2}", published):
            s["publishedAt"] = published
        sources.append(s)
    return unique_sources(sources, max_results)


# ---------- 免费引擎 ----------

def search_ddg_html(query, max_results, tr, deadline):
    params = {"q": query}
    if tr and tr.get("days"):
        params["df"] = DDG_DF[approximate_time_range(tr["days"])]
    body = http_request(f"{DDG_HTML_URL}?{urllib.parse.urlencode(params)}",
                        timeout=min(12, deadline), tries=3)
    sources = []
    for block in re.findall(r'<div class="result results_links[\s\S]*?</div>\s*</div>\s*</div>', body):
        url_m = re.search(r'<a[^>]*class="result__a"[^>]*href="([^"]*)"', block)
        title_m = re.search(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', block)
        sn_m = re.search(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', block)
        url = extract_ddg_url(url_m.group(1)) if url_m else None
        if not url:
            continue
        s = {"url": url}
        if title_m:
            s["title"] = strip_tags(title_m.group(1))
        if sn_m:
            s["snippet"] = strip_tags(sn_m.group(1))
        sources.append(s)
    return unique_sources(sources, max_results)


def search_ddg_lite(query, max_results, tr, deadline):
    params = {"q": query}
    if tr and tr.get("days"):
        params["df"] = DDG_DF[approximate_time_range(tr["days"])]
    body = http_request(f"{DDG_LITE_URL}?{urllib.parse.urlencode(params)}",
                        timeout=min(12, deadline), tries=3)
    links = re.findall(r"<a[^>]*class=['\"]result-link['\"][^>]*>[\s\S]*?</a>", body)
    snippets = re.findall(r"class=['\"]result-snippet['\"][^>]*>([\s\S]*?)</td>", body)
    sources = []
    for i, tag in enumerate(links):
        href_m = re.search(r'href="([^"]*)"', tag)
        title_m = re.search(r"class=['\"]result-link['\"][^>]*>(.*?)</a>", tag)
        if not href_m:
            continue
        url = extract_ddg_url(href_m.group(1))
        if not url or not url.startswith("http"):
            continue
        s = {"url": url}
        if title_m:
            s["title"] = strip_tags(title_m.group(1))
        if i < len(snippets):
            s["snippet"] = strip_tags(snippets[i])
        sources.append(s)
    return unique_sources(sources, max_results)


def search_bing(query, max_results, tr, deadline):
    params = {"q": query, "mkt": "zh-CN"}
    body = http_request(f"{BING_URL}?{urllib.parse.urlencode(params)}",
                        timeout=min(12, deadline), tries=3)
    sources = []
    for block in re.findall(r'<li class="b_algo"[\s\S]*?</li>', body):
        href_m = re.search(r'<a[^>]*href="(https?://[^"]+)"', block)
        title_m = re.search(r'<h2[^>]*>[\s\S]*?<a[^>]*>(.*?)</a>[\s\S]*?</h2>', block)
        sn_m = re.search(r"<p[^>]*>([\s\S]*?)</p>", block)
        if not href_m:
            continue
        s = {"url": href_m.group(1)}
        if title_m:
            s["title"] = strip_tags(title_m.group(1))
        if sn_m:
            s["snippet"] = strip_tags(sn_m.group(1))
        sources.append(s)
    return unique_sources(sources, max_results)


def search_searxng(query, max_results, tr, deadline):
    errors = []
    for base in SEARXNG_INSTANCES:
        try:
            params = {"q": query, "format": "json"}
            if tr and tr.get("days"):
                params["time_range"] = SEARXNG_TIME[approximate_time_range(tr["days"])]
            text = http_request(f"{base}/search?{urllib.parse.urlencode(params)}",
                                timeout=min(8, deadline), headers={"Accept": "application/json"})
            data = json.loads(text)
            results = data.get("results")
            if not isinstance(results, list):
                errors.append(f"{base}: invalid JSON")
                continue
            sources = [{"url": r["url"],
                        **({"title": str(r["title"])} if r.get("title") else {}),
                        **({"snippet": str(r["content"])} if r.get("content") else {})}
                       for r in results if r.get("url")]
            if sources:
                return unique_sources(sources, max_results)
            errors.append(f"{base}: 0 results")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{base}: {e}")
    detail = ", ".join(errors)[:300] if errors else "no instances configured"
    raise EngineError(f"all SearXNG instances failed: {detail}")


def search_anysearch(query, max_results, tr, deadline):
    data = http_json(ANYSEARCH_URL, min(12, deadline),
                     {"query": query, "max_results": max_results})
    if data.get("code") != 0:
        raise EngineError(f"AnySearch API error: {data.get('message', data.get('code'))}")
    results = (data.get("data") or {}).get("results") or []
    return unique_sources([
        {"url": r["url"],
         **({"title": str(r["title"])} if r.get("title") else {}),
         **({"snippet": str(r["snippet"])[:300]} if r.get("snippet") else {})}
        for r in results if r.get("url")], max_results)


# ---------- 付费/可免 Key 引擎 ----------

def search_exa(query, max_results, tr, deadline):
    key = os.environ.get("EXA_API_KEY", "")
    if key:
        body = {"query": query, "type": "auto", "numResults": max_results,
                "contents": {"highlights": {"highlightsPerUrl": 1}}}
        if tr:
            body["startPublishedDate"] = tr.get("after") or iso_days_ago(tr.get("days", 7))
        data = http_json(EXA_URL, min(15, deadline), body,
                         {"Authorization": f"Bearer {key}", "Accept": "application/json"})
        sources = []
        for r in data.get("results") or []:
            hl = [h for h in (r.get("highlights") or []) if h.strip()]
            if not hl or not r.get("url"):
                continue
            s = {"url": r["url"], "snippet": hl[0]}
            if r.get("title"):
                s["title"] = r["title"]
            if r.get("publishedDate"):
                s["publishedAt"] = r["publishedDate"]
            sources.append(s)
        return unique_sources(sources, max_results)
    # 无 key：免费 MCP 通道
    text = mcp_call(EXA_MCP_URL, "web_search_exa",
                    {"query": query, "numResults": max_results}, min(20, deadline))
    return parse_title_url_blocks(text, max_results)


def search_tavily(query, max_results, tr, deadline):
    key = os.environ.get("TAVILY_API_KEY", "")
    body = {"query": query, "max_results": min(max_results, 20), "search_depth": "basic"}
    if tr and tr.get("days"):
        body["time_range"] = approximate_time_range(tr["days"])
    headers = ({"Authorization": f"Bearer {key}"} if key
               else {"x-tavily-access-mode": "keyless"})  # 无 key 走免费匿名额度
    data = http_json(TAVILY_URL, min(15, deadline), body, headers)
    return unique_sources([
        {"url": r["url"],
         **({"title": str(r["title"])} if r.get("title") else {}),
         **({"snippet": str(r["content"])[:300]} if r.get("content") else {})}
        for r in data.get("results") or [] if r.get("url")], max_results)


def search_keenable(query, max_results, tr, deadline):
    key = os.environ.get("KEENABLE_API_KEY", "")
    if key:
        body = {"query": query, "mode": "realtime"}
        if tr:
            body["published_after"] = tr.get("after") or format_keenable_relative(tr.get("days", 7))
        data = http_json(KEENABLE_URL, min(20, deadline), body,
                         {"X-API-Key": key, "Accept": "application/json"})
        return unique_sources([
            {"url": r["url"],
             **({"title": str(r["title"])} if r.get("title") else {}),
             **({"snippet": str(r.get("snippet") or r.get("description"))[:300]}
                if (r.get("snippet") or r.get("description")) else {}),
             **({"publishedAt": str(r["published_at"])} if r.get("published_at") else {})}
            for r in data.get("results") or [] if r.get("url")], max_results)
    # 无 key：免费 MCP 通道
    arguments = {"query": query}
    if tr:
        arguments["published_after"] = tr.get("after") or format_keenable_relative(tr.get("days", 7))
    text = mcp_call(KEENABLE_MCP_URL, "search_web_pages", arguments, min(25, deadline))
    return parse_title_url_blocks(text, max_results)


def search_perplexity(query, max_results, tr, deadline):
    key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not key:
        raise EngineError("Perplexity requires PERPLEXITY_API_KEY")
    data = http_json(PERPLEXITY_URL, min(20, deadline),
                     {"model": "sonar", "max_tokens": 1024,
                      "messages": [{"role": "user", "content": query}]},
                     {"Authorization": f"Bearer {key}", "Accept": "application/json"})
    answer = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    sources = [{"url": u, **({"snippet": answer[:200]} if answer else {})}
               for u in data.get("citations") or []]
    return unique_sources(sources, max_results), answer


def search_deepseek_official(query, max_results, tr, deadline):
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        raise EngineError("DeepSeek requires DEEPSEEK_API_KEY")
    data = http_json(DEEPSEEK_URL, min(20, deadline),
                     {"model": "deepseek-v4-flash", "max_tokens": 4096,
                      "messages": [{"role": "user", "content": [
                          {"type": "text",
                           "text": f"Perform a web search for the query: {query}"}]}],
                      "tools": [{"type": "web_search_20250305",
                                 "name": "web_search", "max_uses": 1}]},
                     {"x-api-key": key, "Authorization": f"Bearer {key}",
                      "anthropic-version": "2023-06-01", "Accept": "application/json"})
    blocks = data.get("content") or []
    snippets = {}
    answer_parts = []
    for block in blocks:
        if block.get("type") == "text":
            answer_parts.append(block.get("text", ""))
            for cite in block.get("citations") or []:
                if cite.get("url") and cite.get("cited_text") and cite["url"] not in snippets:
                    snippets[cite["url"]] = cite["cited_text"]
    sources = []
    for block in blocks:
        if block.get("type") != "web_search_tool_result":
            continue
        for item in block.get("content") or []:
            if item.get("type") != "web_search_result" or not item.get("url"):
                continue
            if any(s["url"] == item["url"] for s in sources):
                continue
            s = {"url": item["url"]}
            if item.get("title"):
                s["title"] = item["title"]
            if snippets.get(item["url"]):
                s["snippet"] = snippets[item["url"]]
            if item.get("page_age"):
                s["publishedAt"] = item["page_age"]
            sources.append(s)
    return unique_sources(sources, max_results), "\n".join(p for p in answer_parts if p)


ENGINE_FUNCS = {
    "ddg": search_ddg_html,
    "ddg-lite": search_ddg_lite,
    "bing": search_bing,
    "searxng": search_searxng,
    "anysearch": search_anysearch,
    "exa": search_exa,
    "tavily": search_tavily,
    "keenable": search_keenable,
    "perplexity": search_perplexity,
    "deepseek-official": search_deepseek_official,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", "-q", required=True)
    ap.add_argument("--max", type=int, default=5)
    ap.add_argument("--engine", "-e", default="bing", choices=ALL_ENGINES,
                    help="首选引擎（默认 bing，与 DSH 一致）")
    ap.add_argument("--time", default="",
                    help="时间过滤：day/week/month/year、12h/3d/2mo/1y、YYYY-MM-DD")
    args = ap.parse_args()

    try:
        tr = parse_time_range(args.time)
    except EngineError as e:
        json.dump({"error": str(e)}, sys.stdout, ensure_ascii=False)
        sys.exit(1)
    preferred = args.engine

    # 构建降级链（与 DSH free-search 一致）
    preferred_skipped_reason = None
    if tr:
        preferred_first = [preferred] if preferred in TIME_ENGINES else []
        other_time = [e for e in TIME_ENGINES if e != preferred]
        no_time = [e for e in PAID_ENGINES + FREE_ENGINES
                   if e not in TIME_ENGINES and e != preferred]
        chain = preferred_first + other_time + no_time
        if preferred not in TIME_ENGINES:
            preferred_skipped_reason = "time-filter"
    else:
        chain = ([preferred] + [e for e in PAID_ENGINES if e != preferred]
                 + [e for e in FREE_ENGINES if e != preferred])

    deadline_at = time.monotonic() + BUDGET_S
    last_error, preferred_failure = None, None

    for engine in chain:
        remaining = deadline_at - time.monotonic()
        if remaining <= 0:
            last_error = EngineError(f"search timed out after {BUDGET_S}s")
            break
        try:
            result = ENGINE_FUNCS[engine](args.query, args.max, tr, remaining)
            answer = None
            if isinstance(result, tuple):  # perplexity / deepseek-official 带 answer
                sources, answer = result
            else:
                sources = result
            if not sources:
                raise EngineError(f'engine "{engine}" returned 0 results')

            # 统一清洗 snippet（与 DSH 一致：链出口处处理）
            for s in sources:
                if s.get("snippet"):
                    s["snippet"] = clean_snippet(s["snippet"])

            out = {"query": args.query, "engine": engine, "results": sources}
            if args.time:
                out["time_filter"] = args.time
            if answer:
                out["answer"] = answer
            # Note：区分"首选不支持时间过滤被跳过"与"首选真实失败"
            if engine != preferred:
                if preferred_skipped_reason == "time-filter":
                    out["note"] = (f"Note: {preferred} does not support time filtering "
                                   f"(timeRange={args.time}), using {engine}.")
                elif preferred_failure:
                    out["note"] = (f"Note: {preferred} unavailable or failed "
                                   f"({preferred_failure}), using {engine}.")
                else:
                    out["note"] = f"Note: {preferred} unavailable or failed, using {engine}."
            json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
            print()
            return
        except Exception as e:  # noqa: BLE001
            last_error = e
            if engine == preferred:
                preferred_failure = str(e)[:150]

    json.dump({"query": args.query, "engine": None, "results": [],
               "error": str(last_error or "all search engines failed")},
              sys.stdout, ensure_ascii=False)
    print()
    sys.exit(1)


if __name__ == "__main__":
    main()
