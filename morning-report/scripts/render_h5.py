#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把晨报/晚报内容 JSON 渲染成**可切换的 H5 页面**（真 Tab，点击导航切换内容面板）。

与 render_email.py 共用同一份内容 JSON：
  · render_email.py → 邮件正文（邮件客户端禁 JS，所以是完整堆叠版）
  · render_h5.py    → H5 页面（导航可点击切换、支持 URL hash 直达、手机自适应）

用法：
  python3 scripts/render_h5.py --data /tmp/report.json --out /tmp/report.html
  python3 scripts/render_h5.py --data ... --out ... --img-mode data   # 图标 base64 内联（推荐，单文件可发）

交互：
  · 点顶部导航切换内容面板；点击后 URL 追加 #tab-<n>，可直接分享/收藏某个板块
  · 打开时若 URL 带 hash，则直接定位到该板块；否则显示第一个板块
  · 键盘 ← → 可切换板块
主题：mode=morning 浅色、mode=evening 暗黑（与邮件同一套配色）
"""
import argparse
import base64
import html as html_mod
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ICONS = os.path.join(ROOT, "assets", "icons", "png")

THEMES = {
    "light": {
        "bg": "#f6f6f5", "card": "#ffffff", "card2": "#f6f6f5", "text": "#1c1c1e",
        "muted": "#8a8a8e", "body": "#6c6c70", "line": "#ececea",
        "up": "#D93025", "down": "#0E8A4F", "shadow": "0 1px 2px rgba(0,0,0,.04), 0 8px 24px rgba(0,0,0,.05)",
    },
    "dark": {
        "bg": "#0a0a0c", "card": "#141417", "card2": "#1c1c21", "text": "#ededf0",
        "muted": "#8d8d96", "body": "#a3a3ac", "line": "#26262c",
        "up": "#FF6B60", "down": "#34D399", "shadow": "0 1px 2px rgba(0,0,0,.4), 0 10px 30px rgba(0,0,0,.35)",
    },
}
ACCENTS = {
    "light": {"clear": "#F4511E", "cloudy": "#D97706", "overcast": "#8A8A8E",
              "rain": "#2563EB", "thunder": "#7C3AED", "snow": "#0891B2", "fog": "#94A3B8"},
    "dark": {"clear": "#FF7A45", "cloudy": "#F0A742", "overcast": "#A1A1AA",
             "rain": "#6B8CFF", "thunder": "#A78BFA", "snow": "#38BDF8", "fog": "#A8B4C4"},
}
COND_RULES = [
    ("thunder", ("雷", "thunder", "storm")), ("snow", ("雪", "snow", "sleet")),
    ("rain", ("雨", "rain", "drizzle", "shower")), ("fog", ("雾", "霾", "fog", "haze", "mist")),
    ("clear", ("晴", "clear", "sunny", "sun")), ("cloudy", ("多云", "cloudy", "partly")),
    ("overcast", ("阴", "overcast", "cloud")),
]
CAT_COLORS = {
    "light": {"weather": "#0E7C86", "world": "#3B5BDB", "china": "#C2255C",
              "finance": "#B7791F", "ai": "#7048E8", "sports": "#0E8A4F", "hot": "#E8590C", "watch": "#DB2777"},
    "dark": {"weather": "#4DD0E1", "world": "#8FA2FF", "china": "#FF7AA2",
             "finance": "#FFC13B", "ai": "#B197FC", "sports": "#4ADE80", "hot": "#FF9F45", "watch": "#F472B6"},
}
CAT_RULES = [("天气", "weather"), ("国际", "world"), ("国内", "china"), ("大盘", "finance"),
             ("财经", "finance"), ("AI", "ai"), ("人工智能", "ai"), ("足球", "sports"),
             ("篮球", "sports"), ("体育", "sports"), ("热榜", "hot"), ("热搜", "hot"), ("关注", "watch"), ("WATCH", "watch")]
COND_COLORS = {
    "light": {"clear": "#D97706", "cloudy": "#8A8A8E", "overcast": "#8A8A8E",
              "rain": "#2563EB", "thunder": "#7C3AED", "snow": "#0891B2", "fog": "#94A3B8"},
    "dark": {"clear": "#FFC13B", "cloudy": "#A1A1AA", "overcast": "#A1A1AA",
             "rain": "#7AA2FF", "thunder": "#B197FC", "snow": "#5AD1E8", "fog": "#A8B4C4"},
}

SECTION_ICON = [("天气", "w-auto"), ("国际", "world"), ("国内", "flag"), ("大盘", "chart-candle"),
                ("财经", "chart-candle"), ("AI", "cpu"), ("人工智能", "cpu"), ("足球", "ball-football"),
                ("篮球", "ball-basketball"), ("体育", "ball-football"), ("热榜", "flame"), ("热搜", "flame"), ("关注", "star"), ("特别", "star")]
MODE_META = {"morning": {"name": "晨报", "kicker": "MORNING REPORT"},
             "evening": {"name": "晚报", "kicker": "EVENING REPORT"}}
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
                      "\U00002B00-\U00002BFF\U0000FE0F\U0000200D\U00002190-\U000021FF]+")
_CACHE = {}


def esc(s):
    return html_mod.escape(EMOJI_RE.sub("", str(s or "")).strip(), quote=True)


def cond_family(cond):
    c = (cond or "").strip().lower()
    for fam, keys in COND_RULES:
        if any(k in c for k in keys):
            return fam
    return "overcast"


def icon(name, theme, img_mode, size=16):
    if not name:
        return ""
    path = os.path.join(ICONS, theme, name + ".png")
    if not os.path.exists(path):
        return ""
    if img_mode == "data":
        if path not in _CACHE:
            with open(path, "rb") as f:
                _CACHE[path] = "data:image/png;base64," + base64.b64encode(f.read()).decode()
        src = _CACHE[path]
    else:
        src = os.path.relpath(path, ROOT)
    return f'<img src="{src}" width="{size}" height="{size}" alt="">'


def cat_of(block):
    zh = str(block.get("nav") or "") + str(block.get("label") or "")
    for key, c in CAT_RULES:
        if key in zh:
            return c
    return ""


def cat_color(block, theme):
    c = cat_of(block)
    return CAT_COLORS[theme].get(c, "#8a8a8e") if c else "#8a8a8e"


def cat_icon(block, theme):
    """栏目彩色图标文件名（无则回退中性）。"""
    zh = str(block.get("label") or "")
    c = cat_of(block)
    if c == "finance" and "龙虎榜" in zh:
        return "cat-finance-coin"
    return {"world": "cat-world-world", "china": "cat-china-flag", "finance": "cat-finance-chart-candle",
            "ai": "cat-ai-cpu", "hot": "cat-hot-flame", "watch": "cat-watch-star",
            "sports": "cat-sports-ball-basketball" if "篮球" in zh else "cat-sports-ball-football",
            }.get(c, "")


def section_icon(block, theme, img_mode, weather_icon):
    zh = str(block.get("label", ""))
    if cat_of(block) == "weather":
        return weather_icon
    colored = cat_icon(block, theme)
    if colored:
        img = icon(colored, theme, img_mode)
        if img:
            return img
    for key, ic in SECTION_ICON:
        if key in zh:
            return weather_icon if ic == "w-auto" else icon(ic, theme, img_mode)
    return ""


def pct_class(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "flat"
    return "up" if f > 0 else ("down" if f < 0 else "flat")


def fmt_pct(v):
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return ""


def sec_head(block, t, ic, sub=False):
    """板块标题：栏目色竖条 + 图标 + 中文 + EN（栏目色）。"""
    cc = cat_color(block, t["_theme"])
    bar = f'<span class="bar" style="background:{cc}"></span>'
    cls = "sec-label sub" if sub else "sec-label"
    return f'<div class="{cls}">{bar}{ic}<span>{esc(block.get("label"))}</span></div>'


def render_weather(block, t, ic, img_mode="data", **kw):
    theme = t["_theme"]

    def one(r):
        cond = r.get("cond") or r.get("text") or ""
        fam = cond_family(cond)
        ric = icon("w-" + fam, theme, img_mode, 16)
        cc = COND_COLORS[theme].get(fam, t["muted"])
        alert = f'<span class="walert">· {esc(r.get("alert"))}</span>' if r.get("alert") else ""
        return ('<div class="wrow">'
                f'<div class="wcity">{esc(r.get("city"))}</div>'
                f'<div class="wcond" style="color:{cc}">{ric}<span>{esc(cond)}</span></div>'
                f'<div class="wtext">{esc(r.get("text"))}'
                f'<span class="wnote">· {esc(r.get("note"))}</span>{alert}</div></div>')

    rows = "".join(one(r) for r in block.get("rows", []))
    return f'<div class="card weather">{sec_head(block, t, ic)}{rows}</div>'


def render_market(block, t, ic, **kw):
    rows = "".join(
        f'<tr><td class="mname">{esc(i.get("name"))}</td>'
        f'<td class="mpoint">{i.get("point"):,.2f}<span class="chg {pct_class(i.get("pct"))}">'
        f'{"%+.2f" % i["chg"] if isinstance(i.get("chg"), (int, float)) else ""}</span></td>'
        f'<td class="mpct {pct_class(i.get("pct"))}">{fmt_pct(i.get("pct"))}</td></tr>'
        for i in block.get("indices", []))
    chips = "".join(
        f'<span class="chip-n">{esc(s.get("name"))} <b class="{pct_class(s.get("pct"))}">{fmt_pct(s.get("pct"))}</b></span>'
        for s in block.get("up", []))
    chips_d = "".join(
        f'<span class="chip-n">{esc(s.get("name"))} <b class="{pct_class(s.get("pct"))}">{fmt_pct(s.get("pct"))}</b></span>'
        for s in block.get("down", []))
    foot = f'<div class="foot">{esc(block.get("footnote"))}</div>' if block.get("footnote") else ""
    return (sec_head(block, t, ic)
            + f'<div class="card"><table class="market">{rows}</table>'
            + (f'<div class="chips"><span class="chip-l">领涨</span>{chips}</div>' if chips else "")
            + (f'<div class="chips"><span class="chip-l">领跌</span>{chips_d}</div>' if chips_d else "")
            + foot + '</div>')


def render_news(block, t, ic, **kw):
    items = []
    for it in block.get("items", []):
        src = f'<span class="src">· {esc(it.get("source"))}</span>' if it.get("source") else ""
        pin = '<span class="pin"></span>' if it.get("pinned") else ""
        summ = f'<div class="summary">{esc(it.get("summary"))}</div>' if it.get("summary") else ""
        items.append(f'<a class="item" href="{esc(it.get("url", "#"))}" target="_blank" rel="noopener">'
                     f'<div class="title">{pin}{esc(it.get("title"))}{src}</div>{summ}</a>')
    return (f'<div class="sec-label">{ic}<span>{esc(block.get("label"))}</span></div>'
            f'<div class="card list">{"".join(items)}</div>')


def render_schedule(block, t, ic, small=False, **kw):
    rows = ""
    if block.get("schedule"):
        lines = "".join(
            f'<div class="sched-line">'
            + (f'<b>{esc(m.get("time"))}</b> ' if m.get("time") else "")
            + f'{esc(m.get("text"))}'
            + (f'<span class="muted"> · {esc(m.get("state"))}</span>' if m.get("state") else "")
            + '</div>'
            for m in block["schedule"])
        rows = (f'<div class="sched"><div class="sched-label">'
                f'{esc(block.get("schedule_label") or "今日赛程")}</div>{lines}</div>')
    items = []
    for it in block.get("items", []):
        pin = '<span class="pin"></span>' if it.get("pinned") else ""
        summ = f'<div class="summary">{esc(it.get("summary"))}</div>' if it.get("summary") else ""
        items.append(f'<a class="item" href="{esc(it.get("url", "#"))}" target="_blank" rel="noopener">'
                     f'<div class="title">{pin}{esc(it.get("title"))}</div>{summ}</a>')
    note = f'<span class="note">{esc(block.get("note"))}</span>' if block.get("note") else ""
    label = sec_head(block, t, ic, sub=small).replace("</div>", f"{note}</div>")
    return f'{label}<div class="card">{rows}{"".join(items)}</div>'


def render_hot(block, t, ic, **kw):
    boards = []
    for b in block.get("boards", []):
        rows = "".join(
            f'<a class="hot-row" href="{esc(i.get("url", "#"))}" target="_blank" rel="noopener">'
            f'<span class="rank">{n}</span><span class="hot-title">{esc(i.get("title"))}</span>'
            f'<span class="hot-num">{esc(i.get("hot"))}</span></a>'
            for n, i in enumerate(b.get("items", []), 1))
        boards.append(f'<div class="board"><div class="board-name">{esc(b.get("board"))}</div>{rows}</div>')
    return (f'<div class="sec-label">{ic}<span>{esc(block.get("label"))}</span></div>'
            f'<div class="card boards">{"".join(boards)}</div>')


def render_quote(block, t, ic, **kw):
    return f'<div class="note-block">{esc(block.get("text"))}</div>'



def render_lhb(block, t, ic, **kw):
    """龙虎榜：排名 / 名称 / 涨跌幅 / 净买入额 / 上榜原因。"""
    items = block.get("items", [])
    rows = []
    for i, it in enumerate(items):
        net = it.get("net")
        net_html = ""
        if isinstance(net, (int, float)):
            net_html = (f'<span class="net {pct_class(net)}">净买入 {net / 1e8:+.2f} 亿</span>')
        exp = esc(it.get("explain"))
        exp_html = f'<span class="exp">{exp}</span>' if exp else ""
        rows.append(f'<div class="lhb-row"><div class="lhb-top">'
                    f'<span class="rk">{it.get("rank", i + 1)}</span>'
                    f'<span class="nm">{esc(it.get("name"))}</span>'
                    f'<span class="pc {pct_class(it.get("pct"))}">{fmt_pct(it.get("pct"))}</span></div>'
                    f'<div class="lhb-sub">{net_html}{exp_html}</div></div>')
    foot = block.get("footnote") or ""
    foot_html = f'<div class="foot">{esc(foot)}</div>' if foot else ""
    return sec_head(block, t, ic) + f'<div class="card lhb">{"".join(rows)}{foot_html}</div>'

def build_groups(blocks):
    """按 nav 分组：天气单独在导航之上；其余按 nav 名归入面板（保持出现顺序）。"""
    groups = []
    for b in blocks:
        nav = EMOJI_RE.sub("", str(b.get("nav") or "")).strip()
        if b.get("type") == "weather" and not nav:
            nav = "天气"          # 天气默认作为第一个导航入口
        if not nav:
            continue
        if not groups or groups[-1]["label"] != nav:
            groups.append({"label": nav, "blocks": []})
        groups[-1]["blocks"].append(b)
    return [], groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", default="", choices=["", "morning", "evening"])
    ap.add_argument("--accent", default="")
    ap.add_argument("--img-mode", default="data", choices=["file", "data"])
    args = ap.parse_args()

    try:
        with open(args.data, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": f"读取失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    mode = args.mode or data.get("mode") or "morning"
    if mode != "evening":
        mode = "morning"
    base = "dark" if mode == "evening" else "light"
    meta = MODE_META[mode]

    cond = data.get("weather_cond", "")
    if not cond:
        for b in data.get("blocks", []):
            if b.get("type") == "weather" and b.get("rows"):
                cond = b["rows"][0].get("cond", "") or b["rows"][0].get("text", "")
                break
    accent = args.accent or ACCENTS[base][cond_family(cond)]
    t = dict(THEMES[base])
    t["_theme"] = base
    wicon = icon(f"w-{cond_family(cond)}", base, args.img_mode, size=15)

    weather_blocks, groups = build_groups([b for b in data.get("blocks", [])])

    REN = {"weather": render_weather, "market": render_market, "news": render_news,
           "schedule": render_schedule, "hot": render_hot, "quote": render_quote,
           "lhb": render_lhb}

    weather_html = "".join(REN[b["type"]](b, t, section_icon(b, base, args.img_mode, wicon))
                           for b in weather_blocks if b["type"] in REN)

    tabs, panels = [], []
    for gi, g in enumerate(groups):
        gicon = section_icon(g["blocks"][0], base, args.img_mode, wicon)
        gcc = cat_color(g["blocks"][0], base)
        tabs.append(f'<button class="tab{" active" if gi == 0 else ""}" data-i="{gi}" '
                    f'aria-controls="panel-{gi}" style="--cat:{gcc}">'
                    f'<span class="dot" style="background:{gcc}"></span>{gicon}{esc(g["label"])}</button>')
        inner = []
        half_buf = []

        def flush_half():
            if half_buf:
                inner.append('<div class="duo">' + "".join(half_buf) + '</div>')
                half_buf.clear()

        for b in g["blocks"]:
            fn = REN.get(b["type"])
            if not fn:
                continue
            ic = section_icon(b, base, args.img_mode, wicon)
            html = (fn(b, t, ic, small=(len(g["blocks"]) > 1), img_mode=args.img_mode)
                    if b["type"] == "schedule" else fn(b, t, ic, img_mode=args.img_mode))
            if b.get("half"):
                half_buf.append(f'<div class="half">{html}</div>')   # 每半块一个容器，别被 grid 拆散
                continue
            flush_half()
            inner.append(html)
        flush_half()
        panels.append(f'<section class="panel{" active" if gi == 0 else ""}" id="panel-{gi}">'
                      f'{"".join(inner)}</section>')

    date = data.get("date", "")
    weekday = data.get("weekday", "")
    date_line = f"{date} · {weekday}" if weekday else date
    subject = f"{meta['name']} · {date} {weekday}".strip()

    doc = f'''<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(subject)}</title>
<style>
:root {{ --bg:{t["bg"]};--card:{t["card"]};--card2:{t["card2"]};--text:{t["text"]};
  --muted:{t["muted"]};--body:{t["body"]};--line:{t["line"]};--accent:{accent};
  --up:{t["up"]};--down:{t["down"]};--shadow:{t["shadow"]}; }}
*{{box-sizing:border-box}}
/* 预留滚动条宽度：切换板块时竖向滚动条出现/消失不再把整页挤左 */
html{{scrollbar-gutter:stable;overflow-y:auto}}
body{{margin:0;background:var(--bg);color:var(--text);line-height:1.7;overflow-x:hidden;
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;}}
.wrap{{max-width:960px;margin:0 auto;padding:20px 16px 64px}}
header{{padding:6px 2px 18px;border-bottom:3px solid var(--accent)}}
.kicker{{font-size:10px;letter-spacing:3px;color:var(--accent);font-weight:700;display:flex;align-items:center;gap:8px}}
h1{{font-size:34px;margin:7px 0 2px;letter-spacing:-.5px}}
.date{{font-size:13px;color:var(--muted)}}
.card{{background:var(--card);border-radius:14px;padding:14px 16px;margin-bottom:14px;box-shadow:var(--shadow)}}
.weather{{margin-top:20px}}
.sec-label{{display:flex;align-items:center;gap:9px;font-size:13px;font-weight:700;margin:26px 2px 11px}}
.bar{{display:inline-block;width:3px;height:13px;border-radius:2px;flex:none}}
.tab .dot{{width:6px;height:6px;border-radius:50%;flex:none}}
.rank.top{{color:var(--cat-hot,#FF9F45);font-weight:700}}
.sec-label img{{vertical-align:-2px}}
.sec-label .note{{font-size:10px;letter-spacing:1px;color:var(--muted);font-weight:600}}
.sec-label.sub{{font-size:12px;margin:16px 2px 8px}}
.wrow{{display:flex;gap:12px;font-size:14px;padding:6px 0;border-bottom:1px solid var(--line)}}
.wrow:last-child{{border-bottom:0}}
.wcity{{width:52px;font-weight:700;flex:none}}
.wcond{{width:104px;color:var(--muted);flex:none;display:flex;align-items:center;gap:5px;white-space:nowrap}}
.wcond img{{display:block;flex:none}}
.wtext{{flex:1}}
.wnote{{color:var(--muted);font-size:13px}}
.walert{{color:var(--accent);font-size:13px;font-weight:600}}
nav#tabs{{position:sticky;top:0;z-index:9;display:flex;gap:8px;overflow-x:auto;
  padding:12px 2px 10px;margin:20px 0 6px;background:linear-gradient(var(--bg) 84%,transparent);
  border-top:1px solid var(--line);
  scroll-snap-type:x proximity;-webkit-overflow-scrolling:touch;scrollbar-width:thin}}
nav#tabs::-webkit-scrollbar{{height:5px}}
nav#tabs::-webkit-scrollbar-thumb{{background:var(--line);border-radius:99px}}
nav#tabs::-webkit-scrollbar-track{{background:transparent}}
.tab{{display:inline-flex;align-items:center;justify-content:center;gap:7px;cursor:pointer;border:0;
  flex:1 0 auto;min-width:max-content;scroll-snap-align:center;
  background:var(--card);color:var(--text);font:600 13px/1 inherit;padding:10px 18px;border-radius:999px;
  box-shadow:var(--shadow);opacity:.72;transition:.18s}}
.tab img{{opacity:.75}}
.tab:hover{{opacity:1;transform:translateY(-1px)}}
.tab.active{{background:var(--cat,var(--accent));color:#fff;opacity:1}}
.tab.active .dot{{background:rgba(255,255,255,.9)!important}}
.tab.active img{{filter:brightness(0) invert(1);opacity:.95}}
.panel{{display:none}}
.panel.active{{display:block}}
.panel.switching{{animation:fade .22s ease}}
@keyframes fade{{from{{opacity:0;transform:translateY(4px)}}to{{opacity:1;transform:none}}}}
.item{{display:block;text-decoration:none;color:inherit;padding:11px 0;border-bottom:1px solid var(--line)}}
.item:last-child{{border-bottom:0}}
.item:first-child{{padding-top:2px}}
.title{{font-size:15px;font-weight:600}}
.src{{font-size:12px;color:var(--muted);font-weight:400;margin-left:6px}}
.summary{{font-size:13px;color:var(--body);margin-top:3px}}
.pin{{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--accent);
  margin-right:7px;vertical-align:2px}}
table.market{{width:100%;border-collapse:collapse;font-size:14px}}
table.market td{{padding:6px 0;border-bottom:1px solid var(--line)}}
table.market tr:last-child td{{border-bottom:0}}
.mname{{font-weight:700}}
.mpoint{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
.mpoint .chg{{font-size:12px;margin-left:6px}}
.mpct{{text-align:right;width:86px;font-weight:700;font-variant-numeric:tabular-nums}}
.up{{color:var(--up)}} .down{{color:var(--down)}} .flat{{color:var(--muted)}}
.chips{{margin-top:9px;font-size:12px;color:var(--body);line-height:2}}
.chip-l{{color:var(--muted);margin-right:8px}}
.chip-n{{margin-right:14px;white-space:nowrap}}
.foot{{margin-top:10px;padding-top:9px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}}
.sched{{background:var(--card2);border-radius:10px;padding:11px 14px;margin-bottom:10px}}
.sched-label{{font-size:10px;font-weight:600;letter-spacing:1.5px;color:var(--muted);margin-bottom:5px}}
.sched-line{{font-size:13.5px;padding:2px 0}}
.muted{{color:var(--muted)}}
.boards{{display:grid;grid-template-columns:1fr;gap:14px}}
.duo{{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}}
.duo .half{{min-width:0}}
.duo .sec-label{{margin-top:0}}
.lhb-row{{padding:6px 0;border-bottom:1px solid var(--line)}}
.lhb-row:last-child{{border-bottom:0}}
.lhb-top{{font-size:13.5px;font-weight:600;display:flex;align-items:baseline;gap:6px}}
.lhb-top .rk{{color:var(--muted);font-size:12px;font-weight:400}}
.lhb-top .nm{{flex:1}}
.lhb-sub{{margin-top:2px;font-size:12px;color:var(--body);line-height:1.7}}
.lhb-sub .exp{{color:var(--muted)}}
.board-name{{font-size:12px;font-weight:700;margin-bottom:6px}}
.hot-row{{display:flex;gap:10px;align-items:baseline;text-decoration:none;color:inherit;padding:4px 0;font-size:14px}}
.rank{{color:var(--muted);font-size:12px;width:14px;flex:none;text-align:right}}
.hot-title{{flex:1}}
.hot-num{{color:var(--accent);font-size:12px;font-weight:700;flex:none}}
.note-block{{margin:26px 0 0;padding:4px 0 4px 14px;border-left:3px solid var(--accent);
  font-size:13px;color:var(--muted)}}
.head-row{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px}}
.head-left{{flex:none}}
.head-quote{{max-width:47%;text-align:right}}
.q-text{{font-size:13px;font-style:italic;color:var(--body);line-height:1.65}}
.q-sign{{font-size:12px;color:var(--muted);margin-top:6px}}
footer{{margin-top:26px;padding-top:18px;border-top:1px solid var(--line);font-size:14px;color:var(--body)}}
footer .sign{{display:block;text-align:right;color:var(--muted);font-size:13px;margin-top:8px}}
@media (max-width:640px){{
  .duo{{grid-template-columns:1fr}}
  .head-row{{flex-direction:column;align-items:flex-start;gap:10px}}
  .head-quote{{max-width:100%;text-align:left}}
}}
@media (min-width:640px){{ .boards{{grid-template-columns:1fr 1fr}} }}
</style></head>
<body><div class="wrap">
<header>
  <div class="head-row">
    <div class="head-left">
      <div class="kicker">{"".join([icon("sunrise" if mode == "morning" else "moon-stars", base, args.img_mode, 13), esc(meta["kicker"])])}</div>
      <h1>{esc(meta["name"])}</h1>
      <div class="date">{esc(date_line)}</div>
    </div>
    <div class="head-quote">
      <div class="q-text">{esc(data.get("quote"))}</div>
      <div class="q-sign">—— 爱你的悠悠</div>
    </div>
  </div>
</header>
<nav id="tabs">{"".join(tabs)}</nav>
{"".join(panels)}

</div>
<script>
(function(){{
  var tabs=[].slice.call(document.querySelectorAll('.tab'));
  var panels=[].slice.call(document.querySelectorAll('.panel'));
  function activate(i,push){{
    if(i<0||i>=tabs.length) return;
    tabs.forEach(function(b,k){{ b.classList.toggle('active',k===i); }});
    panels.forEach(function(p,k){{
      p.classList.toggle('active',k===i);
      p.classList.remove('switching');
      if(k===i){{ void p.offsetWidth; p.classList.add('switching'); }}
    }});
    var id='tab-'+(i+1);
    if(push){{ try{{ history.replaceState(null,'','#'+id); }}catch(e){{ location.hash=id; }} }}
    var nav=document.getElementById('tabs');
    var btn=tabs[i];
    if(nav&&btn&&nav.scrollWidth>nav.clientWidth){{
      nav.scrollTo({{left:btn.offsetLeft-16,behavior:'smooth'}});
    }}
    window.scrollTo({{top:0,behavior:'smooth'}});
  }}
  tabs.forEach(function(b){{ b.addEventListener('click',function(){{ activate(+b.dataset.i,true); }}); }});
  document.addEventListener('keydown',function(e){{
    var cur=tabs.findIndex(function(b){{return b.classList.contains('active');}});
    if(e.key==='ArrowRight') activate(Math.min(cur+1,tabs.length-1),true);
    if(e.key==='ArrowLeft') activate(Math.max(cur-1,0),true);
  }});
  var m=/^#tab-(\\d+)$/.exec(location.hash||'');
  if(m) activate(parseInt(m[1],10)-1,false);
}})();
</script>
</body></html>'''

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(json.dumps({"ok": True, "out": args.out, "mode": mode, "accent": accent,
                      "tabs": [g["label"] for g in groups],
                      "subject": subject}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
