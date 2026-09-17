#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把晨报/晚报内容 JSON 渲染成**固定样式**的 H5 邮件（纯标准库，零依赖）。

样式由本脚本 + templates/email.html 唯一决定，模型只负责填内容，
不参与任何样式决策 —— 因此每次发送的排版、配色、字号完全一致。

· 配色：晨报浅色底、按天气自动选强调色；晚报恒定暗黑底（强调色自动调亮）
· 图标：Tabler 线性图标 PNG（assets/icons/），无 emoji；内容里误留的 emoji 会被剥离

用法：
  python3 scripts/render_email.py --data /tmp/report.json --out /tmp/report.html
  python3 scripts/render_email.py --data /tmp/report.json --out /tmp/report.html --mode evening
  python3 scripts/render_email.py --data /tmp/report.json --out /tmp/report.html --accent "#F4511E"
  python3 scripts/render_email.py --data ... --out ... --img-mode data   # 图标转 base64 内嵌

--img-mode：
  file（默认）图标用绝对路径引用，交 send_mail.py 以 CID 内嵌（推荐，Gmail 可显示）
  data        图标转 base64 data URI（邮件自包含；Gmail 会拦截 data URI，Apple Mail 可显示）

数据 JSON 结构（除 blocks 外都可选）：
{
  "mode": "morning" | "evening",         # 缺省 morning
  "date": "2025-09-05",
  "weekday": "周五",
  "weather_cond": "晴",                   # 决定强调色；不给则取天气板块首行 cond，再不给按"阴"
  "quote": "今日寄语",
  "blocks": [
    {"type": "weather", "label": "今日天气", "en": "WEATHER",
     "rows": [{"city": "北京", "cond": "晴", "text": "16~28°", "note": "现在 24° · 体感 25°", "alert": "建议带伞"}]},

    {"type": "news", "label": "国际新闻", "en": "WORLD",
     "items": [{"title": "...", "summary": "...", "url": "https://...", "source": "量子位", "pinned": true}]},

    {"type": "schedule", "label": "足球", "en": "FOOTBALL", "note": "虎扑实时热帖",
     "schedule": [{"time": "19:35", "text": "中超 · 上海海港 vs 青岛海牛", "state": "未开始"}],
     "items": [{"title": "...", "summary": "...", "url": "https://..."}]},

    {"type": "hot", "label": "全网热榜", "en": "TRENDING",
     "boards": [{"board": "微博热搜", "en": "WEIBO", "items": [{"title": "...", "url": "https://...", "hot": "114万"}]}]}
  ]
}

输出 JSON：{"ok": true, "out": "...", "mode": "...", "accent": "#...", "subject": "..."}
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
TEMPLATE = os.path.join(ROOT, "templates", "email.html")
ICONS = os.path.join(ROOT, "assets", "icons", "png")

# ── 主题（唯一定义处，改这里即改全局样式） ─────────────────────────────
THEMES = {
    "light": {
        "BG": "#f6f6f5", "SHEET": "#ffffff", "TEXT": "#1c1c1e", "MUTED": "#8a8a8e",
        "BODY_MUTED": "#6c6c70", "LINE": "#efefed", "CARD": "#f6f6f5", "QUOTE_TEXT": "#3a3a3c",
        "UP": "#D93025", "DOWN": "#0E8A4F",
    },
    "dark": {
        "BG": "#0a0a0c", "SHEET": "#141417", "TEXT": "#ededf0", "MUTED": "#8d8d96",
        "BODY_MUTED": "#a3a3ac", "LINE": "#26262c", "CARD": "#1c1c21", "QUOTE_TEXT": "#cfcfd6",
        "UP": "#FF6B60", "DOWN": "#34D399",
    },
}

