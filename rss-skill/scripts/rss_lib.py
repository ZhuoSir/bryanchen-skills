#!/usr/bin/env python3
"""rss-skill 共享库：配置加载、Feed 抓取解析（JSON Feed/RSS/Atom）、SQLite+FTS5 存储。

零依赖（Python 3 标准库）。被同目录其他脚本 import，不直接运行。
"""
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"

CONFIG_PATH = os.environ.get(
    "RSS_SKILL_CONFIG",
    os.path.expanduser("~/.config/rss-skill/config.json"),
)
DEFAULT_DB = "/tmp/rss-skill/articles.db"  # 索引只是缓存，丢失后重新 sync 即可

CST = timezone(timedelta(hours=8))  # 展示用东八区


# ---------------------------------------------------------------- 配置

def load_config(require_base=False):
    """读取配置文件。返回 dict；文件不存在时返回空配置。

    配置示例：
    {
      "base_url": "http://127.0.0.1:4000",   // wewe-rss 服务地址
      "db_path": "...",                        // 可选，默认 /tmp/rss-skill/articles.db（缓存，可重建）
      "feeds": [                               // 可选，额外的通用 RSS/Atom/JSON Feed 源
        {"name": "量子位", "url": "https://www.qbitai.com/feed"}
      ]
    }
    """
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    cfg.setdefault("base_url", os.environ.get("RSS_SKILL_BASE_URL", ""))
    cfg.setdefault("db_path", os.environ.get("RSS_SKILL_DB", DEFAULT_DB))
    cfg["db_path"] = os.path.expanduser(cfg["db_path"])
    cfg.setdefault("feeds", [])
    if require_base and not cfg["base_url"]:
        raise SystemExit(json.dumps({
            "ok": False,
            "error": "未配置 wewe-rss 服务地址。请创建配置文件 "
                     f"{CONFIG_PATH}（参考 config.example.json），"
                     "或设置环境变量 RSS_SKILL_BASE_URL。",
        }, ensure_ascii=False))
    if cfg["base_url"]:
        cfg["base_url"] = cfg["base_url"].rstrip("/")
    return cfg


# ---------------------------------------------------------------- 网络

def fetch(url, tries=3, timeout=60):
    """GET 抓取，返回 bytes。带重试。"""
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < tries - 1:
                time.sleep(2 * (attempt + 1))
    raise last


def build_url(base, path, **params):
    """拼接 URL，忽略空值参数。"""
    q = {k: v for k, v in params.items() if v not in (None, "")}
    url = base + path
    if q:
        url += "?" + urllib.parse.urlencode(q)
    return url


# ---------------------------------------------------------------- wewe-rss API

def wewe_list_feeds(base_url):
    """GET /feeds → [{id, name, intro, cover, syncTime, updateTime}]"""
    data = fetch(base_url + "/feeds", timeout=30)
    return json.loads(data.decode("utf-8"))


def wewe_fetch_page(base_url, feed_id=None, page=1, limit=30, fulltext=True):
    """GET /feeds/{all|<id>}.json 拉一页文章，返回 (feed_title, [article...])。

    wewe-rss JSON Feed 字段：id/url/title/content_html/date_published/image/authors。
    """
    fid = feed_id or "all"
    url = build_url(base_url, f"/feeds/{fid}.json",
                    limit=limit, page=page,
                    mode="fulltext" if fulltext else None)
    data = json.loads(fetch(url).decode("utf-8"))
    return data.get("title", fid), data.get("items", [])


def wewe_trigger_update(base_url, feed_id):
    """触发某个订阅源立即更新（服务端异步执行，约 30s+）。"""
    url = build_url(base_url, f"/feeds/{feed_id}.json", limit=1, update="true")
    fetch(url, tries=1, timeout=30)
    return True


# ---------------------------------------------------------------- Feed 解析（通用）

