#!/usr/bin/env python3
"""列出邮箱文件夹 / 邮件列表 / 搜索邮件（IMAP，只读）。

用法：
  python3 list_mail.py --folders                      # 列出所有文件夹
  python3 list_mail.py                                # INBOX 最近 20 封
  python3 list_mail.py --folder INBOX --limit 10
  python3 list_mail.py --unread                       # 仅未读
  python3 list_mail.py --search 发票                  # 按关键词搜索（主题/发件人）
输出 JSON：{"ok": true, "messages": [{uid, date, from, subject, unread}...]}
"""
import argparse
import imaplib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mail_lib import (imap_conn, load_config, decode_str, addr_display,
                      imap_utf7_decode, fail)


def list_folders(conn):
    typ, data = conn.list()
    folders = []
    if typ == "OK":
        for line in data:
            if not line:
                continue
            s = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
            # 形如: (\HasNoChildren) "/" "INBOX"
            parts = s.rsplit(' "', 1)
            name = parts[-1].strip('"') if parts else s
            folders.append(imap_utf7_decode(name))
    return folders


def search_uids(conn, keyword, unread_only):
    """返回 (uid 列表新→旧, 是否需客户端过滤)。

    部分服务器（如 163）SEARCH 支持差：中文 CHARSET 报错、或 TEXT 匹配不到
    头字段。凡服务器搜索报错或结果为空，统一回退为拉取全部后客户端过滤。
    """
    criteria = "UNSEEN" if unread_only else "ALL"
    if keyword:
        for charset in ("UTF-8", None):
            try:
                if charset:
                    typ, data = conn.uid("SEARCH", "CHARSET", charset, "TEXT", keyword,
                                         *(["UNSEEN"] if unread_only else []))
                else:
                    typ, data = conn.uid("SEARCH", "TEXT", keyword,
                                         *(["UNSEEN"] if unread_only else []))
                if typ == "OK" and data[0] and data[0].split():
                    return [u.decode() for u in data[0].split()][::-1], False
            except imaplib.IMAP4.error:
                continue
        # 服务器搜索不可用或无结果 → 客户端过滤兜底
        typ, data = conn.uid("SEARCH", None, criteria)
        if typ != "OK":
            fail("IMAP 搜索失败")
        return [u.decode() for u in data[0].split()][::-1], True
    typ, data = conn.uid("SEARCH", None, criteria)
    if typ != "OK":
        fail("IMAP 搜索失败")
    return [u.decode() for u in data[0].split()][::-1], False


def fetch_headers(conn, uids):
    """批量取头字段与未读标记。"""
    result = {}
    if not uids:
        return result
    uid_set = ",".join(uids)
    typ, data = conn.uid("FETCH", uid_set,
                         "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
    if typ != "OK":
        return result
    cur_uid, cur_flags, cur_headers = None, [], b""
    for item in data:
        if not isinstance(item, tuple):
            continue
        meta, raw = item
        meta_s = meta.decode("utf-8", errors="replace")
        # meta 形如: 123 (UID 456 FLAGS (\Seen) BODY[...] {n}
        import re as _re
        m = _re.search(r"UID (\d+)", meta_s)
        if not m:
            continue
        uid = m.group(1)
        unread = "\\Seen" not in meta_s
        from email import message_from_bytes
        hmsg = message_from_bytes(raw)
        result[uid] = {
            "uid": uid,
            "date": hmsg.get("Date", ""),
            "from": addr_display(hmsg.get("From", "")),
            "subject": decode_str(hmsg.get("Subject", "")) or "(无主题)",
            "unread": unread,
        }
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folders", action="store_true", help="列出所有文件夹")
    ap.add_argument("--folder", default="INBOX", help="文件夹（默认 INBOX）")
    ap.add_argument("--limit", type=int, default=20, help="最多返回条数（默认 20）")
    ap.add_argument("--unread", action="store_true", help="仅未读")
    ap.add_argument("--search", default="", help="关键词（匹配主题/发件人等）")
    args = ap.parse_args()

    cfg = load_config()
    if args.folders:
        conn = imap_conn(cfg)
        folders = list_folders(conn)
        conn.logout()
        print(json.dumps({"ok": True, "folders": folders}, ensure_ascii=False, indent=2))
        return

    conn = imap_conn(cfg, folder=args.folder, readonly=True)
    uids, client_filter = search_uids(conn, args.search, args.unread)

    # 先取头（数量放宽以便客户端过滤后仍有足够条目）
    batch = uids[: args.limit * 5 if client_filter else args.limit]
    headers = fetch_headers(conn, batch)
    conn.logout()

    messages = []
    for uid in batch:  # batch 已是新→旧
        if uid not in headers:
            continue
        m = headers[uid]
        if client_filter and args.search:
            kw = args.search.lower()
            if kw not in m["subject"].lower() and kw not in m["from"].lower():
                continue
        messages.append(m)
        if len(messages) >= args.limit:
            break

    print(json.dumps({
        "ok": True,
        "folder": args.folder,
        "count": len(messages),
        "note": "服务器搜索不可用或无结果，已改客户端过滤（仅匹配主题/发件人）" if client_filter else None,
        "messages": messages,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