# 天气 → 强调色（用户规则：晴=橘红，阴=白灰；其余按语义补全）
ACCENTS = {
    "light": {
        "clear": "#F4511E", "cloudy": "#D97706", "overcast": "#8A8A8E",
        "rain": "#2563EB", "thunder": "#7C3AED", "snow": "#0891B2", "fog": "#94A3B8",
    },
    "dark": {
        "clear": "#FF7A45", "cloudy": "#F0A742", "overcast": "#A1A1AA",
        "rain": "#6B8CFF", "thunder": "#A78BFA", "snow": "#38BDF8", "fog": "#A8B4C4",
    },
}

# 关键词 → 天气族（顺序即优先级：雷 > 雪 > 雨 > 雾霾 > 晴 > 多云 > 阴）
COND_RULES = [
    ("thunder", ("雷", "thunder", "storm")),
    ("snow", ("雪", "snow", "sleet", "blizzard")),
    ("rain", ("雨", "rain", "drizzle", "shower")),
    ("fog", ("雾", "霾", "fog", "haze", "mist", "smog")),
    ("clear", ("晴", "clear", "sunny", "sun")),
    ("cloudy", ("多云", "cloudy", "partly")),
    ("overcast", ("阴", "overcast", "cloud")),
]

# 板块中文名 → (英文小标签, 图标名)
# 栏目点缀色（与 build_icons.py 的 CATEGORY_ICONS 对应；任何天气下都有颜色）
CAT_COLORS = {
    "light": {"weather": "#0E7C86", "world": "#3B5BDB", "china": "#C2255C",
              "finance": "#B7791F", "ai": "#7048E8", "sports": "#0E8A4F", "hot": "#E8590C", "watch": "#DB2777"},
    "dark": {"weather": "#4DD0E1", "world": "#8FA2FF", "china": "#FF7AA2",
             "finance": "#FFC13B", "ai": "#B197FC", "sports": "#4ADE80", "hot": "#FF9F45", "watch": "#F472B6"},
}
# 天气现象点缀色（晴暖 / 雨蓝 / 云灰 / 雷紫 / 雪青）
COND_COLORS = {
    "light": {"clear": "#D97706", "cloudy": "#8A8A8E", "overcast": "#8A8A8E",
              "rain": "#2563EB", "thunder": "#7C3AED", "snow": "#0891B2", "fog": "#94A3B8"},
    "dark": {"clear": "#FFC13B", "cloudy": "#A1A1AA", "overcast": "#A1A1AA",
             "rain": "#7AA2FF", "thunder": "#B197FC", "snow": "#5AD1E8", "fog": "#A8B4C4"},
}
CAT_RULES = [("天气", "weather"), ("国际", "world"), ("国内", "china"), ("大盘", "finance"),
             ("财经", "finance"), ("AI", "ai"), ("人工智能", "ai"), ("足球", "sports"),
             ("篮球", "sports"), ("体育", "sports"), ("热榜", "hot"), ("热搜", "hot"), ("关注", "watch"), ("WATCH", "watch")]

SECTION_META = [
    (("天气",), "WEATHER", "w-auto"),
    (("国际",), "WORLD", "world"),
    (("国内",), "CHINA", "flag"),
    (("人工智能", "AI", "ai"), "AI", "cpu"),
    (("足球",), "FOOTBALL", "ball-football"),
    (("篮球",), "BASKETBALL", "ball-basketball"),
    (("热榜", "热搜", "热点"), "TRENDING", "flame"),
    (("特别关注", "关注"), "WATCH", "star"),
    (("龙虎榜", "席位"), "LHB", "coin"),
    (("大盘", "行情", "财经", "A股", "股市"), "MARKET", "chart-candle"),
]

MODE_META = {
    "morning": {"name": "晨报", "kicker": "MORNING REPORT", "icon": "sunrise"},
    "evening": {"name": "晚报", "kicker": "EVENING REPORT", "icon": "moon-stars"},
}

# emoji / 符号图标剥除（保留 · ° ~ — 等排版字符）
EMOJI_RE = re.compile(
    "[" "\U0001F000-\U0001FAFF" "\U00002600-\U000027BF" "\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF" "\U0000FE0F" "\U0000200D" "\U00002190-\U000021FF" "]+"
)

