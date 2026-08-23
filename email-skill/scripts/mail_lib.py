#!/usr/bin/env python3
"""email-skill 共享工具库：配置加载、IMAP/SMTP 连接、MIME 解析。

仅依赖 Python 3 标准库。配置文件 JSON，查找顺序：
1. 环境变量 EMAIL_SKILL_CONFIG 指定的路径
2. ~/.config/email-skill/config.json
3. ~/.email-skill.json

配置格式（imap/smtp 主机可省略，按邮箱域名自动推断）。

单账号（旧格式，仍兼容）：
{
  "email": "you@qq.com",
  "password": "授权码或密码",
  "name": "你的名字",            // 可选，发件人显示名
  "imap_host": "imap.qq.com",   // 可选
  "imap_port": 993,             // 可选
  "smtp_host": "smtp.qq.com",   // 可选
  "smtp_port": 465,             // 可选
  "smtp_starttls": false        // 可选，587 端口通常需要 true
}

多账号（accounts 列表 + primary 主账号）：
{
  "primary": "qq",              // 主账号标签：发送新邮件默认用它
  "accounts": [
    {"account": "qq",   "email": "a@qq.com",  "password": "...", "name": "张三"},
    {"account": "work", "email": "b@163.com", "password": "...", "name": "张三"}
  ]
}
- 每个账号条目字段与单账号格式相同，额外的 "account" 为账号标签（缺省用 email）
- 收取：list_mail.py 默认聚合所有账号；read/reply/organize 用 --account 指定
- 发送新邮件默认主账号；回复邮件用 --account 指定收到该邮件的账号
"""
import base64
import imaplib
import json
import os
import re
import smtplib
import sys
from email.header import decode_header
from email.utils import parseaddr

# 常见邮箱服务商预设：(imap_host, imap_port, smtp_host, smtp_port, smtp_starttls)
PRESETS = {
    "qq.com": ("imap.qq.com", 993, "smtp.qq.com", 465, False),
    "foxmail.com": ("imap.qq.com", 993, "smtp.qq.com", 465, False),
    "163.com": ("imap.163.com", 993, "smtp.163.com", 465, False),
    "126.com": ("imap.126.com", 993, "smtp.126.com", 465, False),
    "yeah.net": ("imap.yeah.net", 993, "smtp.yeah.net", 465, False),
    "gmail.com": ("imap.gmail.com", 993, "smtp.gmail.com", 465, False),
    "outlook.com": ("imap-mail.outlook.com", 993, "smtp.office365.com", 587, True),
    "hotmail.com": ("imap-mail.outlook.com", 993, "smtp.office365.com", 587, True),
    "icloud.com": ("imap.mail.me.com", 993, "smtp.mail.me.com", 587, True),
    "sina.com": ("imap.sina.com", 993, "smtp.sina.com", 465, False),
    "aliyun.com": ("imap.aliyun.com", 993, "smtp.aliyun.com", 465, False),
    "139.com": ("imap.139.com", 993, "smtp.139.com", 465, False),
}

MAX_BODY_CHARS = 20000  # 正文输出上限，防止超长邮件刷屏


def fail(msg, **extra):
    """输出 JSON 错误并以非零码退出。"""
    out = {"ok": False, "error": msg}
    out.update(extra)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(1)


