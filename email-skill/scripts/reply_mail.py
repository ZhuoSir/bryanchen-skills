#!/usr/bin/env python3
"""回复指定邮件（先 IMAP 取原件，再 SMTP 发送，带 In-Reply-To  threading 头）。

用法：
  python3 reply_mail.py --uid 123 --body "回复内容"
  python3 reply_mail.py --uid 123 --body-file /tmp/reply.txt --all   # 回复全部（含原收件人/抄送）
  python3 reply_mail.py --uid 123 --body "..." --folder INBOX
  python3 reply_mail.py --uid 123 --account work --body "..."        # 多账号：指定收到该邮件的账号
多账号配置下必须 --account 指定收到该邮件的账号（回复即从该账号发出），
账号见 list_mail.py 输出中每封邮件的 account 字段。
正文后自动附带原文引用（> 前缀）。
"""
import argparse
import email
import json
import os
import sys
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mail_lib import (imap_conn, require_account, smtp_send, decode_str,
                      addr_display, extract_body, fail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uid", required=True)
    ap.add_argument("--folder", default="INBOX")
    ap.add_argument("--body", default="")
    ap.add_argument("--body-file", default="")
    ap.add_argument("--all", action="store_true", help="回复全部（原发件人 + 原 To/Cc 中除自己外的地址）")
    ap.add_argument("--account", default="",
                    help="收到该邮件的账号标签（回复即从该账号发出）；多账号配置下必填")
    args = ap.parse_args()

    body = args.body
    if args.body_file:
        try:
            with open(args.body_file, encoding="utf-8") as f:
                body = f.read()
        except OSError as e:
            fail(f"读取正文文件失败: {e}")
    if not body.strip():
        fail("回复正文为空")

    cfg = require_account(args.account, purpose="回复邮件")
    conn = imap_conn(cfg, folder=args.folder, readonly=True)
    typ, data = conn.uid("FETCH", args.uid, "(BODY.PEEK[])")
    conn.logout()
    if typ != "OK" or not data or not isinstance(data[0], tuple):
        fail(f"未找到 UID={args.uid} 的邮件（account={cfg['_account']}，"
             "确认 --account 与 list_mail.py 输出一致、--folder 正确）")

    orig = email.message_from_bytes(data[0][1])
    orig_subject = decode_str(orig.get("Subject", "")) or "(无主题)"
    orig_from = parseaddr(orig.get("From", ""))[1]
    if not orig_from:
        fail("原邮件缺少发件人地址，无法回复")
    orig_date = orig.get("Date", "")
    orig_body, _ = extract_body(orig)

    # 收件人
    to_list = [orig_from]
    cc_list = []
    if args.all:
        me = cfg["email"].lower()
        for hdr in ("To", "Cc"):
            for _, addr in email.utils.getaddresses([orig.get(hdr, "")]):
                if addr and addr.lower() != me and addr not in to_list and addr not in cc_list:
                    cc_list.append(addr)

    subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"

    # 原文引用
    quoted = "\n".join("> " + line for line in orig_body.strip().splitlines())
    full_body = f"{body}\n\n在 {orig_date}，{addr_display(orig.get('From',''))} 写道：\n{quoted}\n"

    msg = MIMEText(full_body, "plain", "utf-8")
    name = cfg.get("name", "")
    msg["From"] = formataddr((str(Header(name, "utf-8")), cfg["email"])) if name else cfg["email"]
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = Header(subject, "utf-8")

    # threading 头
    orig_mid = (orig.get("Message-ID") or "").strip()
    orig_refs = (orig.get("References") or "").strip()
    if orig_mid:
        msg["In-Reply-To"] = orig_mid
        msg["References"] = f"{orig_refs} {orig_mid}".strip()

    smtp_send(cfg, msg, to_list + cc_list)
    print(json.dumps({
        "ok": True,
        "account": cfg["_account"],
        "from": cfg["email"],
        "replied_to_uid": args.uid,
        "to": to_list,
        "cc": cc_list,
        "subject": subject,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
