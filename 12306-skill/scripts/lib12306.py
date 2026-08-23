#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib12306.py — 12306 网页版公开查询接口的共享库（零依赖，Python 3 标准库）

提供：
  - 会话管理（自动先取 Cookie，带浏览器 UA / Referer）
  - 车站名 ↔ 三字代码映射（station_name.js，缓存到系统临时目录，7 天有效）
  - 余票接口端点自动跟进（query / queryA / queryG / queryZ 会不定期迁移，
    12306 通过返回 JSON 里的 c_url 字段告知新端点，本库自动跟随）
  - leftTicket 返回的 `|` 分隔行解析

仅做"查询"：余票 / 时刻。不涉及登录、下单（12306 无官方开放 API，
下单需登录 + 验证码 + 实名核验，自动化违规且有封号风险，不要做）。
"""

import json
import os
import re
import ssl
import tempfile
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

BASE = "https://kyfw.12306.cn"
STATION_JS_URL = BASE + "/otn/resources/js/framework/station_name.js"
TIMEOUT = 15

# leftTicket 查询端点，12306 不定期迁移，按近期实测顺序排列；
# 若返回 JSON 带 c_url 字段则自动跟随该端点。
LEFT_TICKET_ENDPOINTS = [
    "leftTicket/queryG",
    "leftTicket/query",
    "leftTicket/queryA",
    "leftTicket/queryZ",
]

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# leftTicket 行内字段下标（`|` 分隔，社区长期稳定的映射）
IDX = {
    "train_code": 3,        # 车次，如 G103
    "train_no": 2,          # 内部编号，如 240000G10336（查经停站时刻需要）
    "from_telecode": 6,     # 出发站三字码
    "to_telecode": 7,       # 到达站三字码
    "start_time": 8,        # 出发时间 HH:MM
    "arrive_time": 9,       # 到达时间 HH:MM
    "lishi": 10,            # 历时，如 4:29
    "can_buy": 11,          # Y / N / IS_TIME_NOT_BUY
    "start_date": 13,       # 出发日期 YYYYMMDD
    "from_station_no": 16,  # 出发站在全程中的序号（查票价需要）
    "to_station_no": 17,    # 到达站在全程中的序号（查票价需要）
    "seat_types": 35,       # 席别代码串（查票价需要）
}

# 座位字段下标（下标, 座位名）；空串和 "--" 会在解析时丢弃
SEAT_FIELDS = [
    (32, "商务座"), (25, "特等座"), (31, "一等座"), (30, "二等座"),
    (21, "高级软卧"), (23, "软卧"), (33, "动卧"), (28, "硬卧"),
    (24, "软座"), (29, "硬座"), (26, "无座"), (22, "其他"),
]

_ctx = ssl.create_default_context()


def _opener():
    """带 CookieJar + SSL 上下文的 opener（12306 查询接口要求先拿会话 Cookie）。"""
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(CookieJar()),
        urllib.request.HTTPSHandler(context=_ctx),
    )


def _get_json(opener, url, referer=BASE + "/otn/leftTicket/init"):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": referer,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    })
    with opener.open(req, timeout=TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8", "replace"))


def new_session():
    """新建会话：先请求 init 页拿 Cookie。返回 opener。"""
    opener = _opener()
    req = urllib.request.Request(BASE + "/otn/leftTicket/init",
                                 headers={"User-Agent": UA})
    with opener.open(req, timeout=TIMEOUT) as resp:  # noqa: S310
        resp.read()
    return opener


# ---------------------------------------------------------------- 车站代码

def _station_cache_path():
    return os.path.join(tempfile.gettempdir(), "12306_stations.json")


def load_stations(force=False):
    """返回 {车站名: 三字码}。优先读缓存（7 天内有效），否则在线抓取并写缓存。"""
    cache = _station_cache_path()
    if not force and os.path.exists(cache):
        try:
            if time.time() - os.path.getmtime(cache) < 7 * 86400:
                with open(cache, encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    req = urllib.request.Request(STATION_JS_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ctx) as resp:  # noqa: S310
        text = resp.read().decode("utf-8", "replace")
    # 格式：@bjb|北京北|VAP|beijingbei|bjb|0@bhd|北戴河|BDP|...
    stations = {}
    for rec in text.split("@")[1:]:
        parts = rec.split("|")
        if len(parts) >= 3:
            stations[parts[1]] = parts[2]
    try:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(stations, f, ensure_ascii=False)
    except Exception:
        pass  # 缓存写不进不影响功能
    return stations


def resolve_station(name, stations=None):
    """车站名或三字码 → (名称, 三字码)。找不到时返回带建议的错误信息。"""
    stations = stations or load_stations()
    if re.fullmatch(r"[A-Z]{3}", name) and name in stations.values():
        for n, c in stations.items():
            if c == name:
                return n, c
    if name in stations:
        return name, stations[name]
    # 模糊建议
    sugg = [n for n in stations if name in n][:8]
    hint = ("，你是不是想找：" + "、".join(sugg)) if sugg else ""
    raise ValueError(f"未找到车站「{name}」{hint}")


# ---------------------------------------------------------------- 余票查询

def query_left_tickets(opener, date, from_code, to_code):
    """
    查询余票。date 为 YYYY-MM-DD。返回解析后的车次列表（每项 dict）。
    自动尝试多个端点并跟随 c_url 迁移。
    """
    params = urllib.parse.urlencode({
        "leftTicketDTO.train_date": date,
        "leftTicketDTO.from_station": from_code,
        "leftTicketDTO.to_station": to_code,
        "purpose_codes": "ADULT",
    })
    for ep in LEFT_TICKET_ENDPOINTS:
        url = f"{BASE}/otn/{ep}?{params}"
        try:
            data = _get_json(opener, url)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        # 12306 告知端点迁移时跟随一次
        c_url = data.get("c_url")
        if c_url and c_url != ep:
            try:
                data = _get_json(opener, f"{BASE}/otn/{c_url}?{params}")
            except Exception:
                continue
        result = (data.get("data") or {}).get("result") or []
        if result:
            station_map = (data.get("data") or {}).get("map") or {}
            return [parse_row(r, station_map) for r in result]
    raise RuntimeError("所有余票查询端点均未返回数据（可能被风控或端点又迁移了）")


def parse_row(row, station_map=None):
    """解析一根 `|` 分隔的余票行。座位只保留有信息的项。"""
    f = row.split("|")
    station_map = station_map or {}

    def at(i):
        return f[i] if i < len(f) else ""

    seats = {}
    for idx, name in SEAT_FIELDS:
        v = at(idx)
        if v and v != "--":
            seats[name] = v  # 值可能是 "有"、数字、"无"、"候补"
    return {
        "train_code": at(IDX["train_code"]),
        "train_no": at(IDX["train_no"]),
        "from_station": station_map.get(at(IDX["from_telecode"]),
                                        at(IDX["from_telecode"])),
        "to_station": station_map.get(at(IDX["to_telecode"]),
                                      at(IDX["to_telecode"])),
        "from_telecode": at(IDX["from_telecode"]),
        "to_telecode": at(IDX["to_telecode"]),
        "from_station_no": at(IDX["from_station_no"]),
        "to_station_no": at(IDX["to_station_no"]),
        "seat_types": at(IDX["seat_types"]),
        "start_time": at(IDX["start_time"]),
        "arrive_time": at(IDX["arrive_time"]),
        "duration": at(IDX["lishi"]),
        "can_buy": at(IDX["can_buy"]) == "Y",
        "seats": seats,
    }


# ---------------------------------------------------------------- 票价查询

# queryTicketPrice 返回的席别代码 → 中文名
PRICE_SEAT_NAMES = {
    "A9": "商务座", "P": "特等座", "M": "一等座", "O": "二等座",
    "A6": "高级软卧", "A4": "软卧", "F": "动卧", "A3": "硬卧",
    "A2": "软座", "A1": "硬座", "WZ": "无座",
}


def query_price(opener, train_no, from_station_no, to_station_no,
                seat_types, date):
    """
    查询某趟车指定区间的各席别票价（leftTicket/queryTicketPrice）。
    参数均来自余票解析结果。date 为 YYYY-MM-DD。
    返回 {席别中文名: "¥xxx"}，按票价从高到低排序。
    """
    params = urllib.parse.urlencode({
        "train_no": train_no,
        "from_station_no": from_station_no,
        "to_station_no": to_station_no,
        "seat_types": seat_types,
        "train_date": date,
    })
    data = _get_json(opener, f"{BASE}/otn/leftTicket/queryTicketPrice?{params}")
    raw = data.get("data") or {}
    prices = {}
    for code, name in PRICE_SEAT_NAMES.items():
        v = raw.get(code)
        if v:
            prices[name] = v if str(v).startswith("¥") else f"¥{v}"
    return prices


# ---------------------------------------------------------------- 经停站时刻

def query_schedule(opener, train_no, from_telecode, to_telecode, date):
    """
    查询某趟车的全程经停站时刻（czxx/queryByTrainNo）。
    train_no 为内部编号（由余票结果带出），date 为 YYYY-MM-DD。
    返回经停站列表。
    """
    params = urllib.parse.urlencode({
        "train_no": train_no,
        "from_station_telecode": from_telecode,
        "to_station_telecode": to_telecode,
        "depart_date": date,
    })
    data = _get_json(opener, f"{BASE}/otn/czxx/queryByTrainNo?{params}",
                     referer=BASE + "/otn/leftTicket/init")
    rows = (data.get("data") or {}).get("data") or []
    out = []
    for r in rows:
        out.append({
            "station_no": r.get("station_no"),
            "station_name": r.get("station_name"),
            "arrive": r.get("arrive_time"),
            "depart": r.get("start_time"),
            "stopover": r.get("stopover_time"),
        })
    return out
