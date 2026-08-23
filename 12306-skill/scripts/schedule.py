#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
schedule.py — 查询某趟列车的全程经停站时刻表

用法：
  python3 schedule.py --train G103 --date 2026-08-25
  python3 schedule.py --train G103 --from 北京南 --to 上海虹桥 --date 明天

参数：
  --train   车次（必填，如 G103 / K180 / 1271）
  --date    出发日期：YYYY-MM-DD 或 今天/明天/后天（默认明天）
  --from    可选，乘车区间出发站（默认用该车次的始发区域推断）
  --to      可选，乘车区间到达站
说明：
  12306 的时刻接口需要内部 train_no，本脚本先通过余票接口定位该车次。
  因此 --from/--to 需能覆盖该车次当日实际运行区间（不填时默认查
  该车次所在线路的常用大站区间，查不到时请显式给出区间）。
输出：JSON 到 stdout。
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib12306  # noqa: E402

# 未指定区间时的兜底探测区间（覆盖主要干线，按命中率排序）
FALLBACK_ROUTES = [
    ("北京南", "上海虹桥"), ("北京", "上海"),
    ("北京西", "广州南"), ("北京西", "深圳北"),
    ("北京西", "成都东"), ("北京西", "西安北"),
    ("上海虹桥", "杭州东"), ("上海虹桥", "南京南"),
    ("广州南", "深圳北"), ("北京", "哈尔滨"),
]


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


def find_train(session, stations, code, date_str, from_name, to_name):
    """在指定区间余票结果里定位车次，返回该车的完整记录（含 train_no）。"""
    _, from_code = lib12306.resolve_station(from_name, stations)
    _, to_code = lib12306.resolve_station(to_name, stations)
    trains = lib12306.query_left_tickets(session, date_str, from_code, to_code)
    for t in trains:
        if t["train_code"].upper() == code.upper():
            return t
    return None


def main():
    ap = argparse.ArgumentParser(description="12306 经停站时刻表")
    ap.add_argument("--train", required=True, help="车次，如 G103")
    ap.add_argument("--date", default="明天", help="YYYY-MM-DD / 今天 / 明天 / 后天")
    ap.add_argument("--from", dest="from_station", default="", help="区间出发站")
    ap.add_argument("--to", dest="to_station", default="", help="区间到达站")
    args = ap.parse_args()

    date = parse_date(args.date)
    date_str = date.isoformat()
    code = args.train.upper()

    try:
        stations = lib12306.load_stations()
        session = lib12306.new_session()
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return

    # 定位车次（需要内部 train_no）
    hit, searched = None, []
    try:
        if args.from_station and args.to_station:
            routes = [(args.from_station, args.to_station)]
        else:
            routes = FALLBACK_ROUTES
        for from_name, to_name in routes:
            searched.append(f"{from_name}→{to_name}")
            try:
                hit = find_train(session, stations, code, date_str,
                                 from_name, to_name)
            except Exception:
                hit = None
            if hit:
                break
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return

    if not hit:
        print(json.dumps({
            "ok": False,
            "error": (f"未在 {date_str} 找到车次 {code}（已尝试区间："
                      + "、".join(searched) + "）。该车次当日可能不开行，"
                        "或请用 --from/--to 显式给出它经过的区间再试。"),
        }, ensure_ascii=False))
        return

    try:
        stops = lib12306.query_schedule(session, hit["train_no"],
                                        hit["from_telecode"],
                                        hit["to_telecode"], date_str)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return

    print(json.dumps({
        "ok": True,
        "train": hit["train_code"],
        "date": date_str,
        "weekday": "一二三四五六日"[date.weekday()],
        "total_stops": len(stops),
        "stops": stops,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
