#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""晨报/晚报内容去重台账（纯标准库，零依赖）。

问题：晨报与晚报同源（60s 新闻 API / RSS / 虎扑 / 热榜），
      同一天的候选项高度重合 —— 晚报很容易把早上刚发过的新闻再发一遍。

方案：晨报发送成功后把「已发条目」记入当日台账；晚报组装前先跑 filter，
      被剔掉的条目会列出来，由你从候选池里换上别的内容。

用法：
  # 1) 晨报发送成功后登记（幂等，可重复执行）
  python3 scripts/sent_log.py record --data /tmp/morning_report.json --mode morning

  # 2) 晚报用「更大候选池」先过滤，输出可用的 JSON
  python3 scripts/sent_log.py filter --data /tmp/evening_candidates.json --out /tmp/evening_ok.json

  # 3) 查看/清空当日台账
  python3 scripts/sent_log.py show
  python3 scripts/sent_log.py reset

台账位置：<skill>/data/sent/YYYY-MM-DD.json（自动清理 3 天前的旧台账）
匹配口径：标题归一化（去空白与标点、转小写）或 URL 完全相同即视为「已发过」
          —— 同一源的同一条新闻标题逐字相同，可靠；措辞被你改写过的标题按 URL 兜底。
"""
import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SENT_DIR = os.path.join(ROOT, "data", "sent")
KEEP_DAYS = 3

PUNCT_RE = re.compile(r"[\s·、，,。.：:；;！!？?“”\"'（）()\[\]【】《》<>—\-_/\\|~`@#$%^&*+=]+")


def norm_key(text):
    """标题归一化：去掉空白/标点、转小写，作为比对键。"""
    return PUNCT_RE.sub("", str(text or "")).lower()


def state_path(date):
    return os.path.join(SENT_DIR, f"{date}.json")


def load_state(date):
    p = state_path(date)
    if not os.path.exists(p):
        return {"date": date, "entries": []}
    try:
        with open(p, encoding="utf-8") as f:
            s = json.load(f)
        s.setdefault("entries", [])
        return s
    except (OSError, json.JSONDecodeError):
        return {"date": date, "entries": []}


def save_state(state):
    os.makedirs(SENT_DIR, exist_ok=True)
    with open(state_path(state["date"]), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def prune_old():
    """清理超过 KEEP_DAYS 天的台账。"""
    if not os.path.isdir(SENT_DIR):
        return
    cutoff = datetime.date.today() - datetime.timedelta(days=KEEP_DAYS)
    for name in os.listdir(SENT_DIR):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\.json$", name)
        if not m:
            continue
        try:
            d = datetime.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if d < cutoff:
            try:
                os.remove(os.path.join(SENT_DIR, name))
            except OSError:
                pass


def iter_items(data):
    """遍历内容 JSON 里所有「可去重」的条目：news/schedule 的 items、hot 的 boards[].items。

    产出 (block_label, container, list_obj, index, item)；
    container 为 items 列表本身，便于原地删除。
    天气、赛程（'schedule' 字段）不做去重 —— 它们本来就按时间窗变化。
    """
    for block in data.get("blocks", []):
        if not isinstance(block, dict):
            continue
        label = block.get("label") or block.get("type") or ""
        if block.get("type") == "hot":
            for board in block.get("boards", []):
                items = board.get("items", [])
                for i, it in enumerate(items):
                    yield f"{label}/{board.get('board', '')}", items, i, it
        elif isinstance(block.get("items"), list):
            items = block["items"]
            for i, it in enumerate(items):
                yield label, items, i, it


def collect_keys(state):
    keys = set()
    modes = {}
    for e in state.get("entries", []):
        for k in (e.get("key"), norm_key(e.get("url")) if e.get("url") else ""):
            if k:
                keys.add(k)
                modes.setdefault(k, e.get("mode", ""))
    return keys, modes


def cmd_record(args):
    date = args.date or datetime.date.today().isoformat()
    try:
        with open(args.data, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": f"读取失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    state = load_state(date)
    keys, _ = collect_keys(state)
    added = 0
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for label, _items, _i, it in iter_items(data):
        title = (it or {}).get("title", "")
        url = (it or {}).get("url", "")
        k = norm_key(title)
        if not k:
            continue
        if k in keys:
            continue
        state["entries"].append({
            "key": k, "title": title, "url": url,
            "block": label, "mode": args.mode, "at": now,
        })
        keys.add(k)
        added += 1
    save_state(state)
    prune_old()
    print(json.dumps({"ok": True, "date": date, "mode": args.mode,
                      "added": added, "total": len(state["entries"]),
                      "state": state_path(date)}, ensure_ascii=False, indent=2))


def cmd_filter(args):
    date = args.date or datetime.date.today().isoformat()
    try:
        with open(args.data, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": f"读取失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    state = load_state(date)
    keys, modes = collect_keys(state)

    removed, seen_here = [], set()
    kept = 0
    # 倒序删除，避免索引错位
    for label, items, _i, it in sorted(iter_items(data), key=lambda x: -x[2]):
        title = (it or {}).get("title", "")
        url = (it or {}).get("url", "")
        k = norm_key(title)
        uk = norm_key(url) if url else ""
        why = None
        if k and k in keys:
            why = modes.get(k) or "earlier"
        elif uk and uk in keys:
            why = modes.get(uk) or "earlier"
        elif k and k in seen_here:
            why = "same-batch"
        if why:
            removed.append({"block": label, "title": title, "url": url, "already": why})
            del items[_i]
        else:
            if k:
                seen_here.add(k)
            if uk:
                seen_here.add(uk)
            kept += 1

    removed.reverse()
    out = args.out
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    by_block = {}
    for r in removed:
        by_block[r["block"]] = by_block.get(r["block"], 0) + 1

    print(json.dumps({
        "ok": True, "date": date,
        "kept": kept, "removed": len(removed),
        "removed_by_block": by_block,
        "removed_items": removed,
        "out": out or "",
        "hint": ("被剔除的条目要在候选池里换成别的；池子不够时宁少勿重，"
                 "可选 web_search 补 1-2 条，绝不要把晨报发过的再发一次"),
    }, ensure_ascii=False, indent=2))


def cmd_show(args):
    date = args.date or datetime.date.today().isoformat()
    state = load_state(date)
    print(json.dumps({
        "ok": True, "date": date, "path": state_path(date),
        "total": len(state.get("entries", [])),
        "by_mode": {m: sum(1 for e in state["entries"] if e.get("mode") == m)
                    for m in sorted({e.get("mode", "") for e in state["entries"]})},
        "titles": [e.get("title") for e in state.get("entries", [])],
    }, ensure_ascii=False, indent=2))


def cmd_reset(args):
    date = args.date or datetime.date.today().isoformat()
    p = state_path(date)
    existed = os.path.exists(p)
    if existed:
        os.remove(p)
    print(json.dumps({"ok": True, "date": date, "removed": existed, "path": p},
                     ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(description="晨报/晚报内容去重台账")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, fn in (("record", cmd_record), ("filter", cmd_filter),
                     ("show", cmd_show), ("reset", cmd_reset)):
        p = sub.add_parser(name)
        p.add_argument("--date", default="", help="缺省今天 YYYY-MM-DD")
        if name in ("record", "filter"):
            p.add_argument("--data", required=True, help="内容 JSON 路径")
        if name == "record":
            p.add_argument("--mode", default="morning", choices=["morning", "evening"])
        if name == "filter":
            p.add_argument("--out", default="", help="过滤后写回的 JSON 路径（不写则只报告）")
        p.set_defaults(func=fn)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
