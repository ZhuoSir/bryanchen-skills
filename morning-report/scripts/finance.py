#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""财经数据源：A股大盘行情 + 财经要闻（纯标准库，零依赖，免 Key）。

行情（主源东方财富 push2 JSON，兜底新浪 hq.sinajs.cn）
  · 指数：上证 / 深证成指 / 创业板指 / 科创50 / 北证50 / 沪深300 —— 点位、涨跌额、涨跌幅、成交额
  · 两市成交额 = 沪市 + 深市
  · 行业板块涨/跌幅榜 TOP N
  · 涨跌家数（可选 --breadth，需逐页拉全市场，慢）

要闻（主源新浪财经滚动 JSON，兜底同花顺 today_list（GBK）→ 证券时报首页）
  · 输出 title / url / media / time，URL 均为原文链接

用法：
  python3 scripts/finance.py                          # 行情 + 要闻（默认）
  python3 scripts/finance.py --no-news                # 只要行情
  python3 scripts/finance.py --no-quotes              # 只要要闻
  python3 scripts/finance.py --news-limit 8 --sectors 5
  python3 scripts/finance.py --breadth                # 附加涨跌家数（约 56 次请求，~10s）
  python3 scripts/finance.py --json                   # 完整 JSON（默认即为 JSON）

输出 JSON：
{
  "updated": "2026-09-16 19:06",
  "market": {
    "indices": [{code,name,point,chg,pct,turnover}],
    "turnover_total": 1.84e12,          # 元
    "sectors_up": [{name,pct}], "sectors_down": [{name,pct}],
    "breadth": {up,down,flat,total} | null
  },
  "news": [{title,url,media,time}],
  "sources": {"quotes": "eastmoney|sina", "news": "sina-roll|10jqka|stcn"}
}
单源失败不阻塞：行情双源都失败 → market 为 null；要闻三源都失败 → news 为空数组。
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import datetime

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

# 指数：东方财富 secid → 名称；新浪代码作兜底
INDEXES = [
    ("1.000001", "000001", "s_sh000001", "上证指数"),
    ("0.399001", "399001", "s_sz399001", "深证成指"),
    ("0.399006", "399006", "s_sz399006", "创业板指"),
    ("1.000688", "000688", "s_sh000688", "科创50"),
    ("0.899050", "899050", "s_bj899050", "北证50"),
    ("1.000300", "000300", "s_sh000300", "沪深300"),
]
# 东方财富两个行情域名：push2 实时优先，push2delay 延迟行情通常不限流（作兜底）
EM_HOSTS = ("https://push2.eastmoney.com", "https://push2delay.eastmoney.com")
EM_QUOTE = "/api/qt/ulist.np/get?fields=f1,f2,f3,f4,f6,f12,f13,f14&fltt=2&invt=2&secids={secids}"
EM_LIST = "/api/qt/clist/get?pn={pn}&pz={pz}&po={po}&np=1&fltt=2&invt=2&fid=f3&fs={fs}&fields={fields}"
SINA_HQ = "https://hq.sinajs.cn/list={codes}"
LHB_URL = ("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_DAILYBILLBOARD_DETAILSNEW"
           "&columns=TRADE_DATE,SECURITY_CODE,SECURITY_NAME_ABBR,CHANGE_RATE,BILLBOARD_NET_AMT,"
           "BILLBOARD_BUY_AMT,BILLBOARD_SELL_AMT,EXPLAIN&filter=(TRADE_DATE%3D%27{date}%27)"
           "&pageNumber=1&pageSize={n}&sortColumns=BILLBOARD_NET_AMT&sortTypes=-1&source=WEB&client=WEB")
SINA_ROLL = "https://feed.mix.sina.com.cn/api/roll/get?pageid={pageid}&lid={lid}&num={num}&page=1"
# 新浪频道 pageid 归属：财经频道在 153，综合滚动在 155（lid 1686）
SINA_PAGEID = {1686: 155}
THS_NEWS = "http://news.10jqka.com.cn/today_list/"
STCN_NEWS = "https://www.stcn.com/"

NOISE = ("举报", "版权", "关于我们", "客户端", "广告", "招聘", "注册", "登录", "联系",
         "手机版", "APP", "免责", "隐私", "网站地图", "RSS", "更多", "订阅", "首页")


