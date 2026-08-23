#!/usr/bin/env python3
"""发送新邮件（SMTP）。

用法：
  python3 send_mail.py --to a@b.com --subject "主题" --body "正文"
  python3 send_mail.py --to a@b.com,b@c.com --cc d@e.com --subject "..." --body-file /tmp/body.txt
输出 JSON：{"ok": true, "to": [...], "subject": "..."}
"""
import argparse
import json
import os
import sys
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mail_lib import load_config, smtp_send, fail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True, help="收件人，多个用英文逗号分隔")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", default="", help="纯文本正文")
    ap.add_argument("--body-file", default="", help="从文件读取正文（优先于 --body）")
    ap.add_argument("--cc", default="", help="抄送，多个用英文逗号分隔")
    args = ap.parse_args()

    body = args.body
    if args.body_file:
        try:
            with open(args.body_file, encoding="utf-8") as f:
                body = f.read()
        except OSError as e:
            fail(f"读取正文文件失败: {e}")

    cfg = load_config()
    to_list = [a.strip() for a in args.to.split(",") if a.strip()]
    cc_list = [a.strip() for a in args.cc.split(",") if a.strip()]
    if not to_list:
        fail("收件人为空")

    msg = MIMEText(body, "plain", "utf-8")
    name = cfg.get("name", "")
    msg["From"] = formataddr((str(Header(name, "utf-8")), cfg["email"])) if name else cfg["email"]
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = Header(args.subject, "utf-8")

    smtp_send(cfg, msg, to_list + cc_list)
    print(json.dumps({
        "ok": True,
        "from": cfg["email"],
        "to": to_list,
        "cc": cc_list,
        "subject": args.subject,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
