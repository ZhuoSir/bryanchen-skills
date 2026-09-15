#!/usr/bin/env python3
"""web-search: 多引擎联网搜索（Python 标准库零依赖），完整复刻 DSH free-search 插件逻辑。

引擎与降级链（与 DSH web_search 工具一致）：
  首选引擎 → 其他付费引擎（exa/tavily/keenable 无 Key 也走免费通道）→ 免费引擎（bing/anysearch/ddg/ddg-lite/searxng）
- 带 --time 时，支持时间过滤的引擎（tavily/exa/keenable/searxng/ddg/ddg-lite）排在前面；
  首选引擎不支持时间过滤则直接跳过（Note 说明 "does not support time filtering"，而非"失败"）
- 整条链共享 30s 总预算；首选引擎失败原因记入 Note
- API Key 从环境变量读取：EXA_API_KEY / TAVILY_API_KEY / KEENABLE_API_KEY / PERPLEXITY_API_KEY / DEEPSEEK_API_KEY
- 首选引擎可用环境变量 WEB_SEARCH_ENGINE 覆盖（默认 exa）
- query 含 site: 时，实测忽略该操作符的引擎（bing）会被跳过并记入 Note，避免静默返回其他站点的结果

用法:
    python3 search.py --query "关键词" [--max 5] [--engine exa] [--time day|week|month|year|12h|3d|2mo|1y|YYYY-MM-DD]
                      [--strict] [--list-engines]
输出:
    stdout JSON: {"query", "engine", "note"?, "warning"?, "answer"?, "self_check"?,
                  "results": [{title, url, snippet, publishedAt?}]}

为什么需要结果自检：
  降级链只在「失败或 0 结果」时才往后走，因此一个**能返回结果、但结果与查询语义无关**的引擎
  永远不会被跳过——这是最危险的形态（失败可被发现，静默错配不能）。实测默认引擎 bing 搜
  「高升控股股份有限公司 首席技术官 CTO」，返回的是足球运动员「高升」的百科页与「高升」的
  汉语词典释义，而 engine 字段照报成功、无 note、无 error。
  实测同一检索词下 exa / tavily / keenable 均准确命中；`site:` 定向 Bing 实测完全忽略
  （0/3 条来自目标域），exa / tavily / keenable 3/3 遵守。
  为此本版本做三件事：
    1. 默认引擎 bing → exa（可用环境变量 WEB_SEARCH_ENGINE 覆盖）
    2. 引入 ENGINE_TRAITS 引擎画像（质量档位 + 是否遵守 site:），按实测维护
    3. 结果自检 self_check（site: 是否真生效、结果与查询有无词面交集），不通过时输出 warning
  判定与处理规则见 SKILL.md「引擎画像与结果自检」。
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

# ---------- 引擎画像（ENGINE_TRAITS） ----------
# 全部按实测维护，不要凭记忆改。改动前请先按 SKILL.md「引擎画像与结果自检」的方法复测。
#
#   tier 质量档位：
#     precision  语义/精确匹配引擎。适合实体级检索（企业名、人名、site: 定向）。
#     standard   通用搜索引擎，可用，但不保证对实体名做精确匹配。
#     broad      关键词抓取式。实测**会把实体名当普通词处理**：搜「高升控股股份有限公司 首席
#                技术官 CTO」返回足球运动员「高升」的百科页与「高升」的汉语词典释义。
#                因此它的结果不能直接作为实体级事实依据。
#   site: 三态（query 含 site:domain 时该引擎是否真的过滤到该域）：
#     True   实测遵守（结果落在目标域）
#     False  实测忽略（结果来自任意站点）
#     None   未验证 —— 保守处理：只有 --strict 才会要求 site 必须为 True
ENGINE_TRAITS = {
    "exa":               {"tier": "precision", "site": True},
    "tavily":            {"tier": "precision", "site": True},
    "keenable":          {"tier": "precision", "site": True},
    "perplexity":        {"tier": "precision", "site": None},
    "deepseek-official": {"tier": "precision", "site": None},
    "anysearch":         {"tier": "standard",  "site": True},
    "searxng":           {"tier": "standard",  "site": None},
    "ddg":               {"tier": "standard",  "site": None},
    "ddg-lite":          {"tier": "standard",  "site": None},
    "bing":              {"tier": "broad",     "site": False},
}

# 默认引擎：exa。DSH free-search 插件默认 bing，本 skill 有意**偏离**该默认值——
# bing 的静默错配（见文件头说明）会让"看起来成功"的假结果直接进入下游结论。
# 国内网络可设 WEB_SEARCH_ENGINE 覆盖为 tavily/keenable 等。
_ENV_ENGINE = (os.environ.get("WEB_SEARCH_ENGINE") or "").strip().lower()
DEFAULT_ENGINE = _ENV_ENGINE if _ENV_ENGINE in ALL_ENGINES else "exa"

SITE_RE = re.compile(r"\bsite:\s*([^\s]+)", re.I)
# 词面自检时不参与判定的通用词（查询里出现它们不构成"命中了查询"的证据）
QUERY_STOPWORDS = {"the", "a", "an", "of", "and", "or", "for", "in", "on", "to",
                   "最新", "相关", "消息", "新闻", "情况", "介绍"}

BUDGET_S = 30  # 整条引擎链总预算（与 DSH 一致）
MIN_RESPONSE = 500

# 抓 HTML 的引擎（内部多实例 / 多重重试）会独自吃满整条链预算，必须单独设硬上限：
# 实测 ddg 39.5s、searxng 48.4s（都超过 30s 总预算），会把后面的 precision 引擎饿死。
# 对照：exa 3.4s / tavily 2.2s / keenable 4.8s / anysearch 1.6s / bing 0.8s。
SCRAPE_ENGINES = {"bing", "ddg", "ddg-lite", "searxng"}
SCRAPE_BUDGET_S = 8.0

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


def http_request(url, timeout=12, method="GET", body=None, headers=None, tries=1, interval=1.5,
                 budget=None):
    """带重试的 HTTP 请求，返回文本。重试仅用于 GET（HTML 抓取）。

    budget：本次调用允许占用的**总**秒数（含全部重试）。不传则只按单次 timeout 计。

    为什么需要 budget：重试各自计时，所以 tries=3 × timeout=12s ≈ 36s。实测 ddg 在不可达
    网络下耗时 39.5s、searxng 48.4s，**独自吃光整条链的 30s 预算**并把后面的 exa/tavily
    饿死，最终表现为"全网搜索失败"——而实际只是第一个引擎不可达。
    """
    hdrs = {"User-Agent": USER_AGENT, "Accept-Language": ACCEPT_LANG}
    if headers:
        hdrs.update(headers)
    data = json.dumps(body).encode() if body is not None else None
    last = None
    started = time.monotonic()
    for attempt in range(tries):
        if budget is not None:
            left = budget - (time.monotonic() - started)
            if left <= 0.5:
                raise last or EngineError(
                    f"budget {budget:.0f}s exhausted ({url.split('/')[2]})")
            timeout = min(timeout, left)
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


# ---------- 结果自检 ----------
# 目的：识别「引擎成功返回、但结果与查询无关」的静默错配。
# 设计原则是**保守优先（宁漏不误伤）**：只判定证据无歧义的情形，模糊地带交给人/上层 Agent 判断。

def extract_site_domains(query):
    """取出 query 里的 site: 目标域（支持 site:a.com、site:https://a.com/x）。"""
    out = []
    for m in SITE_RE.finditer(query or ""):
        d = m.group(1).strip().strip("\"'").lower()
        d = re.sub(r"^[a-z][a-z0-9+.-]*://", "", d).split("/")[0].split(":")[0].lstrip(".")
        if d:
            out.append(d)
    return out