IMG_CACHE = {}


def cond_family(cond):
    c = (cond or "").strip().lower()
    if not c:
        return "overcast"
    for family, keys in COND_RULES:
        if any(k in c for k in keys):
            return family
    return "overcast"


def strip_emoji(s):
    return EMOJI_RE.sub("", str(s or "")).strip()


def esc(s):
    """转义 + 去 emoji，所有文本出口都走这里。"""
    return html_mod.escape(strip_emoji(s), quote=True)


def icon(name, theme, img_mode, size=14, alt=""):
    """返回图标 <img> 标签；图标缺失时返回空串（版面自动退化为纯文字）。"""
    if not name:
        return ""
    path = os.path.join(ICONS, theme, name + ".png")
    if not os.path.exists(path):
        return ""
    if img_mode == "data":
        if path not in IMG_CACHE:
            with open(path, "rb") as f:
                IMG_CACHE[path] = "data:image/png;base64," + base64.b64encode(f.read()).decode()
        src = IMG_CACHE[path]
    else:
        src = path
    return (f'<img src="{src}" width="{size}" height="{size}" alt="{html_mod.escape(alt)}" '
            f'style="border:0;outline:none;text-decoration:none;vertical-align:-2px;'
            f'display:inline-block;margin-right:7px;">')


def cat_of(block):
    """块 → 栏目 key（决定点缀色与彩色图标）。"""
    zh = str(block.get("nav") or "") + str(block.get("label") or "")
    for key, c in CAT_RULES:
        if key in zh:
            return c
    return ""


def cat_color(block, t):
    c = cat_of(block)
    return CAT_COLORS[t["_theme"]].get(c, t["MUTED"]) if c else t["MUTED"]


def cat_icon_name(block):
    """栏目彩色图标文件名（不存在时回退中性图标）。"""
    c = cat_of(block)
    zh = str(block.get("label") or "")
    if c == "world":
        return "cat-world-world"
    if c == "china":
        return "cat-china-flag"
    if c == "finance":
        return "cat-finance-coin" if "龙虎榜" in zh else "cat-finance-chart-candle"
    if c == "ai":
        return "cat-ai-cpu"
    if c == "sports":
        return "cat-sports-ball-basketball" if "篮球" in zh else "cat-sports-ball-football"
    if c == "hot":
        return "cat-hot-flame"
    return ""


def section_meta(block, theme, img_mode, weather_icon):
    """板块 → (英文标签, 图标 img)。"""
    zh = strip_emoji(block.get("label"))
    en = strip_emoji(block.get("en"))
    ic = ""
    for keys, en_default, ic_name in SECTION_META:
        if any(k in zh for k in keys):
            if not en:
                en = en_default
            ic = weather_icon if ic_name == "w-auto" else icon(ic_name, theme, img_mode)
            break
    # 栏目彩色图标优先（天气保留按天气着色的图标）
    if cat_of(block) and cat_of(block) != "weather":
        colored = icon(cat_icon_name(block), theme, img_mode)
        if colored:
            ic = colored
    return en, ic


def label_html(block, t, img_mode, weather_icon):
    en, ic = section_meta(block, t["_theme"], img_mode, weather_icon)
    en_html = (f'<span style="font-size:10px;font-weight:600;color:{t["MUTED"]};'
               f'letter-spacing:1.5px;margin-left:8px;vertical-align:1px;">'
               f'{html_mod.escape(en)}</span>' if en else "")
    anchor = block.get("_anchor") or ""
    anchor_html = (f'<a name="{anchor}" id="{anchor}" style="display:block;height:0;"></a>'
                   if anchor else "")
    cc = cat_color(block, t)
    bar = (f'<span style="display:inline-block;width:3px;height:13px;background-color:{cc};'
           f'border-radius:2px;margin-right:9px;vertical-align:-2px;"></span>')
    if en and cc != t["MUTED"]:
        en_html = (f'<span style="font-size:10px;font-weight:600;color:{cc};opacity:.85;'
                   f'letter-spacing:1.5px;margin-left:8px;vertical-align:1px;">'
                   f'{html_mod.escape(en)}</span>')
    return (f'<div style="margin-bottom:11px;">{anchor_html}{bar}{ic}'
            f'<span style="font-size:13px;font-weight:700;color:{t["TEXT"]};letter-spacing:0.5px;">'
            f'{html_mod.escape(strip_emoji(block.get("label")))}</span>{en_html}</div>')


