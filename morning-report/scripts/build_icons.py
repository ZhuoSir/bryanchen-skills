#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载并生成邮件用图标（PNG，离线内嵌用）。

图标源：Tabler Icons（MIT 许可，免费可商用）outline 线性图标。
生成物：assets/icons/<theme>/<name>.png —— 3 倍图（42px），邮件里按 14px 显示。
  theme = light | dark（只影响图标线条颜色，与邮件底色调和）
  name  = 中性图标名 + w-<天气族>（天气图标按当日强调色着色）

一次性构建命令（联网）：
  python3 scripts/build_icons.py            # 缺哪张补哪张
  python3 scripts/build_icons.py --force    # 全部重新生成
依赖：cairosvg（仅构建时需要，发送时零依赖）
"""
import argparse
import io
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets", "icons", "png")
SRC = os.path.join(os.path.dirname(HERE), "assets", "icons", "src")

CDN = "https://cdn.jsdelivr.net/npm/@tabler/icons@3.31.0/icons/outline/{}.svg"
SIZE = 42          # 3 倍图，显示 14px
STROKE = "1.75"    # 线性图标线条粗细（Tabler 默认 2）

# 中性图标（跟随主题的中性灰）——板块小图标 + 头部标记 + 置顶
NEUTRAL = {
    "world": "#8a8a8e", "flag": "#8a8a8e", "cpu": "#8a8a8e",
    "ball-football": "#8a8a8e", "ball-basketball": "#8a8a8e", "flame": "#8a8a8e",
    "calendar-event": "#8a8a8e", "pin": "#8a8a8e",
    "chart-candle": "#8a8a8e", "coin": "#8a8a8e",
    "sunrise": "#8a8a8e", "moon-stars": "#8a8a8e",
}
NEUTRAL_DARK = {k: "#878c97" for k in NEUTRAL}

# 天气图标：族 → Tabler 名（按当日强调色着色，随天气变色）
WEATHER = {
    "clear": "sun", "cloudy": "cloud", "overcast": "mist",
    "rain": "cloud-rain", "thunder": "cloud-storm",
    "snow": "cloud-snow", "fog": "cloud-fog",
}

# 与 render_email.py 保持一致
ACCENTS = {
    "light": {"clear": "#F4511E", "cloudy": "#D97706", "overcast": "#8A8A8E",
              "rain": "#2563EB", "thunder": "#7C3AED", "snow": "#0891B2", "fog": "#94A3B8"},
    "dark": {"clear": "#e89167", "cloudy": "#d9a052", "overcast": "#959aa5",
             "rain": "#82a2f0", "thunder": "#a79af0", "snow": "#5cc0da", "fog": "#98a2b3"},
}


# 分类点缀色（导航/板块图标按栏目固定配色，任何天气下都有颜色）
CATEGORY_ICONS = {
    "weather":  {"icons": [], "light": "#0E7C86", "dark": "#55bdc9", "name": "天气"},
    "world":    {"icons": ["world"], "light": "#3B5BDB", "dark": "#93a5e8", "name": "国际"},
    "china":    {"icons": ["flag"], "light": "#C2255C", "dark": "#ea8cab", "name": "国内"},
    "finance":  {"icons": ["chart-candle", "coin"], "light": "#B7791F", "dark": "#dcb05c", "name": "财经"},
    "ai":       {"icons": ["cpu"], "light": "#7048E8", "dark": "#a89be6", "name": "AI"},
    "sports":   {"icons": ["ball-football", "ball-basketball"], "light": "#0E8A4F", "dark": "#57c087", "name": "体育"},
    "hot":      {"icons": ["flame"], "light": "#E8590C", "dark": "#e89b5e", "name": "热榜"},
    "watch":    {"icons": ["star"], "light": "#DB2777", "dark": "#e28db6", "name": "特别关注"},
}


def fetch_svg(name):
    """下载 SVG 原文（带本地缓存）。"""
    os.makedirs(SRC, exist_ok=True)
    cache = os.path.join(SRC, name + ".svg")
    if os.path.exists(cache) and os.path.getsize(cache) > 0:
        return open(cache, encoding="utf-8").read()
    with urllib.request.urlopen(CDN.format(name), timeout=20) as r:
        svg = r.read().decode("utf-8")
    with open(cache, "w", encoding="utf-8") as f:
        f.write(svg)
    return svg


def tint(svg, color):
    """把 currentColor 换成目标颜色，并按 SIZE 放大。"""
    svg = svg.replace("currentColor", color)
    svg = svg.replace('width="24"', f'width="{SIZE}"').replace('height="24"', f'height="{SIZE}"')
    svg = svg.replace('stroke-width="2"', f'stroke-width="{STROKE}"')
    return svg


def render_png(svg, out_path):
    import cairosvg
    png = cairosvg.svg2png(bytestring=svg.encode("utf-8"),
                           output_width=SIZE, output_height=SIZE)
    with open(out_path, "wb") as f:
        f.write(png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="已存在的也重新生成")
    args = ap.parse_args()

    try:
        import cairosvg  # noqa: F401
    except ImportError:
        print("需要 cairosvg 才能构建图标：pip install cairosvg", file=sys.stderr)
        sys.exit(1)

    jobs = []  # (theme, out_name, tabler_name, color)
    for name, color in NEUTRAL.items():
        jobs.append(("light", name, name, color))
    for name, color in NEUTRAL_DARK.items():
        jobs.append(("dark", name, name, color))
    for theme in ("light", "dark"):
        for fam, tabler in WEATHER.items():
            jobs.append((theme, f"w-{fam}", tabler, ACCENTS[theme][fam]))

    # 分类彩色图标：cat-<分类>-<图标>.png
    for cat, cfg in CATEGORY_ICONS.items():
        for tabler in cfg["icons"]:
            for theme in ("light", "dark"):
                jobs.append((theme, f"cat-{cat}-{tabler}", tabler, cfg[theme]))

    made = skipped = 0
    for theme, out_name, tabler, color in jobs:
        out_dir = os.path.join(ASSETS, theme)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, out_name + ".png")
        if os.path.exists(out_path) and not args.force:
            skipped += 1
            continue
        try:
            render_png(tint(fetch_svg(tabler), color), out_path)
            made += 1
        except Exception as e:  # 网络/渲染异常
            print(f"失败 {theme}/{out_name} ({tabler}): {e}", file=sys.stderr)
    print(f"图标生成完成：新建/更新 {made} 张，跳过 {skipped} 张 → {ASSETS}")


if __name__ == "__main__":
    main()