def parse_date(raw):
    if not raw:
        return None
    raw = str(raw).strip()
    try:
        dt = parsedate_to_datetime(raw)  # RSS pubDate (RFC 822)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        pass
    try:  # ISO 8601 (Atom / JSON Feed)
        dt = datetime.fromisoformat(re.sub(r"Z$", "+00:00", raw))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def _extract_js_content(s):
    """提取 <div id="js_content"> 容器内部 HTML；找不到或为空返回 None。"""
    m = re.search(r"<div[^>]*\bid\s*=\s*[\"']js_content[\"'][^>]*>", s)
    if not m:
        return None
    depth = 0
    end = None
    for t in re.finditer(r"<(/?)div\b[^>]*?>", s[m.start():]):
        depth += -1 if t.group(1) else 1
        if depth == 0:
            end = m.start() + t.start()
            break
    inner = s[m.end():end] if end else s[m.end():]
    return inner if inner.strip() else None


def clean_content_html(html):
    """清洗正文 HTML：

    1. 若为整页文档（wewe-rss 全文模式返回的是公众号完整页面，含 head/脚本/
       base64，单篇可达 3~4MB），优先提取 <div id="js_content"> 正文容器；
       js_content 为空（JS 渲染页面）时退化为只保留 <body>；
    2. 删除 script/style/iframe 块与 base64 data URI，只保留可读正文结构。
    """
    if not html:
        return ""
    s = html
    if re.match(r"(?i)\s*(<!doctype|<html)", s):
        s = _extract_js_content(s) or _extract_body(s)
    s = re.sub(r"(?is)<(script|style|iframe|noscript|svg)\b[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?is)<(script|link|meta)\b[^>]*?/?>", " ", s)  # 自闭合/残缺标签
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r'(?i)(src|data-src)\s*=\s*["\']data:[^"\']*["\']',
               r'\1="(base64图片已省略)"', s)
    return s.strip()


def _extract_body(s):
    """整页兜底：只保留 <body>；没有 body 则砍掉 head。"""
    mb = re.search(r"(?is)<body[^>]*>(.*)</body>", s)
    if mb:
        return mb.group(1)
    return re.sub(r"(?is)^.*?</head>", " ", s)


def html_to_text(html):
    """粗暴 HTML → 纯文本：去脚本/样式/标签，压缩空白。"""
    if not html:
        return ""
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|h[1-6]|tr|blockquote|section)>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                 ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        s = s.replace(a, b)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()


def parse_json_feed(data, source_name, feed_name=None):
    """解析 JSON Feed 1.x（wewe-rss 的 .json 输出即此格式）。

    data 可以是 bytes/str/dict；feed_name 可显式指定（wewe 单源接口不返回源名时用）。
    """
    if isinstance(data, dict):
        doc = data
    else:
        doc = json.loads(data.decode("utf-8") if isinstance(data, bytes) else data)
    feed_title = feed_name or doc.get("title") or source_name
    articles = []
    for it in doc.get("items", []):
        url = it.get("url") or it.get("external_url") or ""
        uid = str(it.get("id") or url)
        html = clean_content_html(it.get("content_html") or "")
        text = it.get("content_text") or html_to_text(html)
        authors = it.get("authors") or []
        author = authors[0].get("name") if authors else it.get("author", {}).get("name") \
            if isinstance(it.get("author"), dict) else None
        dt = parse_date(it.get("date_published") or it.get("date_modified"))
        articles.append({
            "guid": uid, "url": url, "title": (it.get("title") or "").strip(),
            "author": author, "published": dt.isoformat() if dt else None,
            "content_html": html, "content_text": text,
            "feed_name": feed_title, "source": source_name,
        })
    return feed_title, articles


