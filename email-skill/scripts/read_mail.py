#!/usr/bin/env python3
"""按 UID 读取邮件全文（IMAP，只读，不改变已读状态）。

用法：
  python3 read_mail.py --uid 123 [--folder INBOX]
输出 JSON：{ok, uid, subject, from, to, date, message_id, body_format, body, attachments}
"""
import argparse
import email
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mail_lib import (imap_conn, load_config, decode_str, addr_display,
                      extract_body, list_attachments, truncate, fail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uid", required=True, help="邮件 UID（由 list_mail.py 获得）")
    ap.add_argument("--folder", default="INBOX")
    args = ap.parse_args()

    cfg = load_config()
    conn = imap_conn(cfg, folder=args.folder, readonly=True)
    # BODY.PEEK[] 不设置 \Seen，避免误标已读
    typ, data = conn.uid("FETCH", args.uid, "(BODY.PEEK[])")
    if typ != "OK" or not data or not isinstance(data[0], tuple):
        conn.logout()
        fail(f"未找到 UID={args.uid} 的邮件（folder={args.folder}）")
    conn.logout()

    msg = email.message_from_bytes(data[0][1])
    body, fmt = extract_body(msg)
    print(json.dumps({
        "ok": True,
        "uid": args.uid,
        "folder": args.folder,
        "subject": decode_str(msg.get("Subject", "")) or "(无主题)",
        "from": addr_display(msg.get("From", "")),
        "to": decode_str(msg.get("To", "")),
        "cc": decode_str(msg.get("Cc", "")),
        "date": msg.get("Date", ""),
        "message_id": (msg.get("Message-ID") or "").strip(),
        "references": (msg.get("References") or "").strip(),
        "body_format": fmt,
        "body": truncate(body),
        "attachments": list_attachments(msg),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
