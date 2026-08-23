#!/usr/bin/env python3
"""email-skill 共享工具库：配置加载、IMAP/SMTP 连接、MIME 解析。

仅依赖 Python 3 标准库。配置文件 JSON，查找顺序：
1. 环境变量 EMAIL_SKILL_CONFIG 指定的路径
2. ~/.config/email-skill/config.json
3. ~/.email-skill.json

配置格式（imap/smtp 主机可省略，按邮箱域名自动推断）：
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
"""
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


def load_config():
    path_used = None
    cfg = None
    candidates = [
        os.environ.get("EMAIL_SKILL_CONFIG"),
        os.path.expanduser("~/.config/email-skill/config.json"),
        os.path.expanduser("~/.email-skill.json"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    cfg = json.load(f)
                path_used = p
                break
            except Exception as e:
                fail(f"配置文件解析失败: {p}: {e}")
    if cfg is None:
        fail("未找到配置文件。请创建 ~/.config/email-skill/config.json"
             "（参考 skill 目录下 config.example.json），或设置 EMAIL_SKILL_CONFIG 环境变量。")

    email_addr = cfg.get("email", "")
    if "@" not in email_addr:
        fail("配置缺少有效 email 字段", config=path_used)
    if not cfg.get("password"):
        fail("配置缺少 password 字段（QQ/163 等需用授权码而非登录密码）", config=path_used)

    domain = email_addr.split("@")[-1].lower()
    preset = PRESETS.get(domain)
    if preset:
        cfg.setdefault("imap_host", preset[0])
        cfg.setdefault("imap_port", preset[1])
        cfg.setdefault("smtp_host", preset[2])
        cfg.setdefault("smtp_port", preset[3])
        cfg.setdefault("smtp_starttls", preset[4])
    for k in ("imap_host", "smtp_host"):
        if not cfg.get(k):
            fail(f"配置缺少 {k}，且域名 {domain} 无内置预设，请在配置中显式填写", config=path_used)
    cfg.setdefault("imap_port", 993)
    cfg.setdefault("smtp_port", 465)
    cfg.setdefault("smtp_starttls", False)
    cfg["_path"] = path_used
    return cfg


def imap_conn(cfg, folder=None, readonly=True):
    """建立 IMAP 连接并登录；folder 非空时选中该文件夹。"""
    try:
        conn = imaplib.IMAP4_SSL(cfg["imap_host"], int(cfg["imap_port"]))
        conn.login(cfg["email"], cfg["password"])
    except imaplib.IMAP4.error as e:
        fail(f"IMAP 登录失败：{e}（QQ/163 等需开启 IMAP 服务并使用授权码）")
    except OSError as e:
        fail(f"IMAP 连接失败 {cfg['imap_host']}:{cfg['imap_port']}: {e}")
    if folder:
        typ, _ = conn.select(folder, readonly=readonly)
        if typ != "OK":
            conn.logout()
            fail(f"无法打开文件夹: {folder}", hint="用 list_mail.py --folders 查看可用文件夹")
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
        text = re.sub(r"(?is)</p>", "\n\n", text)
        text = re.sub(r"(?s)<[^>]+>", "", text)
        import html as html_mod
        return html_mod.unescape(text).strip(), "html"
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