def parse_xml_feed(data, source_name):
    """解析 RSS 2.0 / Atom。"""
    root = ET.fromstring(data)
    articles = []
    if root.tag == f"{ATOM}feed":
        feed_title = root.findtext(f"{ATOM}title") or source_name
        for e in root.findall(f"{ATOM}entry"):
            link_el = e.find(f"{ATOM}link[@rel='alternate']")
            if link_el is None:
                link_el = e.find(f"{ATOM}link")
            url = link_el.get("href") if link_el is not None else ""
            html = clean_content_html(
                (e.findtext(f"{ATOM}content")
                 or e.findtext(f"{ATOM}summary") or ""))
            dt = parse_date(e.findtext(f"{ATOM}published")
                            or e.findtext(f"{ATOM}updated"))
            articles.append({
                "guid": e.findtext(f"{ATOM}id") or url, "url": url,
                "title": (e.findtext(f"{ATOM}title") or "").strip(),
                "author": (e.findtext(f"{ATOM}author/{ATOM}name")),
                "published": dt.isoformat() if dt else None,
                "content_html": html, "content_text": html_to_text(html),
                "feed_name": feed_title, "source": source_name,
            })
    else:  # RSS 2.0
        feed_title = root.findtext("./channel/title") or source_name
        for it in root.iter("item"):
            url = (it.findtext("link") or "").strip()
            html = clean_content_html(
                it.findtext(f"{CONTENT_NS}encoded") or it.findtext("description") or "")
            dt = parse_date(it.findtext("pubDate"))
            articles.append({
                "guid": it.findtext("guid") or url, "url": url,
                "title": (it.findtext("title") or "").strip(),
                "author": it.findtext("author") or it.findtext(
                    "{http://purl.org/dc/elements/1.1/}creator"),
                "published": dt.isoformat() if dt else None,
                "content_html": html, "content_text": html_to_text(html),
                "feed_name": feed_title, "source": source_name,
            })
    return feed_title, articles


def parse_feed(data, source_name):
    """自动识别 JSON Feed / RSS / Atom。"""
    head = data[:200].lstrip() if isinstance(data, bytes) else data[:200].lstrip()
    if head.startswith(b"{") if isinstance(head, bytes) else head.startswith("{"):
        return parse_json_feed(data, source_name)
    return parse_xml_feed(data, source_name)


# ---------------------------------------------------------------- 存储

# FTS5 内置 unicode61 分词器无法切分中文（"肝癌AI模型" 整串算一个词），
# 这里自己做 bigram 切分：CJK 连续串切成重叠二字组，拉丁/数字串保留整词，
# 空格连接后写入 FTS 表；查询侧用同样规则切分并组短语查询，实现中文全文搜索。
CJK_FULL = re.compile(
    r"[一-鿿㐀-䶿豈-﫿]+$")
TOKEN_RE = re.compile(
    r"[一-鿿㐀-䶿豈-﫿]+|[A-Za-z0-9_]+")


def fts_tokens(text):
    """文本 → FTS 词元列表（CJK bigram + 拉丁整词）。"""
    tokens = []
    for m in TOKEN_RE.finditer(text or ""):
        s = m.group(0)
        if CJK_FULL.match(s):
            if len(s) == 1:
                tokens.append(s)
            else:
                tokens.extend(s[i:i + 2] for i in range(len(s) - 1))
        else:
            tokens.append(s)
    return tokens


def fts_index_text(text):
    return " ".join(fts_tokens(text))


def fts_query(raw):
    """用户输入 → FTS5 查询串。

    空格分隔的每段独立组短语（段内保持顺序/相邻），段间 AND。
    用户手写 FTS 语法（含引号或列过滤 "title:"）时原样透传。
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    if '"' in raw or ":" in raw:
        return raw
    parts = []
    for seg in raw.split():
        toks = [t.replace('"', "") for t in fts_tokens(seg)]
        if toks:
            parts.append('"' + " ".join(toks) + '"')
    return " AND ".join(parts) if parts else None


SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guid TEXT NOT NULL,
    url TEXT,
    title TEXT,
    author TEXT,
    published TEXT,
    feed_name TEXT,
    source TEXT,          -- wewe:<feed_id> 或 custom:<name>
    content_html TEXT,
    content_text TEXT,
    fetched_at TEXT,
    UNIQUE(source, guid)
);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published DESC);
CREATE INDEX IF NOT EXISTS idx_articles_feed ON articles(feed_name);
"""


