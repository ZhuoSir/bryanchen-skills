#!/usr/bin/env python3
"""下载指定邮件的附件（IMAP，BODY.PEEK 只读，不改变已读状态）。

用法：
  python3 download_attachment.py --account qq2 --uid 123 --list              # 先列出附件（名称/大小）
  python3 download_attachment.py --account qq2 --uid 123                      # 下载全部附件
  python3 download_attachment.py --account qq2 --uid 123 --filename 发票      # 只下载名称包含关键词的附件
  python3 download_attachment.py --account qq2 --uid 123 --output-dir /tmp/x  # 指定保存目录
多账号配置下 --account 必填（uid 只在单账号内有意义，账号见 list_mail.py 输出的 account 字段）。
默认保存到 ~/Downloads/email-skill/，重名自动加 (1)(2) 后缀，不覆盖已有文件。
输出 JSON：{"ok": true, "saved": [{"filename", "path", "size"}...]}
"""
import argparse
import email
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mail_lib import imap_conn, require_account, decode_str, fail

DEFAULT_OUTDIR = os.path.expanduser("~/Downloads/email-skill")


def sanitize(name):
    """去掉文件系统非法字符，保留中文。"""
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name).strip(" .")
    return name or "attachment"


def iter_attachments(msg):
    """遍历邮件部件，返回 (解码后文件名, part) 列表。

    判定：有 filename，或 Content-Disposition 为 attachment。
    内联图片（带文件名）也会列出，由用户决定下载与否。
    """
    found = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        fn = part.get_filename()
        disp = str(part.get("Content-Disposition") or "").lower()
        if not fn and "attachment" not in disp:
            continue
        found.append((decode_str(fn) if fn else "unnamed", part))
    return found


def unique_path(directory, filename):
    """重名时自动加 (1)(2)... 后缀。"""
    path = os.path.join(directory, sanitize(filename))
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(sanitize(filename))
    i = 1
    while True:
        path = os.path.join(directory, f"{stem}({i}){ext}")
        if not os.path.exists(path):
            return path
        i += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uid", required=True, help="邮件 UID（由 list_mail.py 获得）")
    ap.add_argument("--account", default="", help="邮件所属账号标签（多账号必填）")
    ap.add_argument("--folder", default="INBOX")
    ap.add_argument("--list", action="store_true", help="只列出附件不下载")
    ap.add_argument("--filename", default="",
                    help="只下载文件名包含该关键词的附件（不区分大小写）")
    ap.add_argument("--output-dir", default=DEFAULT_OUTDIR,
                    help=f"保存目录（默认 {DEFAULT_OUTDIR}）")
    args = ap.parse_args()

    cfg = require_account(args.account, purpose="下载附件")
    conn = imap_conn(cfg, folder=args.folder, readonly=True)
    typ, data = conn.uid("FETCH", args.uid, "(BODY.PEEK[])")
    conn.logout()
    if typ != "OK" or not data or not isinstance(data[0], tuple):
        fail(f"未找到 UID={args.uid} 的邮件（account={cfg['_account']}, folder={args.folder}）")

    msg = email.message_from_bytes(data[0][1])
    subject = decode_str(msg.get("Subject", "")) or "(无主题)"
    attachments = iter_attachments(msg)
    if not attachments:
        print(json.dumps({"ok": True, "account": cfg["_account"], "uid": args.uid,
                          "subject": subject, "attachments": [],
                          "note": "该邮件没有附件"}, ensure_ascii=False, indent=2))
        return

    if args.filename:
        kw = args.filename.lower()
        attachments = [(fn, p) for fn, p in attachments if kw in fn.lower()]
        if not attachments:
            fail(f"没有文件名包含「{args.filename}」的附件",
                 hint="先用 --list 查看所有附件名")

    if args.list:
        print(json.dumps({
            "ok": True, "account": cfg["_account"], "uid": args.uid,
            "subject": subject,
            "attachments": [{"filename": fn,
                             "size": len(p.get_payload(decode=True) or b"")}
                            for fn, p in attachments],
        }, ensure_ascii=False, indent=2))
        return

    outdir = os.path.expanduser(args.output_dir)
    try:
        os.makedirs(outdir, exist_ok=True)
    except OSError as e:
        fail(f"创建保存目录失败: {e}")

    saved, failed = [], []
    for fn, part in attachments:
        payload = part.get_payload(decode=True)
        if payload is None:
            failed.append({"filename": fn, "error": "无法解码附件内容"})
            continue
        path = unique_path(outdir, fn)
        try:
            with open(path, "wb") as f:
                f.write(payload)
        except OSError as e:
            failed.append({"filename": fn, "error": str(e)})
            continue
        saved.append({"filename": fn, "path": path, "size": len(payload)})

    out = {"ok": bool(saved) and not failed, "account": cfg["_account"],
           "uid": args.uid, "subject": subject, "output_dir": outdir,
           "saved": saved}
    if failed:
        out["failed"] = failed
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if not saved:
        sys.exit(1)


if __name__ == "__main__":
    main()
