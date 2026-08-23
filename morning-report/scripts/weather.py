#!/usr/bin/env python3
"""morning-report: 国内主要城市天气预报（零依赖，Python 标准库，免 API Key）。

主源 Open-Meteo（一次请求返回全部城市，~1s）；兜底 wttr.in（逐城请求）。
WMO weather_code 已映射为中文描述 + emoji。

用法:
    python3 weather.py              # 今日天气（晨报）
    python3 weather.py --tomorrow   # 明日天气（晚报）
输出:
    stdout JSON: {"date": "...", "source": "...",
                  "cities": [{"city","now":{...},"today"|"tomorrow":{...}}, ...]}
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 晨报关注城市（名称, 纬度, 经度）
CITIES = [
    ("北京", 39.9042, 116.4074),
    ("深圳", 22.5431, 114.0579),
    ("上海", 31.2304, 121.4737),
    ("杭州", 30.2741, 120.1551),
    ("通辽", 43.6529, 122.2434),
    ("崇礼", 40.9746, 115.2826),  # 张家口市崇礼区
]

# WMO weather code -> (中文, emoji)
WMO = {
    0: ("晴", "☀️"), 1: ("大致晴", "🌤️"), 2: ("多云", "⛅"), 3: ("阴", "☁️"),
    45: ("雾", "🌫️"), 48: ("冻雾", "🌫️"),
    51: ("毛毛雨", "🌦️"), 53: ("毛毛雨", "🌦️"), 55: ("毛毛雨", "🌦️"),
    56: ("冻毛毛雨", "🌧️"), 57: ("冻毛毛雨", "🌧️"),
    61: ("小雨", "🌧️"), 63: ("中雨", "🌧️"), 65: ("大雨", "🌧️"),
    66: ("冻雨", "🌧️"), 67: ("冻雨", "🌧️"),
    71: ("小雪", "🌨️"), 73: ("中雪", "🌨️"), 75: ("大雪", "🌨️"),
    77: ("雪粒", "🌨️"),
    80: ("阵雨", "🌦️"), 81: ("阵雨", "🌦️"), 82: ("暴雨", "🌧️"),
    85: ("阵雪", "🌨️"), 86: ("阵雪", "🌨️"),
    95: ("雷暴", "⛈️"), 96: ("雷暴伴冰雹", "⛈️"), 99: ("雷暴伴冰雹", "⛈️"),
}


def wmo(code):
    return WMO.get(code, (f"天气代码{code}", "🌡️"))


def fetch(url, tries=2, timeout=10):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < tries - 1:
                time.sleep(1.0)
    raise last


def from_open_meteo(tomorrow=False):
    lats = ",".join(str(c[1]) for c in CITIES)
    lons = ",".join(str(c[2]) for c in CITIES)
    url = ("https://api.open-meteo.com/v1/forecast?"
           f"latitude={lats}&longitude={lons}"
           "&current=temperature_2m,weather_code,wind_speed_10m,"
           "relative_humidity_2m,apparent_temperature"
           "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
           "precipitation_probability_max"
           "&timezone=Asia%2FShanghai&forecast_days=2")
    blocks = json.loads(fetch(url))
    if isinstance(blocks, dict):  # 单城市时返回对象而非数组
        blocks = [blocks]
    idx = 1 if tomorrow else 0  # daily 数组 [今天, 明天]
    day_key = "tomorrow" if tomorrow else "today"
    cities = []
    for (name, _, _), b in zip(CITIES, blocks):
        cur, day = b["current"], b["daily"]
        c_text, c_emoji = wmo(cur.get("weather_code"))
        d_text, d_emoji = wmo(day["weather_code"][idx])
        cities.append({
            "city": name,
            "now": {
                "temp": cur.get("temperature_2m"),
                "feels_like": cur.get("apparent_temperature"),
                "text": c_text, "emoji": c_emoji,
                "humidity": cur.get("relative_humidity_2m"),
                "wind_kmh": cur.get("wind_speed_10m"),
            },
            day_key: {
                "max": day["temperature_2m_max"][idx],
                "min": day["temperature_2m_min"][idx],
                "text": d_text, "emoji": d_emoji,
                "rain_prob": day.get("precipitation_probability_max", [None])[idx],
            },
        })
    return {"source": "Open-Meteo", "cities": cities}


def from_wttr(tomorrow=False):
    """兜底：wttr.in 逐城一行格式（只有当前天气，无当日/明日高低温）。"""
    day_key = "tomorrow" if tomorrow else "today"
    cities = []
    for name, lat, lon in CITIES:
        loc = urllib.parse.quote(f"{lat},{lon}")
        text = fetch(f"https://wttr.in/{loc}?format=%c|%t|%f|%w|%h&lang=zh",
                     tries=1)
        parts = [p.strip() for p in text.strip().split("|")]
        if len(parts) < 5:
            raise RuntimeError(f"wttr.in: bad line for {name}: {text!r}")
        emoji, temp, feels, wind, hum = parts[:5]
        cities.append({
            "city": name,
            "now": {"temp": temp.lstrip("+"), "feels_like": feels.lstrip("+"),
                    "text": "", "emoji": emoji,
                    "humidity": hum.rstrip("%"), "wind_kmh": wind},
            day_key: None,
        })
    return {"source": "wttr.in（仅当前天气）", "cities": cities}


CHAIN = [("open-meteo", from_open_meteo), ("wttr.in", from_wttr)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tomorrow", action="store_true",
                    help="输出明日天气预报（晚报用），默认为今日")
    args = ap.parse_args()

    target_date = date.today() + (timedelta(days=1) if args.tomorrow else timedelta())
    errors = []
    for name, fn in CHAIN:
        try:
            out = fn(tomorrow=args.tomorrow)
            out["date"] = target_date.isoformat()
            out["chain_source"] = name
            if errors:
                out["note"] = "fallback used: " + "; ".join(errors)
            json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
            print()
            return
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    json.dump({"date": None, "source": None, "cities": [],
               "error": "; ".join(errors)}, sys.stdout, ensure_ascii=False)
    print()
    sys.exit(1)


if __name__ == "__main__":
    main()