def annotate_nav(blocks):
    """按块的 nav 字段生成导航分组（同名的块归一组，首块承载锚点）。

    新增模块只要给块加 "nav": "xxx"，导航会自动多一个入口 —— 不需要改模板。
    天气块与没有 nav 的块不参与导航。
    """
    groups, seen = [], {}
    for b in blocks:
        nav = strip_emoji(b.get("nav"))
        if b.get("type") == "weather" and not nav:
            nav = "天气"          # 天气默认作为导航第一个入口
        if not nav:
            continue
        if nav in seen:
            b["_anchor"] = ""
            continue
        anchor = f"nav-{len(groups) + 1}"
        seen[nav] = anchor
        b["_anchor"] = anchor
        groups.append({"label": nav, "anchor": anchor, "cat": cat_of(b)})
    return groups


def render_nav(groups, t, mode):
    """导航条：胶囊标签，点击跳到对应板块（邮件客户端对页内锚点支持不一，但可读性/索引价值一致）。"""
    if len(groups) < 2:
        return ""
    cells = []
    for g in groups:
        cc = CAT_COLORS[t["_theme"]].get(g.get("cat"), t["MUTED"])
        dot = (f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;'
               f'background-color:{cc};margin-right:6px;vertical-align:1px;"></span>')
        cell = (f'<a href="#{g["anchor"]}" style="display:inline-block;padding:7px 10px;'
                f'border-radius:999px;background-color:{t["CARD"]};color:{t["TEXT"]};font-size:12px;'
                f'font-weight:600;text-decoration:none;letter-spacing:0.2px;white-space:nowrap;">'
                f'{dot}{html_mod.escape(g["label"])}</a>')
        cells.append(f'<td align="center" style="padding:0 4px 8px;">{cell}</td>')
    pills = [f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;">'
             f'<tr>{"".join(cells)}</tr></table>']
    kicker = "今晚看这些" if mode == "evening" else "今天看这些"
    return (f'    <div style="margin-top:24px;padding-top:14px;border-top:1px solid {t["LINE"]};">\n'
            f'      <div style="font-size:10px;letter-spacing:2px;color:{t["MUTED"]};'
            f'font-weight:600;margin-bottom:9px;">{kicker} · 点击直达</div>\n'
            f'      <div>{"".join(pills)}</div>\n    </div>\n')


def render_weather(block, t):
    rows = []
    raw_rows = block.get("rows", [])
    for i, r in enumerate(raw_rows):
        border = "" if i == len(raw_rows) - 1 else f'border-bottom:1px solid {t["LINE"]};'
        cond = strip_emoji(r.get("cond"))
        ric = icon(f"w-{cond_family(cond)}", t["_theme"], t["_img_mode"], size=15)
        cc = COND_COLORS[t["_theme"]].get(cond_family(cond), t["MUTED"])
        if ric:
            ric = ric.replace('margin-right:7px', 'margin-right:5px')
        cond_html = (f'<span style="color:{cc};font-size:13px;white-space:nowrap;font-weight:600;">{html_mod.escape(cond)}</span>'
                     if cond else "")
        note = ""
        if r.get("note"):
            note = (f'<span class="weather-note" style="color:{t["MUTED"]};font-size:13px;">'
                    f'&nbsp;· {esc(r["note"])}</span>')
        alert = ""
        if r.get("alert"):
            alert = (f'<span class="weather-note" style="color:{t["ACCENT"]};font-size:13px;font-weight:600;">'
                     f'· {esc(r["alert"])}</span>')
        rows.append(
            f'''      <tr>
        <td class="weather-td" style="padding:7px 0;font-size:14px;{border}width:22%;white-space:nowrap;"><strong>{esc(r.get("city"))}</strong></td>
        <td class="weather-td" style="padding:7px 0;font-size:14px;{border}width:32%;white-space:nowrap;">{ric}{cond_html}</td>
        <td style="padding:7px 0;font-size:14px;{border}">{esc(r.get("text"))}{note}{alert}</td>
      </tr>''')
    return (f'    <div style="margin-top:28px;">\n      {label_html(block, t, t["_img_mode"], t["_weather_icon"])}\n'
            f'      <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">\n'
            + "\n".join(rows) + '\n      </table>\n    </div>\n')


