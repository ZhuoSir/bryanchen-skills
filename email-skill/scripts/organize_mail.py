#!/usr/bin/env python3
"""整理邮件：标记已读/未读、加/去星标、移动到文件夹、删除、新建文件夹（IMAP）。

用法：
  python3 organize_mail.py --uid 1,2,3 --action mark-read      [--folder INBOX]
  python3 organize_mail.py --uid 4 --action move --target Archive
  python3 organize_mail.py --uid 5 --action delete             # 移入 Trash（无 Trash 则直接删除）
  python3 organize_mail.py --action mkdir --target "账单/2026"  # 新建文件夹
  python3 organize_mail.py --account work --uid 1 --action mark-read   # 多账号：指定账号
多账号配置下必须 --account 指定邮件所属账号（见 list_mail.py 输出的 account 字段）；
不同账号需分批整理（UID 只在单账号内有意义）。
动作：mark-read | mark-unread | flag | unflag | move | delete | mkdir
输出 JSON：{"ok": true, "action": ..., "affected": n}
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mail_lib import (imap_conn, require_account, imap_utf7_decode,
                      imap_utf7_encode, fail)

ACTIONS = ("mark-read", "mark-unread", "flag", "unflag", "move", "delete", "mkdir")
TRASH_CANDIDATES = ("Trash", "Deleted Messages", "Deleted", "已删除", "垃圾邮件")


def find_trash(conn):
    typ, data = conn.list()
    if typ == "OK":
        names = []
        for line in data:
            if not line:
                continue
            s = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
            names.append(imap_utf7_decode(s.rsplit(' "', 1)[-1].strip('"')))
        low = {n.lower(): n for n in names}
        for cand in TRASH_CANDIDATES:
            if cand.lower() in low:
                return low[cand.lower()]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uid", default="", help="邮件 UID，多个用英文逗号分隔")
    ap.add_argument("--action", required=True, choices=ACTIONS)
    ap.add_argument("--folder", default="INBOX", help="源文件夹（默认 INBOX）")
    ap.add_argument("--target", default="", help="目标文件夹（move/mkdir 必填）")
    ap.add_argument("--account", default="",
                    help="邮件所属账号标签；多账号配置下必填")
    args = ap.parse_args()

    cfg = require_account(args.account, purpose="整理邮件")

    if args.action == "mkdir":
        if not args.target:
            fail("mkdir 需要 --target 指定文件夹名")
        conn = imap_conn(cfg)
        typ, resp = conn.create(f'"{imap_utf7_encode(args.target)}"')
        conn.logout()
        if typ != "OK":
            fail(f"创建文件夹失败: {resp}")
        print(json.dumps({"ok": True, "account": cfg["_account"],
                          "action": "mkdir", "folder": args.target},
                         ensure_ascii=False, indent=2))
        return

    uids = [u.strip() for u in args.uid.split(",") if u.strip()]
    if not uids:
        fail("该操作需要 --uid 指定至少一封邮件")
    uid_set = ",".join(uids)

    conn = imap_conn(cfg, folder=args.folder, readonly=False)

    def store(flag_op, flags):
        typ, resp = conn.uid("STORE", uid_set, flag_op, flags)
        if typ != "OK":
            conn.logout()
            fail(f"STORE {flag_op} {flags} 失败: {resp}")

    if args.action == "mark-read":
        store("+FLAGS", "(\\Seen)")
    elif args.action == "mark-unread":
        store("-FLAGS", "(\\Seen)")
    elif args.action == "flag":
        store("+FLAGS", "(\\Flagged)")
    elif args.action == "unflag":
        store("-FLAGS", "(\\Flagged)")
    elif args.action == "move":
        if not args.target:
            conn.logout()
            fail("move 需要 --target 指定目标文件夹")
        typ, resp = conn.uid("COPY", uid_set, f'"{imap_utf7_encode(args.target)}"')
        if typ != "OK":
            conn.logout()
            fail(f"复制到 {args.target} 失败: {resp}（文件夹不存在？可先用 --action mkdir 创建）")
        store("+FLAGS", "(\\Deleted)")
        conn.expunge()
    elif args.action == "delete":
        trash = find_trash(conn)
        if trash and trash != args.folder:
            typ, _ = conn.uid("COPY", uid_set, f'"{imap_utf7_encode(trash)}"')
            if typ != "OK":
                trash = None  # 复制失败则退回直接删除
        store("+FLAGS", "(\\Deleted)")
        conn.expunge()
        print(json.dumps({
            "ok": True, "account": cfg["_account"], "action": "delete",
            "moved_to": trash or "(直接永久删除)",
            "affected": len(uids), "uids": uids,
        }, ensure_ascii=False, indent=2))
        conn.logout()
        return

    conn.logout()
    out = {"ok": True, "account": cfg["_account"],
           "action": args.action, "affected": len(uids), "uids": uids}
    if args.action == "move":
        out["moved_to"] = args.target
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
