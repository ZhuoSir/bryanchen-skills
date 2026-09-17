#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告装配器：并行抓全部数据源 → 直接产出「内容 JSON」（纯标准库）。

产出可直接交给 render_email.py / render_h5.py；
模型只需在 JSON 里补 `summary`（一句话摘要），其余字段全部由脚本填好。

用法：
  python3 scripts/build_report.py --mode morning --out /tmp/morning_report.json
  python3 scripts/build_report.py --mode evening --out /tmp/evening_report.json --dedup

放开配额（默认已放大，按需再加）：
  --news 8        国际/国内各最多 8 条（来自 news_api 全部 15 条 + news_web 兜底）
  --ai 9          AI 动态最多 9 条（量子位/TechCrunch/InfoQ 各 5 条里挑）
  --finance 12    财经要闻最多 12 条
  --weather-news 8 天气新闻最多 8 条
  --sports 6      足球/篮球热帖各最多 6 条
  --hot 10        每个热榜平台最多 10 条
  --sectors 8     大盘领涨/领跌各 8 个板块
  --web 0         news_web 频道页补充条数（0=不用）

--dedup：装配后直接过一遍 sent_log（晚报默认建议开，避免与晨报重复）
--raw-dir DIR：把各脚本原始输出落盘，便于排查
"""
import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CITIES = "北京,深圳,上海,杭州,通辽,崇礼"
INTL_KEYS = ("美国", "英国", "日本", "俄", "欧盟", "塞方", "印度", "联合国", "伊朗",
             "以色列", "沙特", "德国", "法国", "韩国", "朝鲜", "乌克兰", "加拿大", "澳")


def run(script, args, timeout=90):
    """跑一个取数脚本，返回解析后的 JSON（失败返回 None）。"""
    cmd = [sys.executable, os.path.join(HERE, script)] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return json.loads(r.stdout) if r.stdout.strip() else None
    except Exception as e:
        sys.stderr.write(f"[warn] {script} {' '.join(args)} 失败: {e}\n")
        return None


def is_intl(title):
    return any(k in title for k in INTL_KEYS)


def hhmm_alert(rain_prob):
    return "建议带伞" if (rain_prob or 0) >= 50 else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="morning", choices=["morning", "evening"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--news", type=int, default=8)
    ap.add_argument("--ai", type=int, default=9)
    ap.add_argument("--finance", type=int, default=12)
    ap.add_argument("--weather-news", type=int, default=8)
    ap.add_argument("--sports", type=int, default=6)
    ap.add_argument("--hot", type=int, default=5)
    ap.add_argument("--sectors", type=int, default=8)
    ap.add_argument("--lhb", type=int, default=8, help="龙虎榜条数（0=不取）")
    ap.add_argument("--web", type=int, default=0, help="news_web 补充条数（0=不用）")
    ap.add_argument("--dedup", action="store_true", help="装配后过 sent_log 去重")
    ap.add_argument("--date", default="", help="台账日期，缺省今天")
    ap.add_argument("--watch", default="",
                    help="特别关注词条，逗号分隔；缺省读 data/watchlist.json 的 keywords")
    ap.add_argument("--watch-limit", type=int, default=8, help="每个词条最多几条")
    ap.add_argument("--watch-days", type=int, default=3, help="只保留近 N 天（0=不限）")
    ap.add_argument("--raw-dir", default="", help="原始输出落盘目录")
    args = ap.parse_args()

    ev = args.mode == "evening"
    today = (__import__("datetime").date.today()).isoformat()

    # ── 并行取数 ──────────────────────────────────────────────
    # 取数时按 2~3 倍抓：去重会剔掉晨报已发条目，需要余量来补位
    def fetch_n(target, mult=2, cap=40):
        return min(max(target * mult, target + 8), cap)

    # 特别关注：--watch 优先，缺省读 data/watchlist.json
    watch_kws = [k.strip() for k in args.watch.split(",") if k.strip()]
    if not watch_kws:
        wl_path = os.path.join(ROOT, "data", "watchlist.json")
        if os.path.exists(wl_path):
            try:
                watch_kws = [k.strip() for k in json.load(open(wl_path, encoding="utf-8")).get("keywords", []) if str(k).strip()]
            except (OSError, json.JSONDecodeError):
                watch_kws = []

    jobs = {
        "weather": ("weather.py", (["--tomorrow"] if ev else [])),
        **({"watch": ("watch_news.py", ["--kw", ",".join(watch_kws),
                                        "--limit", str(args.watch_limit), "--days", str(args.watch_days)])}
           if watch_kws else {}),
        "weather_news": ("weather_news.py", ["--limit", str(fetch_n(args.weather_news, 3, 30)), "--cities", CITIES]),
        "news": ("news_api.py", ["--max", "15"]),
        "finance": ("finance.py", ["--news-limit", str(fetch_n(args.finance, 3, 40)), "--sectors", str(args.sectors),
                                   "--lhb", str(args.lhb)]),
        "rss": ("fetch_rss.py", ["--days", "2", "--per-source", "8"]),
        "hupu": ("hupu.py", ["--per-section", str(fetch_n(args.sports, 3, 30))]),
        "hot": ("hot_rank.py", ["--top", str(fetch_n(args.hot, 4, 50))]),
    }
    if args.web:
        jobs["web"] = ("news_web.py", ["--sources", "all", "--limit", str(args.web)])

    data = {}
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = {k: ex.submit(run, *v) for k, v in jobs.items()}
        for k, f in futs.items():
            data[k] = f.result()

    # ── 去重准备：在取 N 条之前过滤候选池，被剔除的条目会自动由后面的候选补位 ──
    keys = set()
    if args.dedup:
        sys.path.insert(0, HERE)
        import sent_log                      # 同目录模块
        state = sent_log.load_state(args.date or today)
        keys, _ = sent_log.collect_keys(state)

    skipped = [0]

    def fresh(items):
        """剔除当日已发条目（标题归一化或 URL 相同），返回剩余候选。"""
        if not keys:
            return list(items)
        out = []
        for it in items:
            k = sent_log.norm_key(it.get("title"))
            u = sent_log.norm_key(it.get("url")) if it.get("url") else ""
            if (k and k in keys) or (u and u in keys):
                skipped[0] += 1
                continue
            out.append(it)
        return out

    if args.raw_dir:
        os.makedirs(args.raw_dir, exist_ok=True)
        for k, v in data.items():
            if v is not None:
                with open(os.path.join(args.raw_dir, k + ".json"), "w", encoding="utf-8") as fp:
                    json.dump(v, fp, ensure_ascii=False, indent=1)

    blocks = []

    # 1) 天气
    w = data.get("weather") or {}
    rows = []
    for c in w.get("cities", []):
        d = c.get("tomorrow") if ev else c.get("today")
        if not d:
            continue
        note = f"降水 {d.get('rain_prob', 0)}%"
        if not ev and c.get("now"):
            note = f"现在 {round(c['now']['temp'])}° · 体感 {round(c['now']['feels_like'])}° · " + note
        rows.append({"city": c["city"], "cond": d.get("text", ""),
                     "text": f"{round(d.get('min', 0))}~{round(d.get('max', 0))}°",
                     "note": note, **({"alert": hhmm_alert(d.get("rain_prob"))} if hhmm_alert(d.get("rain_prob")) else {})})
    if rows:
        blocks.append({"type": "weather", "label": "明日天气" if ev else "今日天气",
                       "en": "WEATHER", "nav": "天气", "rows": rows})

    # 2) 特别关注（观察名单，紧跟天气之后）
    for w in (data.get("watch") or {}).get("watches", []):
        if not w.get("items"):
            continue
        watch_items = []
        for i in w["items"]:
            src = i.get("source", "")
            pub = (i.get("published") or "")[5:]        # 'MM-DD HH:MM'
            if pub:
                src = f"{src} · {pub}" if src else pub
            watch_items.append({"title": i["title"], "url": i["url"],
                                "source": src, "published": i.get("published", "")})
        blocks.append({"type": "news",
                       "label": f"特别关注 · {w['kw']}", "en": "WATCH", "nav": "特别关注",
                       "items": fresh(watch_items)[:args.watch_limit]})

    # 3) 天气新闻
    wn = (data.get("weather_news") or {}).get("items", [])
    if wn:
        blocks.append({"type": "news", "label": "天气新闻", "en": "WEATHER NEWS", "nav": "天气",
                       "items": fresh([{"title": i["title"], "url": i["url"],
                                        "source": f"中国天气网 · {i.get('tag', '全国')}"}
                                       for i in wn])[:args.weather_news]})

    # 4) 国际 / 国内
    news = (data.get("news") or {}).get("items", [])
    web = ((data.get("web") or {}).get("items") or []) if args.web else []
    pool = [{"title": i["title"], "url": i["url"]} for i in news] + \
           [{"title": i["title"], "url": i["url"], "source": i.get("outlet", "")} for i in web]
    intl = fresh([i for i in pool if is_intl(i["title"])])[:args.news]
    dom = fresh([i for i in pool if not is_intl(i["title"])])[:args.news]
    if intl:
        blocks.append({"type": "news", "label": "国际新闻", "en": "WORLD", "nav": "国际新闻", "items": intl})
    if dom:
        blocks.append({"type": "news", "label": "国内新闻", "en": "CHINA", "nav": "国内新闻", "items": dom})

    # 4) 大盘 + 财经要闻
    fin = data.get("finance") or {}
    m = fin.get("market")
    if m:
        blocks.append({"type": "market", "label": "A股大盘", "en": "MARKET", "nav": "财经新闻", "half": True,
                       "indices": [{"name": i["name"], "point": i["point"], "chg": i["chg"], "pct": i["pct"]}
                                   for i in m.get("indices", [])],
                       "footnote": "两市成交额 {} 亿元 · 数据 {} · {}".format(
                           f'{(m.get("turnover_total") or 0) / 1e8:,.0f}', fin.get("updated", ""),
                           "今日收盘" if ev else "昨日收盘"),
                       "up": m.get("sectors_up", []), "down": m.get("sectors_down", [])})
    lh = (m or {}).get("lhb") or {}
    if lh.get("items"):
        blocks.append({"type": "lhb", "label": "龙虎榜", "en": "LHB", "nav": "财经新闻", "half": True,
                       "items": lh["items"],
                       "footnote": "按净买入额排序 · {} · 来源 {}".format(
                           (lh.get("date") or "最新交易日"),
                           "东方财富龙虎榜" if lh.get("source") == "eastmoney-lhb" else "涨幅榜（龙虎榜不可用）")})

    fn = fin.get("news", [])
    if fn:
        blocks.append({"type": "news", "label": "财经要闻", "en": "FINANCE", "nav": "财经新闻",
                       "items": fresh([{"title": i["title"], "url": i["url"],
                                     **({"source": i["media"]} if i.get("media") else {})}
                                    for i in fn])[:args.finance]})

    # 5) AI 动态
    ai = (data.get("rss") or {}).get("items", [])
    if ai:
        blocks.append({"type": "news", "label": "AI 动态", "en": "AI", "nav": "AI 动态",
                       "items": fresh([{"title": i["title"], "url": i["url"], "source": i.get("source", "")}
                                    for i in ai])[:args.ai]})

    # 6) 体育（足球 / 篮球 / 其他）
    hp = data.get("hupu") or {}
    matches = (hp.get("matches") or {}).get("football") or []
    fb_sched = [{"time": x.get("time", ""),
                 "text": "{} · {} {}-{} {}".format(x.get("competition", ""), x.get("home", ""),
                                                   x.get("home_score", ""), x.get("away_score", ""), x.get("away", "")).strip(" -"),
                 "state": x.get("status", "")} for x in matches]
    for key, label, en in (("football", "足球", "FOOTBALL"), ("basketball", "篮球", "BASKETBALL")):
        sec = (hp.get("sections") or {}).get(key) or []
        if not sec:
            continue
        sched = fb_sched if key == "football" else [{"time": "", "text": "今晚无 NBA 比赛（休赛期）" if ev else "今日无 NBA 比赛（休赛期）", "state": ""}]
        blocks.append({"type": "schedule", "label": label, "en": en, "nav": "体育新闻",
                       "note": "虎扑实时热帖", "schedule_label": "今晚赛程" if ev else "今日赛程",
                       "schedule": sched,
                       "items": fresh([{"title": i["title"], "url": i["url"],
                                     **({"pinned": True} if i.get("pinned") else {})}
                                    for i in sec])[:args.sports]})

    # 7) 热榜
    boards = (data.get("hot") or {}).get("boards") or {}
    hot_boards = []
    for b in boards.values():
        if not b.get("ok"):
            continue
        hot_boards.append({"board": b["name"], "items": fresh([
            {"title": i["title"], "url": i["link"],
             "hot": (f"{i['hot']/10000:.0f}万" if isinstance(i.get("hot"), (int, float)) and i["hot"] > 100000 else str(i.get("hot", "")))}
            for i in b["items"]])[:args.hot]})
    if hot_boards:
        blocks.append({"type": "hot", "label": "全网热榜", "en": "TRENDING", "nav": "热榜", "boards": hot_boards})

    out = {"mode": args.mode, "date": today,
           "weekday": "周" + "一二三四五六日"[__import__("datetime").date.today().weekday()],
           "weather_cond": (rows[0]["cond"] if rows else "阴"),
           "quote": (data.get("news") or {}).get("tip") or "",
           "blocks": blocks}

    removed = skipped[0]        # 被去重跳过的候选条数（已由后续候选补位）

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    blocks = out["blocks"]          # 去重后要重新取一次，否则统计是旧数据
    stat = {b.get("label", b.get("type")): (len(b.get("items", [])) if b.get("type") != "hot"
            else sum(len(x["items"]) for x in b.get("boards", []))) for b in blocks}
    print(json.dumps({"ok": True, "out": args.out, "mode": args.mode,
                      "blocks": stat, "total_items": sum(stat.values()),
                      "dedup_removed": removed,
                      "missing_sources": [k for k, v in data.items() if v is None]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