def _load_raw():
    """读取配置文件原始 JSON，返回 (cfg_dict, path)。"""
    candidates = [
        os.environ.get("EMAIL_SKILL_CONFIG"),
        os.path.expanduser("~/.config/email-skill/config.json"),
        os.path.expanduser("~/.email-skill.json"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f), p
            except Exception as e:
                fail(f"配置文件解析失败: {p}: {e}")
    fail("未找到配置文件。请创建 ~/.config/email-skill/config.json"
         "（参考 skill 目录下 config.example.json），或设置 EMAIL_SKILL_CONFIG 环境变量。")


def _normalize_account(acc, path):
    """校验单个账号配置并按域名补全预设，返回补全后的 dict。"""
    acc = dict(acc)
    email_addr = acc.get("email", "")
    if "@" not in email_addr:
        fail("配置缺少有效 email 字段", config=path)
    if not acc.get("password"):
        fail(f"账号 {email_addr} 缺少 password 字段（QQ/163 等需用授权码而非登录密码）",
             config=path)

    domain = email_addr.split("@")[-1].lower()
    preset = PRESETS.get(domain)
    if preset:
        acc.setdefault("imap_host", preset[0])
        acc.setdefault("imap_port", preset[1])
        acc.setdefault("smtp_host", preset[2])
        acc.setdefault("smtp_port", preset[3])
        acc.setdefault("smtp_starttls", preset[4])
    for k in ("imap_host", "smtp_host"):
        if not acc.get(k):
            fail(f"账号 {email_addr} 缺少 {k}，且域名 {domain} 无内置预设，请在配置中显式填写",
                 config=path)
    acc.setdefault("imap_port", 993)
    acc.setdefault("smtp_port", 465)
    acc.setdefault("smtp_starttls", False)
    acc["_path"] = path
    return acc


def load_accounts():
    """加载全部账号，返回 (accounts, primary_label)。

    accounts 为规范化后的账号 dict 列表，每个含 "_account" 标签与 "_path"。
    兼容旧单账号格式（无 accounts 字段时整个配置即唯一账号）。
    """
    raw, path = _load_raw()
    if isinstance(raw, dict) and isinstance(raw.get("accounts"), list) and raw["accounts"]:
        accounts = []
        for i, entry in enumerate(raw["accounts"]):
            if not isinstance(entry, dict):
                fail(f"accounts[{i}] 不是对象", config=path)
            label = entry.get("account") or entry.get("email", f"account-{i}")
            acc = _normalize_account(entry, path)
            acc["_account"] = label
            accounts.append(acc)
        labels = [a["_account"] for a in accounts]
        if len(set(labels)) != len(labels):
            fail(f"账号标签重复：{labels}（请为每个账号设置不同的 account 字段）", config=path)
        primary = raw.get("primary") or labels[0]
        if primary not in labels:
            fail(f"primary 账号 '{primary}' 不在 accounts 中（可选：{', '.join(labels)}）",
                 config=path)
        return accounts, primary
    # 旧单账号格式
    if not isinstance(raw, dict):
        fail("配置文件格式错误：顶层必须是 JSON 对象", config=path)
    acc = _normalize_account(raw, path)
    acc["_account"] = raw.get("account") or raw.get("email", "default")
    return [acc], acc["_account"]


def load_config(account=None):
    """加载指定账号配置；account=None 时用主账号（发送新邮件的默认账号）。"""
    accounts, primary = load_accounts()
    if account is None:
        account = primary
    for acc in accounts:
        if acc["_account"] == account:
            return acc
    fail(f"未知账号 '{account}'"
         f"（可选：{', '.join(a['_account'] for a in accounts)}；主账号：{primary}）")


def require_account(account, purpose="该操作"):
    """read/reply/organize 等按 UID 操作的账号解析。

    多账号配置下必须显式 --account（UID 只在单账号内有意义，跨账号会撞号），
    单账号配置直接返回唯一账号，保持旧行为。
    """
    accounts, primary = load_accounts()
    if account:
        return load_config(account)
    if len(accounts) > 1:
        fail(f"{purpose}在多账号配置下必须用 --account 指定邮件所属账号"
             f"（可选：{', '.join(a['_account'] for a in accounts)}；主账号：{primary}）。"
             "邮件所属账号见 list_mail.py 输出中每封邮件的 account 字段。")
    return accounts[0]


def imap_utf7_decode(s):
    """解码 RFC 3501 修改版 UTF-7（IMAP 文件夹名，如 &g0l6P3ux- → 草稿箱）。"""
    out = []
    i = 0
    while i < len(s):
        if s[i] == "&":
            j = s.find("-", i)
            if j == -1:
                out.append(s[i:])
                break
            chunk = s[i + 1:j]
            if chunk == "":
                out.append("&")
            else:
                b64 = chunk.replace(",", "/")
                b64 += "=" * ((-len(b64)) % 4)
                try:
                    out.append(base64.b64decode(b64).decode("utf-16-be", errors="replace"))
                except Exception:
                    out.append(s[i:j + 1])
            i = j + 1
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def imap_utf7_encode(s):
    """编码为 RFC 3501 修改版 UTF-7（中文文件夹名 → IMAP 形式）。"""
    out, buf = [], []

    def flush():
        if buf:
            b = base64.b64encode("".join(buf).encode("utf-16-be")).decode()
            out.append("&" + b.rstrip("=").replace("/", ",") + "-")
            buf.clear()

    for ch in s:
        o = ord(ch)
        if 0x20 <= o <= 0x7E:
            flush()
            out.append("&-" if ch == "&" else ch)
        else:
            buf.append(ch)
    flush()
    return "".join(out)


def _send_id(conn):
    """发送 IMAP ID 命令（163/QQ 等国内邮箱要求，否则 SELECT 会被拒绝）。"""
    try:
        if "ID" not in imaplib.Commands:
            imaplib.Commands["ID"] = ("AUTH", "SELECTED")
        conn._simple_command("ID", '("name" "email-skill" "version" "1.0" "vendor" "bryanchen-skills")')
    except Exception:
        pass  # 不支持 ID 的服务器忽略


def imap_conn(cfg, folder=None, readonly=True):
    """建立 IMAP 连接并登录；folder 非空时选中该文件夹。"""
    try:
        conn = imaplib.IMAP4_SSL(cfg["imap_host"], int(cfg["imap_port"]))
        conn.login(cfg["email"], cfg["password"])
    except imaplib.IMAP4.error as e:
        fail(f"IMAP 登录失败：{e}（QQ/163 等需开启 IMAP 服务并使用授权码）")
    except OSError as e:
        fail(f"IMAP 连接失败 {cfg['imap_host']}:{cfg['imap_port']}: {e}")
    _send_id(conn)
    if folder:
        quoted = f'"{imap_utf7_encode(folder)}"'
        typ, resp = conn.select(quoted, readonly=readonly)
        if typ != "OK":
            conn.logout()
            fail(f"无法打开文件夹: {folder}（{resp}）",
                 hint="用 list_mail.py --folders 查看可用文件夹")
    return conn


def smtp_send(cfg, msg, to_addrs):
    """通过 SMTP 发送 email.message.Message 对象。"""
    try:
        if cfg.get("smtp_starttls"):
            s = smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=30)
            s.ehlo()
            s.starttls()
            s.ehlo()
        else:
            s = smtplib.SMTP_SSL(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=30)
        s.login(cfg["email"], cfg["password"])
        s.sendmail(cfg["email"], to_addrs, msg.as_string())
        s.quit()
    except smtplib.SMTPAuthenticationError as e:
        fail(f"SMTP 登录失败：{e}（QQ/163 等需用授权码）")
    except (smtplib.SMTPException, OSError) as e:
        fail(f"SMTP 发送失败 {cfg['smtp_host']}:{cfg['smtp_port']}: {e}")


