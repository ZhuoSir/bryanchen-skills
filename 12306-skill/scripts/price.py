#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
price.py — 查询某趟列车指定区间的各席别票价

用法：
  python3 price.py --train G25 --from 北京南 --to 上海虹桥 --date 明天

参数：
  --train   车次（必填，如 G25）
  --from    出发站（必填，该车次当日实际停靠的车站）
  --to      到达站（必填）
  --date    出发日期：YYYY-MM-DD 或 今天/明天/后天（默认明天）
说明：
  12306 的票价接口需要内部 train_no 与车站序号，本脚本先通过余票接口
  定位车次（因此区间必须是该车次当日实际运行区间），再查票价。
输出：JSON 到 stdout。
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib12306  # noqa: E402


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
    ap = argparse.ArgumentParser(description="12306 票价查询")
    ap.add_argument("--train", required=True, help="车次，如 G25")
    ap.add_argument("--from", dest="from_station", required=True, help="出发站")
    ap.add_argument("--to", dest="to_station", required=True, help="到达站")
    ap.add_argument("--date", default="明天", help="YYYY-MM-DD / 今天 / 明天 / 后天")
    args = ap.parse_args()

    date = parse_date(args.date)
    date_str = date.isoformat()
    code = args.train.upper()

    try:
        stations = lib12306.load_stations()
        from_name, from_code = lib12306.resolve_station(args.from_station, stations)
        to_name, to_code = lib12306.resolve_station(args.to_station, stations)
        session = lib12306.new_session()
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return

    # 定位车次（需要 train_no / 车站序号 / 席别代码串）
    try:
        trains = lib12306.query_left_tickets(session, date_str, from_code, to_code)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return
    hit = next((t for t in trains
                if t["train_code"].upper() == code), None)
    if not hit:
        print(json.dumps({
            "ok": False,
            "error": f"未在 {date_str} 的 {from_name}→{to_name} 找到车次 {code}"
                     "（当日可能不开行，或区间不是该车实际停靠站）",
        }, ensure_ascii=False))
        return

    try:
        prices = lib12306.query_price(session, hit["train_no"],
                                      hit["from_station_no"],
                                      hit["to_station_no"],
                                      hit["seat_types"], date_str)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return

    print(json.dumps({
        "ok": True,
        "train": hit["train_code"],
        "date": date_str,
        "weekday": "一二三四五六日"[date.weekday()],
        "from": from_name,
        "to": to_name,
        "depart": hit["start_time"],
        "arrive": hit["arrive_time"],
        "duration": hit["duration"],
        "prices": prices,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