def open_db(cfg=None):
    cfg = cfg or load_config()
    db_path = cfg["db_path"]
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.row_factory = sqlite3.Row
    # FTS5 不可用（极少数精简 Python 构建）时降级为 LIKE 搜索
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts "
            "USING fts5(title, content, feed_name)"
        )
        conn.execute("SELECT 1 FROM articles_fts LIMIT 0")
        return conn, True
    except sqlite3.Error:
        return conn, False


def _fts_replace(conn, rowid, title, content_text, feed_name):
    """重建某行的 FTS 索引（先删后插）。"""
    conn.execute("DELETE FROM articles_fts WHERE rowid=?", (rowid,))
    conn.execute(
        "INSERT INTO articles_fts(rowid, title, content, feed_name) VALUES (?,?,?,?)",
        (rowid, fts_index_text(title), fts_index_text(content_text),
         fts_index_text(feed_name)))


def upsert_articles(conn, articles, source, has_fts=True):
    """按 (source, guid) 去重入库并维护 FTS 索引。返回 (新增数, 更新数)。"""
    now = datetime.now(timezone.utc).isoformat()
    added = updated = 0
    for a in articles:
        guid = str(a.get("guid") or a.get("url") or a.get("title"))
        if not guid:
            continue
        row = conn.execute(
            "SELECT id, content_text FROM articles WHERE source=? AND guid=?",
            (source, guid)).fetchone()
        if row is None:
            cur = conn.execute(
                "INSERT INTO articles(guid,url,title,author,published,feed_name,"
                "source,content_html,content_text,fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (guid, a.get("url"), a.get("title"), a.get("author"),
                 a.get("published"), a.get("feed_name"), source,
                 a.get("content_html"), a.get("content_text"), now))
            if has_fts:
                _fts_replace(conn, cur.lastrowid, a.get("title"),
                             a.get("content_text"), a.get("feed_name"))
            added += 1
        else:
            # 已存在且已有正文、本次又没拿到正文 → 跳过，避免把全文覆盖成空
            if row["content_text"] and not a.get("content_text"):
                continue
            conn.execute(
                "UPDATE articles SET url=?,title=?,author=?,published=?,feed_name=?,"
                "content_html=?,content_text=?,fetched_at=? WHERE id=?",
                (a.get("url"), a.get("title"), a.get("author"),
                 a.get("published"), a.get("feed_name"), a.get("content_html"),
                 a.get("content_text"), now, row["id"]))
            if has_fts:
                _fts_replace(conn, row["id"], a.get("title"),
                             a.get("content_text"), a.get("feed_name"))
            updated += 1
    conn.commit()
    return added, updated


def make_snippet(title, content, query_raw, width=80):
    """从标题/正文里定位查询词并截取上下文，命中处用【】标出。"""
    text = f"{title or ''}。{content or ''}"
    terms = [t for seg in (query_raw or "").split()
             for t in ([seg] if len(seg) <= 4 else [seg, *fts_tokens(seg)])
             if t]
    pos, hit = -1, ""
    low = text.lower()
    for t in terms:
        i = low.find(t.lower())
        if i >= 0 and (pos < 0 or i < pos):
            pos, hit = i, t
    if pos < 0:
        return re.sub(r"\s+", " ", (content or title or ""))[: width * 2]
    start = max(0, pos - width // 2)
    end = min(len(text), pos + len(hit) + width)
    frag = text[start:end]
    frag = frag.replace(hit, f"【{hit}】", 1)
    return ("…" if start > 0 else "") + frag + ("…" if end < len(text) else "")


def out(obj):
    """统一 JSON 输出。"""
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2, default=str)
    print()


def fail(msg, **extra):
    out({"ok": False, "error": msg, **extra})
    sys.exit(1)


def fmt_local(iso):
    """UTC ISO → 东八区可读时间。"""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
        return dt.astimezone(CST).strftime("%Y-%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        return iso