def render_news_item(it, t):
    src = ""
    if it.get("source"):
        src = (f'<span style="font-size:12px;color:{t["MUTED"]};font-weight:400;">'
               f'&nbsp;· {esc(it["source"])}</span>')
    pin = icon("pin", t["_theme"], t["_img_mode"], size=12) if it.get("pinned") else ""
    summary = ""
    if it.get("summary"):
        summary = (f'\n        <div style="font-size:13px;color:{t["BODY_MUTED"]};margin-top:3px;">'
                   f'{esc(it["summary"])}</div>')
    return (f'      <div style="margin-bottom:16px;">\n'
            f'        {pin}<a href="{esc(it.get("url", "#"))}" style="color:{t["TEXT"]};text-decoration:none;font-size:15px;font-weight:600;">{esc(it.get("title"))}</a>{src}{summary}\n'
            f'      </div>')


def render_news(block, t):
    items = "\n".join(render_news_item(i, t) for i in block.get("items", []))
    return (f'    <div style="margin-top:30px;">\n      {label_html(block, t, t["_img_mode"], t["_weather_icon"])}\n'
            f'{items}\n    </div>\n')


def render_schedule(block, t):
    sched = ""
    if block.get("schedule"):
        cal = icon("calendar-event", t["_theme"], t["_img_mode"], size=12)
        lines = []
        for m in block["schedule"]:
            time = f'<strong>{esc(m.get("time"))}</strong> ' if m.get("time") else ""
            state = ""
            if m.get("state"):
                state = f'<span style="color:{t["MUTED"]};font-size:13px;">&nbsp;· {esc(m["state"])}</span>'
            lines.append(f'        <div style="font-size:14px;padding:2px 0;">{time}{esc(m.get("text"))}{state}</div>')
        sched_head = (f'<div style="font-size:10px;font-weight:600;letter-spacing:1.5px;color:{t["MUTED"]};'
                      f'margin-bottom:6px;">{cal}'
                      f'{html_mod.escape(strip_emoji(block.get("schedule_label")) or "今日赛程")}</div>')
        sched = (f'      <div class="card-pad" style="background-color:{t["CARD"]};border-radius:10px;padding:12px 16px;margin-bottom:16px;">\n'
                 f'        {sched_head}\n' + "\n".join(lines) + '\n      </div>\n')
    note = ""
    if block.get("note"):
        note = (f'<span style="font-size:10px;font-weight:600;letter-spacing:1.5px;'
                f'color:{t["MUTED"]};margin-left:8px;vertical-align:1px;">{esc(block["note"])}</span>')
    items = "\n".join(render_news_item(i, t) for i in block.get("items", []))
    lbl = label_html(block, t, t["_img_mode"], t["_weather_icon"])
    if note:
        lbl = lbl.replace("</div>", note + "</div>")
    return (f'    <div style="margin-top:30px;">\n      {lbl}\n'
            f'{sched}{items}\n    </div>\n')


