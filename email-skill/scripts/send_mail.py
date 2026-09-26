#!/usr/bin/env python3
"""发送新邮件（SMTP）。默认纯文本；支持 Markdown / HTML 正文（multipart/alternative，
HTML 版 + 自动生成的纯文本兜底，老客户端也能读）；支持多个附件（--attach 可重复）。

HTML 正文里的**本地图片自动内嵌为 CID**（multipart/related）：晨报/晚报模板的图标
（assets/icons/*.png）在 Gmail / QQ / 163 里也能正常显示，不依赖外链图床、
也不会被「阻止加载远程图片」拦下。不想内嵌时加 --no-inline-images。

用法：
  python3 send_mail.py --to a@b.com --subject "主题" --body "正文"
  python3 send_mail.py --to a@b.com,b@c.com --cc d@e.com --subject "..." --body-file /tmp/body.txt
  python3 send_mail.py --to a@b.com --subject "..." --markdown-file report.md   # md 渲染为 HTML
  python3 send_mail.py --to a@b.com --subject "..." --html-file report.html     # 直接发 HTML（自动内嵌本地图标）
  python3 send_mail.py --to a@b.com --subject "..." --body "..." --account work # 指定发件账号
  python3 send_mail.py --to a@b.com --subject "..." --body "..." --attach 发票.pdf --attach 行程单.pdf
多账号配置下缺省用主账号（配置中的 primary）发送。附件中文文件名自动 RFC 2231 编码。
输出 JSON：{"ok": true, "to": [...], "subject": "...", "format": "plain|markdown|html",
           "attachments": [...], "inlined": N}
"""
import argparse
import json
import mimetypes
import os
import re
import sys
from email.encoders import encode_base64
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mail_lib import load_config, smtp_send, md_to_html, fail

MAX_ATTACH_TOTAL = 45 * 1024 * 1024  # 总附件上限（主流邮箱单封约 50MB，留余量）
IMG_TAG_RE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', re.I)


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
    t = re.sub(r"(?is)<img [^>]*alt=\"([^\"]*)\"[^>]*>", r"\1", t)
    t = re.sub(r"(?is)<br\s*/?>", "\n", t)
    t = re.sub(r"(?is)</(p|div|li|h[1-6]|tr|blockquote)>", "\n", t)
    t = re.sub(r"(?s)<[^>]+>", "", t)
    import html as html_mod
    return html_mod.unescape(t).strip()


def inline_images(html_text, base_dir=""):
    """把 HTML 里的本地图片转成 CID 内嵌。

    返回 (new_html, images)：images 为 [(cid, MIMEImage), ...]
    只处理本地存在的图片路径；http(s)/data:/cid: 一律跳过（保持原样）。
    """
    images = []
    counter = [0]

    def repl(m):
        head, src, tail = m.group(1), m.group(2), m.group(3)
        if re.match(r"(?i)^(https?:|data:|cid:|//)", src):
            return m.group(0)
        path = src if os.path.isabs(src) else os.path.join(base_dir, src)
        path = path.replace("file://", "")
        if not os.path.isfile(path):
            return m.group(0)
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            return m.group(0)
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        subtype = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg",
                   "gif": "gif", "webp": "webp", "svg": "svg+xml"}.get(ext, "png")
        counter[0] += 1
        cid = f"dshimg{counter[0]}.{ext or 'png'}@dsh"
        img = MIMEImage(data, _subtype=subtype)
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline",
                       filename=os.path.basename(path))
        images.append((cid, img))
        return head + "cid:" + cid + tail

    return IMG_TAG_RE.sub(repl, html_text), images


def build_message(plain, html_part, base_dir, inline=True):
    """组装邮件体：有内嵌图片时用 multipart/related 包住 multipart/alternative。

    返回 (msg, inlined_count)。外层如再有附件，由调用方包 multipart/mixed
    （最终结构 mixed → related → alternative，符合 RFC 2387 惯例）。
    """
    images = []
    if html_part is not None and inline:
        html_part, images = inline_images(html_part, base_dir)

    if html_part is None:
        return MIMEText(plain, "plain", "utf-8"), 0

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(plain, "plain", "utf-8"))
    alt.attach(MIMEText(html_part, "html", "utf-8"))
    if not images:
        return alt, 0

    root = MIMEMultipart("related")
    root.attach(alt)
    for _cid, img in images:
        root.attach(img)
    return root, len(images)