def check_site_filter(query, sources):
    """query 含 site: 时校验该过滤是否真的生效；不含 site: 返回 None。

    这是确定性判定（比对结果 URL 的 host），因此可作硬门禁：
    bing 实测忽略 site:，会静默返回任意站点的结果，在这里必然暴露为 honored=False。
    """
    domains = extract_site_domains(query)
    if not domains:
        return None
    matched = 0
    for s in sources:
        host = (urllib.parse.urlsplit(s.get("url") or "").netloc or "").lower().split(":")[0]
        if any(host == d or host.endswith("." + d) for d in domains):
            matched += 1
    return {"domains": domains, "matched": matched, "total": len(sources),
            "honored": matched > 0}


def _cjk_bigrams(text):
    out = set()
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text or ""):
        for i in range(len(run) - 1):
            out.add(run[i:i + 2])
    return out


def query_terms(query):
    """把 query 拆成用于词面校验的项（去掉 site: 操作符与布尔词）。"""
    q = SITE_RE.sub(" ", query or "")
    q = re.sub(r"\b(?:OR|AND|NOT)\b", " ", q)
    terms, seen = [], set()
    for t in re.split(r"[\s,，、;；/|\\()（）\[\]【】\"'“”]+", q):
        t = t.strip(" .,!?:;、。，！？")
        tl = t.lower()
        if len(t) < 2 or tl in QUERY_STOPWORDS or tl in seen:
            continue
        seen.add(tl)
        terms.append(t)
    return terms


