#!/usr/bin/env python3
"""列出邮箱文件夹 / 邮件列表 / 搜索邮件（IMAP，只读）。

用法：
  python3 list_mail.py --folders                      # 列出所有账号的文件夹
  python3 list_mail.py                                # 聚合所有账号 INBOX 最近 20 封
  python3 list_mail.py --account qq --limit 10        # 只看指定账号
  python3 list_mail.py --folder INBOX --limit 10
  python3 list_mail.py --unread                       # 仅未读（所有账号）
  python3 list_mail.py --search 发票                  # 按关键词搜索（主题/发件人）
多账号配置下默认聚合所有账号，每封邮件带 account 字段，按日期新→旧排序；
单个账号连接失败不阻塞其他账号，错误记入输出的 errors 字段。
输出 JSON：{"ok": true, "messages": [{account, uid, date, from, subject, unread}...]}
"""
import argparse
import contextlib
import imaplib
import io
import json
import os
import sys
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mail_lib import (imap_conn, load_accounts, load_config, decode_str,
                      addr_display, imap_utf7_decode, fail)


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


def list_messages_for_account(cfg, args):
    """单账号收取，返回 (messages, client_filter)。异常经 fail → SystemExit 上抛。"""
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
        m["account"] = cfg["_account"]
        messages.append(m)
        if len(messages) >= args.limit:
            break
    return messages, client_filter


def date_key(m):
    """邮件日期排序键（新→旧），解析失败排最后。"""
    try:
        return -parsedate_to_datetime(m.get("date") or "").timestamp()
    except (TypeError, ValueError, OverflowError):
        return float("inf")


def run_captured(fn, *fn_args):
    """运行单账号操作；fail() 的 SystemExit 转为 (None, error_msg)，不阻塞其他账号。"""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            return fn(*fn_args), None
    except SystemExit as e:
        if e.code in (0, None):
            return None, None
        err = "操作失败"
        try:
            err = json.loads(buf.getvalue()).get("error", err)
        except (ValueError, AttributeError):
            pass
        return None, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folders", action="store_true", help="列出所有文件夹")
    ap.add_argument("--account", default="",
                    help="账号标签；多账号配置下缺省聚合所有账号")
    ap.add_argument("--folder", default="INBOX", help="文件夹（默认 INBOX）")
    ap.add_argument("--limit", type=int, default=20, help="最多返回条数（默认 20）")
    ap.add_argument("--unread", action="store_true", help="仅未读")
    ap.add_argument("--search", default="", help="关键词（匹配主题/发件人等）")
    args = ap.parse_args()

    accounts, primary = load_accounts()
    targets = [load_config(args.account)] if args.account else accounts
    multi = len(targets) > 1

    if args.folders:
        if not multi:
            conn = imap_conn(targets[0])
            folders = list_folders(conn)
            conn.logout()
            print(json.dumps({"ok": True, "account": targets[0]["_account"],
                              "folders": folders}, ensure_ascii=False, indent=2))
            return
        per_account, errors = {}, []
        for cfg in targets:
            def _folders(c=cfg):
                conn = imap_conn(c)
                try:
                    return list_folders(conn)
                finally:
                    conn.logout()
            res, err = run_captured(_folders)
            if err:
                errors.append({"account": cfg["_account"], "error": err})
            else:
                per_account[cfg["_account"]] = res
        print(json.dumps({"ok": not errors or bool(per_account),
                          "primary": primary,
                          "folders": per_account,
                          "errors": errors or None},
                         ensure_ascii=False, indent=2))
        return

    all_messages, errors = [], []
    client_filter_used = False
    for cfg in targets:
        res, err = run_captured(list_messages_for_account, cfg, args)
        if err:
            errors.append({"account": cfg["_account"], "error": err})
            continue
        messages, client_filter = res
        client_filter_used = client_filter_used or client_filter
        all_messages.extend(messages)

    if errors and not multi:
        fail(errors[0]["error"])  # 单账号保持旧行为：直接报错并非零退出

    # 聚合时跨账号按日期新→旧排序并应用总 limit
    if multi:
        all_messages.sort(key=date_key)
        all_messages = all_messages[: args.limit]

    out = {
        "ok": True,
        "folder": args.folder,
        "count": len(all_messages),
        "note": "服务器搜索不可用或无结果，已改客户端过滤（仅匹配主题/发件人）"
                if client_filter_used else None,
        "messages": all_messages,
    }
    if multi:
        out["accounts"] = [c["_account"] for c in targets]
        out["primary"] = primary
    if errors:
        out["errors"] = errors
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
