#!/usr/bin/env python3
"""发送新邮件（SMTP）。默认纯文本；支持 Markdown / HTML 正文（multipart/alternative，
HTML 版 + 自动生成的纯文本兜底，老客户端也能读）。

用法：
  python3 send_mail.py --to a@b.com --subject "主题" --body "正文"
  python3 send_mail.py --to a@b.com,b@c.com --cc d@e.com --subject "..." --body-file /tmp/body.txt
  python3 send_mail.py --to a@b.com --subject "..." --markdown-file report.md   # md 渲染为 HTML
  python3 send_mail.py --to a@b.com --subject "..." --html-file report.html     # 直接发 HTML
输出 JSON：{"ok": true, "to": [...], "subject": "...", "format": "plain|markdown|html"}
"""
import argparse
import json
import os
import re
import sys
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mail_lib import load_config, smtp_send, md_to_html, fail


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        fail(f"读取文件失败: {e}")


def html_to_plain(html_text):
    """从 HTML 粗提取纯文本（兜底 part 用）。"""
    t = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html_text)
    t = re.sub(r"(?is)<a [^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"\2（\1）", t)
    t = re.sub(r"(?is)<br\s*/?>", "\n", t)
    t = re.sub(r"(?is)</(p|div|li|h[1-6]|tr|blockquote)>", "\n", t)
    t = re.sub(r"(?s)<[^>]+>", "", t)
    import html as html_mod
    return html_mod.unescape(t).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True, help="收件人，多个用英文逗号分隔")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", default="", help="纯文本正文")
    ap.add_argument("--body-file", default="", help="从文件读取纯文本正文（优先于 --body）")
    ap.add_argument("--markdown-file", default="", help="Markdown 文件，渲染为 HTML 邮件")
    ap.add_argument("--html-file", default="", help="HTML 文件，直接作为 HTML 邮件")
    ap.add_argument("--cc", default="", help="抄送，多个用英文逗号分隔")
    args = ap.parse_args()

    fmt = "plain"
    plain = args.body
    html_part = None

    if args.markdown_file:
        md = read_file(args.markdown_file)
        plain = md  # md 源码本身即可读，直接作纯文本兜底
        html_part = md_to_html(md)
        fmt = "markdown"
    elif args.html_file:
        html_part = read_file(args.html_file)
        plain = html_to_plain(html_part)
        fmt = "html"
    elif args.body_file:
        plain = read_file(args.body_file)

    cfg = load_config()
    to_list = [a.strip() for a in args.to.split(",") if a.strip()]
    cc_list = [a.strip() for a in args.cc.split(",") if a.strip()]
    if not to_list:
        fail("收件人为空")

    name = cfg.get("name", "")
    from_hdr = formataddr((str(Header(name, "utf-8")), cfg["email"])) if name else cfg["email"]

    if html_part is not None:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html_part, "html", "utf-8"))
    else:
        msg = MIMEText(plain, "plain", "utf-8")

    msg["From"] = from_hdr
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
        "format": fmt,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