def render_hot(block, t):
    boards = []
    for b in block.get("boards", []):
        en = strip_emoji(b.get("en"))
        if not en:
            for keys, en_default, _ic in SECTION_META:
                if any(k in strip_emoji(b.get("board")) for k in keys):
                    en = en_default
                    break
        en_html = (f'<span style="font-size:10px;font-weight:600;color:{t["MUTED"]};letter-spacing:1.5px;'
                   f'margin-left:8px;">{html_mod.escape(en)}</span>' if en else "")
        head = (f'<div style="font-size:12px;font-weight:700;color:{t["TEXT"]};margin:12px 0 5px;">'
                f'{esc(b.get("board"))}{en_html}</div>')
        rows = []
        for idx, it in enumerate(b.get("items", []), 1):
            hot = ""
            if it.get("hot"):
                hot = (f'<span style="color:{t["ACCENT"]};font-size:12px;font-weight:700;">'
                       f'&nbsp;{esc(it["hot"])}</span>')
            rc = cat_color(block, t) if idx <= 3 else t["MUTED"]
            rw = "700" if idx <= 3 else "400"
            rows.append(f'        <div style="font-size:14px;padding:3px 0;">'
                        f'<span style="color:{rc};font-size:12px;font-weight:{rw};">{idx}</span>&nbsp;&nbsp;'
                        f'<a href="{esc(it.get("url", "#"))}" style="color:{t["TEXT"]};text-decoration:none;">'
                        f'{esc(it.get("title"))}</a>{hot}</div>')
        boards.append(head + "\n" + "\n".join(rows))
    body = "\n".join(boards)
    return (f'    <div style="margin-top:30px;">\n      {label_html(block, t, t["_img_mode"], t["_weather_icon"])}\n'
            f'      <div class="card-pad" style="background-color:{t["CARD"]};border-radius:10px;padding:14px 18px;">\n'
            f'{body}\n      </div>\n    </div>\n')


def render_quote(block, t):
    return (f'    <div style="margin-top:26px;padding:2px 0 2px 14px;border-left:3px solid {t["ACCENT"]};">\n'
            f'      <div style="font-size:14px;color:{t["BODY_MUTED"]};">{esc(block.get("text"))}</div>\n    </div>\n')


def fmt_pct(v):
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return ""