def check_relevance(query, sources):
    """词面自检：query 的关键词在结果里到底出现了没有。

    只判「完全无交集」这一个无歧义情形 —— 实测 bing 的错配结果（足球运动员百科 / 汉语词典）
    与查询 0/3 词面重合，而正确结果至少命中 1 项，判别清晰。
    CJK 长词按**整词**计，所以「企业全称 vs 简称」这类部分命中不会被误判为失败。
    coverage（CJK bigram 覆盖率）只作参考、不参与判定：实测错配 ≈0.08、正确 ≈0.25，
    两者太近，做门禁会误伤，故仅作提示。
    """
    terms = query_terms(query)
    if len(terms) < 2:
        return None  # 单词查询没有判别力，不判定
    blob = " ".join(f"{s.get('title', '')} {s.get('snippet', '')}" for s in sources).lower()
    matched = [t for t in terms if t.lower() in blob]
    qb, bb = _cjk_bigrams(query), _cjk_bigrams(blob)
    return {"terms": len(terms), "matched": len(matched),
            "level": "ok" if matched else "none",
            "coverage": round(len(qb & bb) / len(qb), 2) if qb else None,
            "missing": [t for t in terms if t.lower() not in blob][:5]}


# ---------- 免费引擎 ----------

def search_ddg_html(query, max_results, tr, deadline):
    params = {"q": query}
    if tr and tr.get("days"):
        params["df"] = DDG_DF[approximate_time_range(tr["days"])]
    body = http_request(f"{DDG_HTML_URL}?{urllib.parse.urlencode(params)}",
                        timeout=min(12, deadline), tries=3, budget=deadline)
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
                        timeout=min(12, deadline), tries=3, budget=deadline)
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
                        timeout=min(12, deadline), tries=3, budget=deadline)
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
    started = time.monotonic()
    for base in SEARXNG_INSTANCES:
        # 6 个实例各 8s 上限 = 最多 48s，会把整条链吃光 —— 按总预算截断
        left = deadline - (time.monotonic() - started)
        if left <= 0.5:
            errors.append("实例轮询预算耗尽")
            break
        try:
            params = {"q": query, "format": "json"}
            if tr and tr.get("days"):
                params["time_range"] = SEARXNG_TIME[approximate_time_range(tr["days"])]
            text = http_request(f"{base}/search?{urllib.parse.urlencode(params)}",
                                timeout=min(8, left), headers={"Accept": "application/json"})
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
    ap.add_argument("--query", "-q", default="",
                    help="搜索关键词（--list-engines 时可省略）")
    ap.add_argument("--max", type=int, default=5)
    ap.add_argument("--engine", "-e", default=DEFAULT_ENGINE, choices=ALL_ENGINES,
                    help=f"首选引擎（默认 {DEFAULT_ENGINE}；可用环境变量 WEB_SEARCH_ENGINE 覆盖）")
    ap.add_argument("--time", default="",
                    help="时间过滤：day/week/month/year、12h/3d/2mo/1y、YYYY-MM-DD")
    ap.add_argument("--strict", action="store_true",
                    help="精度优先：排除 broad 档引擎（bing）；query 含 site: 时只用实测遵守 site: 的引擎；"
                         "自检不通过（site: 未生效 / 与查询无词面交集）视为该引擎失败并继续降级")
    ap.add_argument("--list-engines", action="store_true",
                    help="打印引擎画像（质量档位 / site: 支持）后退出")
    args = ap.parse_args()

    if args.list_engines:
        json.dump({"default": DEFAULT_ENGINE, "traits": ENGINE_TRAITS,
                   "tiers": {t: [e for e in ALL_ENGINES
                                 if (ENGINE_TRAITS.get(e) or {}).get("tier") == t]
                             for t in ("precision", "standard", "broad")},
                   "time_engines": TIME_ENGINES},
                  sys.stdout, ensure_ascii=False, indent=2)
        print()
        return

    try:
        tr = parse_time_range(args.time)
    except EngineError as e:
        json.dump({"error": str(e)}, sys.stdout, ensure_ascii=False)
        sys.exit(1)

    if not args.query.strip():
        json.dump({"error": "--query/-q is required"}, sys.stdout, ensure_ascii=False)
        print()
        sys.exit(1)
    preferred = args.engine

    # ---- 构建降级链 ----
    site_domains = extract_site_domains(args.query)

    def eligible(engine):
        """按引擎画像决定是否允许该引擎进入本次降级链。"""
        traits = ENGINE_TRAITS.get(engine)
        if traits is None:
            # 画像缺失 = 质量未知：--strict 下按"失败关闭"处理，别让不明档位的引擎混进结果
            return not args.strict
        if site_domains:
            if traits.get("site") is False:
                return False   # 实测忽略 site: —— 会静默返回别站结果，任何模式都不用
            if args.strict and traits.get("site") is not True:
                return False   # 未验证是否遵守 site: —— 只在 --strict 下排除
        if args.strict and traits.get("tier") == "broad":
            return False
        return True

    skip_reasons = []
    if not eligible(preferred):
        pt = ENGINE_TRAITS.get(preferred) or {}
        if not pt:
            skip_reasons.append("no engine traits (unknown quality), excluded by --strict")
        if site_domains and pt.get("site") is False:
            skip_reasons.append(f"ignores site: operator (query asks for {','.join(site_domains)})")
        elif site_domains and args.strict and pt.get("site") is not True:
            skip_reasons.append("site: support unverified, excluded by --strict")
        if pt and args.strict and pt.get("tier") == "broad":
            skip_reasons.append("broad-tier engine excluded by --strict")

    cand = [preferred] + [e for e in PAID_ENGINES + FREE_ENGINES if e != preferred]
    cand = [e for e in cand if eligible(e)]

    if tr:
        # 支持时间过滤的引擎排前面；首选不支持则整体跳过（Note 说明是"跳过"而非"失败"）
        chain = ([e for e in cand if e in TIME_ENGINES]
                 + [e for e in cand if e not in TIME_ENGINES])
        if preferred in cand and preferred not in TIME_ENGINES:
            chain = [e for e in chain if e != preferred]
            skip_reasons.append(f"does not support time filtering (timeRange={args.time})")
    else:
        chain = cand

    if not chain:
        json.dump({"query": args.query, "engine": None, "results": [],
                   "error": "no eligible engine: " + "; ".join(skip_reasons or ["engine pool empty"])},
                  sys.stdout, ensure_ascii=False)
        print()
        sys.exit(1)

    deadline_at = time.monotonic() + BUDGET_S
    last_error, preferred_failure = None, None

    for engine in chain:
        remaining = deadline_at - time.monotonic()
        if remaining <= 0:
            last_error = EngineError(f"search timed out after {BUDGET_S}s")
            break
        try:
            # 抓 HTML 的引擎单独限时：否则一个不可达引擎会吃光整条链，把后面的引擎饿死
            slice_s = min(remaining, SCRAPE_BUDGET_S) if engine in SCRAPE_ENGINES else remaining
            result = ENGINE_FUNCS[engine](args.query, args.max, tr, slice_s)
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

            # ---- 结果自检（见文件头"为什么需要结果自检"）----
            check = {}
            site_info = check_site_filter(args.query, sources)
            if site_info:
                check["site_filter"] = site_info
            rel_info = check_relevance(args.query, sources)
            if rel_info:
                check["relevance"] = rel_info

            # --strict：自检不通过 = 该引擎结果不可用，继续降级（宁可无结果，不用错结果）
            if args.strict:
                if site_info and not site_info["honored"]:
                    raise EngineError(
                        f'engine "{engine}" ignored the site: operator '
                        f'(0/{site_info["total"]} results from {",".join(site_info["domains"])})')
                if rel_info and rel_info["level"] == "none":
                    raise EngineError(
                        f'engine "{engine}" returned results with no query-term overlap '
                        f'(0/{rel_info["terms"]})')

            out = {"query": args.query, "engine": engine, "results": sources}
            if args.time:
                out["time_filter"] = args.time
            if answer:
                out["answer"] = answer
            if check:
                out["self_check"] = check

            # warning：结果可用但不该无条件采信，供上层 Agent / SKILL.md 铁律处置
            warns = []
            if ENGINE_TRAITS.get(engine, {}).get("tier") == "broad":
                warns.append(f'引擎 "{engine}" 为 broad 档（实测会把实体名当普通词处理），'
                             f"实体级结论不可直接采信；建议 --strict 或 --engine exa/tavily")
            if site_info and not site_info["honored"]:
                warns.append(f'引擎 "{engine}" 未遵守 site: 过滤'
                             f'（{site_info["matched"]}/{site_info["total"]} 条来自 '
                             f'{",".join(site_info["domains"])}），结果可能来自其他站点')
            if rel_info and rel_info["level"] == "none":
                warns.append(f"结果与查询无词面交集（0/{rel_info['terms']}："
                             f"{'、'.join(rel_info['missing'])}），疑似语义错配，不得作为事实依据")
            if warns:
                out["warning"] = " | ".join(warns)

            # Note：区分"首选被画像/时间过滤规则跳过"与"首选真实失败"
            if engine != preferred:
                if skip_reasons:
                    out["note"] = (f"Note: {preferred} skipped ({'; '.join(skip_reasons)}), "
                                   f"using {engine}.")
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
