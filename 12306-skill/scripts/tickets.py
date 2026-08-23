#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tickets.py — 查询 12306 余票

用法：
  python3 tickets.py --from 北京 --to 上海 --date 2026-08-25
  python3 tickets.py --from 北京南 --to 上海虹桥 --date 明天 --type G
  python3 tickets.py --from 北京 --to 上海 --date 后天 --train G103

参数：
  --from    出发站（车站名或三字码，如 北京 / BJP）
  --to      到达站
  --date    出发日期：YYYY-MM-DD，或 今天/明天/后天（默认明天）
  --type    可选，按车次类型过滤，逗号分隔：G,D,C,K,T,Z,数字（如 G,D）
  --train   可选，只看指定车次（如 G103），可与 --type 二选一
输出：JSON 到 stdout。ok=false 时带 error 说明。
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib12306  # noqa: E402

TRAIN_TYPES = {"G", "D", "C", "K", "T", "Z"}


def parse_date(s):
    today = datetime.date.today()
    if s in (None, "", "明天"):
        return today + datetime.timedelta(days=1)
    if s == "今天":
        return today
    if s == "后天":
        return today + datetime.timedelta(days=2)
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        raise SystemExit(json.dumps(
            {"ok": False, "error": f"无法识别日期「{s}」，请用 YYYY-MM-DD 或 今天/明天/后天"},
            ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description="12306 余票查询")
    ap.add_argument("--from", dest="from_station", required=True, help="出发站")
    ap.add_argument("--to", dest="to_station", required=True, help="到达站")
    ap.add_argument("--date", default="明天", help="YYYY-MM-DD / 今天 / 明天 / 后天")
    ap.add_argument("--type", default="", help="车次类型过滤，如 G,D")
    ap.add_argument("--train", default="", help="只看指定车次，如 G103")
    args = ap.parse_args()

    date = parse_date(args.date)
    date_str = date.isoformat()

    try:
        stations = lib12306.load_stations()
        from_name, from_code = lib12306.resolve_station(args.from_station, stations)
        to_name, to_code = lib12306.resolve_station(args.to_station, stations)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return

    try:
        session = lib12306.new_session()
        trains = lib12306.query_left_tickets(session, date_str, from_code, to_code)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return

    # 过滤
    if args.train:
        want = args.train.upper()
        trains = [t for t in trains if t["train_code"].upper() == want]
    elif args.type:
        types = {x.strip().upper() for x in args.type.split(",") if x.strip()}
        def match(code):
            first = code[0].upper()
            if first in TRAIN_TYPES:
                return first in types
            return "数字" in types  # 纯数字普速
        trains = [t for t in trains if match(t["train_code"])]

    result = {
        "ok": True,
        "date": date_str,
        "weekday": "一二三四五六日"[date.weekday()],
        "from": from_name,
        "to": to_name,
        "total": len(trains),
        "trains": [{
            "train": t["train_code"],
            "from": t["from_station"],
            "to": t["to_station"],
            "depart": t["start_time"],
            "arrive": t["arrive_time"],
            "duration": t["duration"],
            "can_buy": t["can_buy"],
            "seats": t["seats"],
        } for t in trains],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