def decode_str(s):
    """解码 MIME 编码的头字段（如 =?UTF-8?B?...?=）。"""
    if not s:
        return ""
    parts = []
    for text, charset in decode_header(s):
        if isinstance(text, bytes):
            try:
                parts.append(text.decode(charset or "utf-8", errors="replace"))
            except (LookupError, TypeError):
                parts.append(text.decode("utf-8", errors="replace"))
        else:
            parts.append(text)
    return "".join(parts)


def addr_display(header_val):
    """从地址头提取 '名字 <addr>' 的友好形式。"""
    name, addr = parseaddr(header_val or "")
    name = decode_str(name)
    return f"{name} <{addr}>" if name else (addr or "")


def extract_body(msg):
    """提取正文：优先 text/plain，否则 text/html 去标签。"""
    plain, html = None, None
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp.lower():
                continue
            if ctype == "text/plain" and plain is None:
                plain = part
            elif ctype == "text/html" and html is None:
                html = part
    else:
        if msg.get_content_type() == "text/html":
            html = msg
        else:
            plain = msg

    def payload(p):
        raw = p.get_payload(decode=True) or b""
        charset = p.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")

    if plain is not None:
        return payload(plain), "plain"
    if html is not None:
        text = payload(html)
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
        text = re.sub(r"(?is)<br\s*/?>", "\n", text)
        text = re.sub(r"(?is)</(p|div|tr|table|h[1-6]|li)>", "\n", text)
        text = re.sub(r"(?s)<[^>]+>", "", text)
        import html as html_mod
        text = html_mod.unescape(text)
        # 折叠表格套表格留下的大量空白：清理每行尾部空白、压缩连续空行
        lines = [ln.strip() for ln in text.splitlines()]
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
        return text, "html"
    return "", "empty"