def pct_color(v, t):
    """A股惯例：红涨绿跌。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return t["MUTED"]
    if f > 0:
        return t["UP"]
    if f < 0:
        return t["DOWN"]
    return t["MUTED"]


def render_market(block, t):
    """A股大盘：指数表（红涨绿跌）+ 成交额 + 领涨/领跌板块。half=true 时用于左右两栏。

    block: {label, en, indices:[{name,point,chg,pct}], footnote, up:[{name,pct}], down:[{name,pct}]}
    """
    half = bool(block.get("half"))
    fs = "13px" if half else "14px"
    pct_w = "66px" if half else "78px"
    rows = []
    idx = block.get("indices", [])
    for i, it in enumerate(idx):
        border = "" if i == len(idx) - 1 else f'border-bottom:1px solid {t["LINE"]};'
        pt = it.get("point")
        if isinstance(pt, (int, float)):
            try:
                pt = f"{float(pt):,.2f}"
            except (TypeError, ValueError):
                pt = esc(pt)
        else:
            pt = esc(pt)
        chg = it.get("chg")
        chg_html = ""
        if isinstance(chg, (int, float)):
            chg_html = (f'<span style="color:{pct_color(it.get("pct"), t)};font-size:12px;">'
                        f'&nbsp;{chg:+.2f}</span>')
        rows.append(
            f'''      <tr>
        <td style="padding:6px 0;font-size:14px;{border}"><strong>{esc(it.get("name"))}</strong></td>
        <td class="market-td" style="padding:6px 0;font-size:{fs};{border}text-align:right;white-space:nowrap;">{pt}{chg_html}</td>
        <td class="market-td" style="padding:6px 0;font-size:{fs};{border}text-align:right;white-space:nowrap;width:{pct_w};color:{pct_color(it.get("pct"), t)};font-weight:700;">{fmt_pct(it.get("pct"))}</td>
      </tr>''')
    table = ("      <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\">\n"
             + "\n".join(rows) + "\n      </table>\n") if rows else ""

    def chips(items, is_up):
        if not items:
            return ""
        parts = []
        for it in items:
            parts.append(f'<span style="white-space:nowrap;">{esc(it.get("name"))} '
                         f'<span style="color:{pct_color(it.get("pct"), t)};font-weight:600;">'
                         f'{fmt_pct(it.get("pct"))}</span></span>')
        label = "领涨" if is_up else "领跌"
        return (f'      <div style="margin-top:9px;font-size:12px;color:{t["BODY_MUTED"]};line-height:2;">'
                f'<span style="color:{t["MUTED"]};white-space:nowrap;display:inline-block;'
                f'margin-right:8px;">{label}</span>'
                + '&nbsp; '.join(parts) + '</div>\n')

    foot = block.get("footnote") or ""
    foot_html = ""
    if foot:
        foot_html = (f'      <div style="margin-top:10px;padding-top:9px;border-top:1px solid {t["LINE"]};'
                     f'font-size:12px;color:{t["MUTED"]};">{esc(foot)}</div>\n')
    mt = "0" if half else "30px"
    return (f'    <div style="margin-top:{mt};">\n'
            f'      {label_html(block, t, t["_img_mode"], t["_weather_icon"])}\n'
            f'      <div class="card-pad" style="background-color:{t["CARD"]};border-radius:10px;padding:12px 16px;">\n'
            f'{table}{chips(block.get("up"), True)}{chips(block.get("down"), False)}{foot_html}'
            f'      </div>\n    </div>\n')



def render_lhb(block, t):
    """龙虎榜：排名 / 名称 / 涨跌幅 / 净买入额 / 上榜原因。half=true 时与大盘并排。"""
    mt = "0" if block.get("half") else "30px"
    rows = []
    items = block.get("items", [])
    for i, it in enumerate(items):
        border = "" if i == len(items) - 1 else f'border-bottom:1px solid {t["LINE"]};'
        net = it.get("net")
        net_html = ""
        if isinstance(net, (int, float)):
            col = t["UP"] if net > 0 else t["DOWN"]
            net_html = (f'<span style="color:{col};font-size:12px;font-weight:600;">'
                        f'净买入 {net / 1e8:+.2f} 亿</span>')
        exp = esc(it.get("explain"))
        exp_html = f'<span style="color:{t["MUTED"]};font-size:12px;"> · {exp}</span>' if exp else ""
        rows.append(
            f'      <div style="padding:6px 0;{border}">'
            f'<div style="font-size:13.5px;font-weight:600;">'
            f'<span style="color:{t["MUTED"]};font-size:12px;font-weight:400;">{it.get("rank", i + 1)}</span> '
            f'{esc(it.get("name"))} '
            f'<span style="color:{pct_color(it.get("pct"), t)};font-weight:700;">{fmt_pct(it.get("pct"))}</span>'
            f'</div><div style="margin-top:2px;">{net_html}{exp_html}</div></div>')
    foot = block.get("footnote") or ""
    foot_html = (f'      <div style="margin-top:9px;padding-top:8px;border-top:1px solid {t["LINE"]};'
                  f'font-size:11px;color:{t["MUTED"]};">{esc(foot)}</div>\n' if foot else "")
    return (f'    <div style="margin-top:{mt};">\n'
            f'      {label_html(block, t, t["_img_mode"], t["_weather_icon"])}\n'
            f'      <div class="card-pad" style="background-color:{t["CARD"]};border-radius:10px;padding:12px 16px;">\n'
            + "\n".join(rows) + f'\n{foot_html}      </div>\n    </div>\n')

RENDERERS = {"weather": render_weather, "news": render_news,
             "schedule": render_schedule, "hot": render_hot, "quote": render_quote,
             "market": render_market, "lhb": render_lhb}


def build_theme(mode, cond, accent_override=None):
    base = "dark" if mode == "evening" else "light"
    t = dict(THEMES[base])
    t["ACCENT"] = accent_override or ACCENTS[base][cond_family(cond)]
    t["_theme"] = base
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="内容 JSON 路径")
    ap.add_argument("--out", required=True, help="输出 HTML 路径")
    ap.add_argument("--mode", default="", choices=["", "morning", "evening"],
                    help="缺省读 data.mode，再缺省 morning")
    ap.add_argument("--accent", default="", help="强制强调色（不给则按天气自动选）")
    ap.add_argument("--img-mode", default="file", choices=["file", "data"],
                    help="file=绝对路径交给 send_mail 内嵌 CID；data=base64 内嵌")
    ap.add_argument("--template", default=TEMPLATE)
    args = ap.parse_args()

    try:
        with open(args.data, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": f"读取/解析数据失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    mode = args.mode or data.get("mode") or "morning"
    if mode != "evening":
        mode = "morning"
    meta = MODE_META[mode]

    # 强调色：data.weather_cond → 天气板块首行 cond → 阴
    cond = data.get("weather_cond", "")
    if not cond:
        for b in data.get("blocks", []):
            if b.get("type") == "weather" and b.get("rows"):
                cond = b["rows"][0].get("cond", "") or b["rows"][0].get("text", "")
                break
    t = build_theme(mode, cond, args.accent or None)
    t["_img_mode"] = args.img_mode
    # 天气板块图标 = 当日天气族（着强调色）
    t["_weather_icon"] = icon(f"w-{cond_family(cond)}", t["_theme"], args.img_mode)

    # 邮件版不渲染导航：多数客户端（163/QQ/Gmail）会拦截页内锚点，点了没反应 → 直接竖版堆叠。
    # 导航只在 H5（render_h5.py）里提供，那里是真切换。
    raw_blocks = [b for b in data.get("blocks", []) if RENDERERS.get(b.get("type"))]
    annotate_nav(raw_blocks)        # 仍标锚点（部分客户端可用），但不生成导航条
    nav_html = ""                   # 邮件不出导航条

    # 邮件一律单栏竖版：不渲染导航、不做左右两栏
    # （两栏表格在窄屏下会被不可断行内容撑宽，导致手机端横向拉扯；两栏只在 H5 里提供）
    blocks = [RENDERERS[b["type"]](b, t) for b in raw_blocks]
    # 邮件不插导航条

    date = data.get("date", "")
    weekday = data.get("weekday", "")
    date_line = f"{date} · {weekday}" if weekday else date

    try:
        with open(args.template, encoding="utf-8") as f:
            out = f.read()
    except OSError as e:
        print(json.dumps({"ok": False, "error": f"模板读取失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    head_icon = icon(meta["icon"], t["_theme"], args.img_mode, size=13)
    repl = {
        "{{SUBJECT}}": html_mod.escape(f"{meta['name']} · {date} {weekday}".strip()),
        "{{BG}}": t["BG"], "{{SHEET}}": t["SHEET"],
        "{{TEXT}}": t["TEXT"], "{{MUTED}}": t["MUTED"], "{{BODY_MUTED}}": t["BODY_MUTED"],
        "{{LINE}}": t["LINE"], "{{CARD}}": t["CARD"], "{{QUOTE_TEXT}}": t["QUOTE_TEXT"],
        "{{ACCENT}}": t["ACCENT"], "{{KICKER}}": meta["kicker"], "{{HEAD_ICON}}": head_icon,
        "{{TITLE}}": meta["name"], "{{DATE}}": esc(date_line),
        "{{BLOCKS}}": "\n".join(blocks).rstrip(),
        "{{QUOTE}}": esc(data.get("quote")),
    }
    for k, v in repl.items():
        out = out.replace(k, v)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(out)

    print(json.dumps({"ok": True, "out": args.out, "mode": mode,
                      "cond": cond or "阴(默认)", "accent": t["ACCENT"],
                      "img_mode": args.img_mode,
                      "subject": f"{meta['name']} · {date} {weekday}".strip()},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