def make_attachment(path):
    """按扩展名猜 MIME 类型构造附件 part，返回 (part, 原始字节数)。"""
    fn = os.path.basename(path)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        fail(f"读取附件失败: {e}")
    ctype, _ = mimetypes.guess_type(fn)
    maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
    part = MIMEBase(maintype, subtype)
    part.set_payload(data)
    encode_base64(part)
    part.add_header("Content-Disposition", "attachment", filename=fn)
    return part, len(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True, help="收件人，多个用英文逗号分隔")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", default="", help="纯文本正文")
    ap.add_argument("--body-file", default="", help="从文件读取纯文本正文（优先于 --body）")
    ap.add_argument("--markdown-file", default="", help="Markdown 文件，渲染为 HTML 邮件")
    ap.add_argument("--html-file", default="", help="HTML 文件，直接作为 HTML 邮件")
    ap.add_argument("--cc", default="", help="抄送，多个用英文逗号分隔")
    ap.add_argument("--account", default="",
                    help="发件账号标签；缺省用主账号（primary）")
    ap.add_argument("--attach", action="append", default=[],
                    help="附件文件路径，可重复传多个")
    ap.add_argument("--no-inline-images", action="store_true",
                    help="不把 HTML 里的本地图片内嵌为 CID")
    args = ap.parse_args()

    fmt = "plain"
    plain = args.body
    html_part = None
    base_dir = ""

    if args.markdown_file:
        md = read_file(args.markdown_file)
        plain = md  # md 源码本身即可读，直接作纯文本兜底
        html_part = md_to_html(md)
        base_dir = os.path.dirname(os.path.abspath(args.markdown_file))
        fmt = "markdown"
    elif args.html_file:
        html_part = read_file(args.html_file)
        plain = html_to_plain(html_part)
        base_dir = os.path.dirname(os.path.abspath(args.html_file))
        fmt = "html"
    elif args.body_file:
        plain = read_file(args.body_file)

    cfg = load_config(args.account or None)
    to_list = [a.strip() for a in args.to.split(",") if a.strip()]
    cc_list = [a.strip() for a in args.cc.split(",") if a.strip()]
    if not to_list:
        fail("收件人为空")

    name = cfg.get("name", "")
    from_hdr = formataddr((str(Header(name, "utf-8")), cfg["email"])) if name else cfg["email"]

    msg, inlined = build_message(plain, html_part, base_dir,
                                 inline=not args.no_inline_images)

    # 附件：包一层 multipart/mixed
    attach_paths = []
    for p in args.attach:
        p = os.path.expanduser(p)
        if not os.path.isfile(p):
            fail(f"附件不存在: {p}")
        attach_paths.append(p)
    if attach_paths:
        total = sum(os.path.getsize(p) for p in attach_paths)
        if total > MAX_ATTACH_TOTAL:
            fail(f"附件总大小 {total / 1024 / 1024:.1f}MB，超过 {MAX_ATTACH_TOTAL // 1024 // 1024}MB 上限"
                 "（主流邮箱单封约限 50MB，建议压缩或分批发送）")
        outer = MIMEMultipart("mixed")
        outer.attach(msg)
        for p in attach_paths:
            part, _size = make_attachment(p)
            outer.attach(part)
        msg = outer

    msg["From"] = from_hdr
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = Header(args.subject, "utf-8")

    smtp_send(cfg, msg, to_list + cc_list)
    print(json.dumps({
        "ok": True,
        "account": cfg["_account"],
        "from": cfg["email"],
        "to": to_list,
        "cc": cc_list,
        "subject": args.subject,
        "format": fmt,
        "attachments": [os.path.basename(p) for p in attach_paths],
        "inlined": inlined,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