def list_attachments(msg):
    """返回附件文件名列表。"""
    names = []
    for part in msg.walk():
        disp = str(part.get("Content-Disposition") or "")
        if "attachment" in disp.lower():
            fn = part.get_filename()
            if fn:
                names.append(decode_str(fn))
    return names


def truncate(text, limit=MAX_BODY_CHARS):
    if len(text) > limit:
        return text[:limit] + f"\n... [正文过长已截断，共 {len(text)} 字符]"
    return text


def md_to_html(md_text):
    """极简 Markdown → HTML 转换器（用于 HTML 邮件）。

    支持：# 标题、**粗体**、`代码`、[链接](url)、裸 URL 自动链接、
    - / · 无序列表、1. 有序列表、> 引用、--- / ─── 分隔线、普通段落。
    """
    import html as html_mod

    def inline(t):
        t = html_mod.escape(t)
        t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                   r'<a href="\2" style="color:#1a73e8">\1</a>', t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        # 裸 URL 自动链接（排除已进入 href 属性的）
        t = re.sub(r'(?<!["=])(https?://[^\s<"]+)',
                   r'<a href="\1" style="color:#1a73e8">\1</a>', t)
        return t

    out = []
    list_type = None      # 当前打开的列表：ul / ol
    in_quote = False

    def close_blocks():
        nonlocal list_type, in_quote
        if list_type:
            out.append(f"</{list_type}>")
            list_type = None
        if in_quote:
            out.append("</blockquote>")
            in_quote = False

    for raw in md_text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        m = re.match(r"^(#{1,4})\s+(.*)", stripped)
        if m:
            close_blocks()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            continue

        if re.match(r"^(-{3,}|─{3,}|—{3,}|\*{3,})$", stripped):
            close_blocks()
            out.append('<hr style="border:none;border-top:1px solid #ddd">')
            continue

        m = re.match(r"^[-*·]\s+(.*)", stripped)
        if m:
            if in_quote:
                out.append("</blockquote>"); in_quote = False
            if list_type != "ul":
                if list_type:
                    out.append(f"</{list_type}>")
                out.append("<ul>"); list_type = "ul"
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue

        m = re.match(r"^(\d+)[.、]\s+(.*)", stripped)
        if m:
            if in_quote:
                out.append("</blockquote>"); in_quote = False
            if list_type != "ol":
                if list_type:
                    out.append(f"</{list_type}>")
                out.append("<ol>"); list_type = "ol"
            out.append(f"<li>{inline(m.group(2))}</li>")
            continue

        if stripped.startswith(">"):
            if list_type:
                out.append(f"</{list_type}>"); list_type = None
            if not in_quote:
                out.append('<blockquote style="border-left:3px solid #ccc;'
                           'margin:8px 0;padding-left:12px;color:#555">')
                in_quote = True
            content = stripped.lstrip(">").strip()
            if content:
                out.append(f"<div>{inline(content)}</div>")
            continue

        close_blocks()
        if stripped:
            out.append(f"<p>{inline(stripped)}</p>")

    close_blocks()
    body = "\n".join(out)
    return ('<div style="font-family:-apple-system,PingFang SC,Microsoft YaHei,'
            'sans-serif;font-size:15px;line-height:1.7;color:#222">'
            f"{body}</div>")