def fetch(url, referer="", encoding=None, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
        **({"Referer": referer} if referer else {}),
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    if encoding:
        return raw.decode(encoding, errors="ignore")
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def num(v):
    return v if isinstance(v, (int, float)) else None


# ── 行情 ───────────────────────────────────────────────────────────────
def _pack_indices(diff):
    by_code = {str(x.get("f12")): x for x in diff}
    out = []
    for _secid, code, _sina, name in INDEXES:
        x = by_code.get(code)
        if not x:
            continue
        out.append({"code": code, "name": x.get("f14") or name,
                    "point": num(x.get("f2")), "chg": num(x.get("f4")),
                    "pct": num(x.get("f3")), "turnover": num(x.get("f6"))})
    return out or None


def quotes_eastmoney(retries=2):
    """东方财富指数行情：push2 → push2delay 两个域名，各带退避重试。"""
    secids = ",".join(i[0] for i in INDEXES)
    for attempt in range(retries + 1):
        for host in EM_HOSTS:
            try:
                d = json.loads(fetch(host + EM_QUOTE.format(secids=secids),
                                     referer="https://quote.eastmoney.com/"))
                diff = (d.get("data") or {}).get("diff") or []
                packed = _pack_indices(diff) if diff else None
                if packed:
                    return packed, ("eastmoney" if "push2delay" not in host else "eastmoney-delay")
            except Exception:
                pass
        if attempt < retries:
            time.sleep(0.8 * (attempt + 1))
    raise RuntimeError("empty diff")


def quotes_sina():
    codes = ",".join(i[2] for i in INDEXES)
    text = fetch(SINA_HQ.format(codes=codes), referer="https://finance.sina.com.cn",
                 encoding="gb18030")
    out = []
    for line, (_s, code, _sc, name) in zip(re.findall(r'="([^"]*)"', text), INDEXES):
        p = line.split(",")
        if len(p) < 6:
            continue
        out.append({"code": code, "name": p[0] or name,
                    "point": float(p[1]), "chg": float(p[2]), "pct": float(p[3]),
                    "turnover": float(p[5]) * 10000 if p[5] else None})  # 万元 → 元
    if not out:
        raise RuntimeError("sina parse failed")
    return out, "sina"


def _sector_page(limit, po, fs, retries=3):
    """取一页板块榜（涨/跌）；失败重试，仍失败返回 None（不静默吞成空列表）。"""
    for attempt in range(retries + 1):
        for host in EM_HOSTS:
            try:
                d = json.loads(fetch(host + EM_LIST.format(pn=1, pz=limit, po=po, fs=fs, fields="f3,f14"),
                                     referer="https://quote.eastmoney.com/"))
                rows = [{"name": x.get("f14"), "pct": num(x.get("f3"))}
                        for x in ((d.get("data") or {}).get("diff") or [])
                        if num(x.get("f3")) is not None]
                if rows:
                    return rows
            except Exception:
                pass
        if attempt < retries:
            time.sleep(0.8 * (attempt + 1))   # 退避，防东财限流
    return None


def sectors(limit, fs="m:90+t:2"):
    """行业板块涨幅榜 / 跌幅榜。返回 (up, down)；单侧失败返回 None 以便上层报告状态。"""
    up = _sector_page(limit, 1, fs)
    time.sleep(0.3)
    down = _sector_page(limit, 0, fs)
    return up, down


def breadth(max_pages=60):
    """涨跌家数：逐页拉沪深A股快照统计（较慢，默认关闭）。"""
    fs = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
    up = down = flat = 0
    total = None
    for pn in range(1, max_pages + 1):
        try:
            d = json.loads(fetch(EM_LIST.format(pn=pn, pz=100, po=1, fs=fs, fields="f3")))
        except Exception:
            break
        data = d.get("data") or {}
        diff = data.get("diff") or []
        total = data.get("total") or total
        if not diff:
            break
        for x in diff:
            v = num(x.get("f3"))
            if v is None:
                flat += 1
            elif v > 0:
                up += 1
            elif v < 0:
                down += 1
            else:
                flat += 1
        if total and (up + down + flat) >= total:
            break
        time.sleep(0.05)
    if up + down + flat == 0:
        return None
    return {"up": up, "down": down, "flat": flat, "total": total or (up + down + flat)}



def _lhb_raw(limit, date_str):
    d = json.loads(fetch(LHB_URL.format(date=date_str, n=limit), referer="https://data.eastmoney.com/"))
    if not d.get("success"):
        raise RuntimeError(d.get("message") or "lhb failed")
    rows = (d.get("result") or {}).get("data") or []
    if not rows:
        raise RuntimeError("lhb empty")
    return rows


def lhb(limit):
    """龙虎榜（按净买入额降序）。找不到当日就往前找最多 7 天；全失败退回「涨幅榜」。"""
    import datetime as _dt
    for i in range(8):
        d = (_dt.date.today() - _dt.timedelta(days=i)).isoformat()
        try:
            rows = _lhb_raw(limit, d)
        except Exception:
            continue
        items = []
        for n, r in enumerate(rows, 1):
            items.append({
                "rank": n,
                "code": r.get("SECURITY_CODE"),
                "name": r.get("SECURITY_NAME_ABBR"),
                "pct": num(r.get("CHANGE_RATE")),
                "net": num(r.get("BILLBOARD_NET_AMT")),
                "explain": (r.get("EXPLAIN") or "").strip(),
            })
        return {"items": items, "date": d, "source": "eastmoney-lhb"}
    # 兜底：涨幅榜
    try:
        fs = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
        d = json.loads(fetch(next(h for h in EM_HOSTS) + EM_LIST.format(
            pn=1, pz=limit, po=1, fs=fs, fields="f2,f3,f12,f14"),
            referer="https://quote.eastmoney.com/"))
        rows = (d.get("data") or {}).get("diff") or []
        items = [{"rank": n, "code": x.get("f12"), "name": x.get("f14"),
                  "pct": num(x.get("f3")), "net": None, "explain": "涨幅榜（龙虎榜不可用）"}
                 for n, x in enumerate(rows, 1)]
        return {"items": items, "date": "", "source": "eastmoney-gainers"} if items else None
    except Exception:
        return None


# ── 要闻 ───────────────────────────────────────────────────────────────
def news_sina(limit, lids=(2516, 2518)):
    """新浪财经滚动（pageid=153）：2516=财经要闻、2518=国际市场；多频道合并去重。"""
    items, seen = [], set()
    for lid in lids:
        try:
            pageid = SINA_PAGEID.get(lid, 153)
            d = json.loads(fetch(SINA_ROLL.format(pageid=pageid, lid=lid, num=max(limit, 15))))
        except Exception:
            continue
        for it in (d.get("result") or {}).get("data") or []:
            title = (it.get("title") or "").strip()
            url = it.get("url") or ""
            if not title or not url or title in seen:
                continue
            seen.add(title)
            ts = it.get("intime") or it.get("ctime")
            try:
                tm = datetime.fromtimestamp(int(ts)).strftime("%H:%M")
            except (TypeError, ValueError):
                tm = ""
            items.append({"title": title, "url": url,
                          "media": (it.get("media_name") or "").strip(), "time": tm})
    if not items:
        raise RuntimeError("sina roll empty")
    items.sort(key=lambda x: x["time"], reverse=True)
    return items[:limit], "sina-roll"


def news_10jqka(limit):
    page = fetch(THS_NEWS, encoding="gb18030")
    items, seen = [], set()
    for url, title in re.findall(r'<a[^>]+href="(https?://news\.10jqka\.com\.cn/\d+/c\d+\.shtml)"[^>]*>([^<]{8,60})</a>', page):
        t = re.sub(r"\s+", " ", title).strip()
        if url in seen or any(n in t for n in NOISE):
            continue
        seen.add(url)
        items.append({"title": t, "url": url, "media": "同花顺", "time": ""})
        if len(items) >= limit:
            break
    if not items:
        raise RuntimeError("10jqka empty")
    return items, "10jqka"


def news_stcn(limit):
    page = fetch(STCN_NEWS)
    items, seen = [], set()
    for url, title in re.findall(r'<a[^>]+href="(/article/detail/\d+\.html)"[^>]*>([^<]{8,60})</a>', page):
        t = re.sub(r"\s+", " ", title).strip()
        if url in seen or any(n in t for n in NOISE):
            continue
        seen.add(url)
        items.append({"title": t, "url": "https://www.stcn.com" + url, "media": "证券时报", "time": ""})
        if len(items) >= limit:
            break
    if not items:
        raise RuntimeError("stcn empty")
    return items, "stcn"


def main():
    ap = argparse.ArgumentParser(description="A股大盘行情 + 财经要闻")
    ap.add_argument("--news-limit", type=int, default=8)
    ap.add_argument("--news-lid", default="2516,2518",
                    help="新浪财经频道 lid，逗号分隔（2516=财经要闻 2518=国际市场）")
    ap.add_argument("--sectors", type=int, default=5, help="板块涨/跌幅榜条数")
    ap.add_argument("--breadth", action="store_true", help="附加涨跌家数（慢）")
    ap.add_argument("--lhb", type=int, default=8, help="龙虎榜条数（0=不取）")
    ap.add_argument("--no-news", action="store_true")
    ap.add_argument("--no-quotes", action="store_true")
    args = ap.parse_args()

    out = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "market": None, "news": [], "sources": {}}

    if not args.no_quotes:
        indices, src = None, ""
        for fn in (quotes_eastmoney, quotes_sina):
            try:
                indices, src = fn()
                break
            except Exception:
                continue
        if indices:
            cyb = {i["code"]: i for i in indices}
            turnover = sum(i["turnover"] or 0 for i in
                           (cyb.get("000001"), cyb.get("399001")) if i)
            up, down = (sectors(args.sectors) if args.sectors > 0 else ([], []))
            mkt = {"indices": indices,
                   "turnover_total": turnover or None,
                   "sectors_up": up or [], "sectors_down": down or [],
                   "sectors_ok": bool(up) and bool(down),
                   "breadth": breadth() if args.breadth else None,
                   "lhb": (lhb(args.lhb) if args.lhb else None)}
            out["market"] = mkt
            out["sources"]["quotes"] = src

    if not args.no_news:
        lids = tuple(int(x) for x in str(args.news_lid).split(",") if x.strip().isdigit())
        for fn in (lambda: news_sina(args.news_limit, lids),
                   lambda: news_10jqka(args.news_limit),
                   lambda: news_stcn(args.news_limit)):
            try:
                items, src = fn()
                out["news"] = items
                out["sources"]["news"] = src
                break
            except Exception:
                continue

    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out["market"] is None and not out["news"] and not (args.no_news or args.no_quotes):
        sys.exit(1)


if __name__ == "__main__":
    main()
