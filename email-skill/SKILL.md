---
name: email-skill
description: "收发与管理个人邮箱：查看收件箱/未读邮件、搜索邮件、阅读全文、发送新邮件、回复邮件（带引用与线程头）、整理邮件（已读/星标/移动文件夹/删除/新建文件夹）。基于 IMAP/SMTP，支持 QQ/163/Gmail/Outlook 等常见邮箱。触发词：查邮件、发邮件、回复邮件、整理邮件、未读邮件、email、inbox。NOT for: 批量营销邮件群发、邮件营销自动化、访问他人邮箱。"
---

# 邮件 Skill（email-skill）

零依赖（Python 3 标准库 imaplib/smtplib/email），基于 IMAP + SMTP，免第三方库。

## 首次配置（仅一次）

复制 `config.example.json` 到 `~/.config/email-skill/config.json` 并填写：

```bash
mkdir -p ~/.config/email-skill
cp config.example.json ~/.config/email-skill/config.json
# 然后编辑填入 email 和 password
```

- **QQ/163/126 邮箱**：`password` 填**授权码**（网页邮箱 设置 → 账户 → 开启 IMAP/SMTP 服务时生成），不是登录密码
- **Gmail**：需开启两步验证后使用「应用专用密码」
- `imap_host`/`smtp_host` 留空即可，脚本按邮箱域名自动推断（QQ/163/Gmail/Outlook/iCloud/新浪/阿里/139 已内置预设）
- 也可用环境变量 `EMAIL_SKILL_CONFIG` 指定配置文件路径
- ⚠️ 配置文件含密码，不要提交进任何 git 仓库

## When to Use

✅ 用户说：查一下我的邮件 / 有未读邮件吗 / 发封邮件给 xx / 回复这封邮件 / 把这封邮件移到归档 / 搜索发票相关邮件

❌ 不适用：批量群发营销邮件、定时邮件自动化、没有凭据的邮箱

## 脚本一览（均在 scripts/ 下）

### 1. 列出文件夹 / 邮件列表 / 搜索

```bash
python3 scripts/list_mail.py --folders                 # 列出所有文件夹
python3 scripts/list_mail.py --limit 20                # INBOX 最近 20 封
python3 scripts/list_mail.py --unread                  # 仅未读
python3 scripts/list_mail.py --search 发票             # 关键词搜索
python3 scripts/list_mail.py --folder Sent --limit 10  # 指定文件夹
```

输出每封：`uid`、`date`、`from`、`subject`、`unread`。**后续所有操作都靠 uid**。

### 2. 阅读邮件全文

```bash
python3 scripts/read_mail.py --uid 123
```

- 输出正文（优先纯文本，HTML 自动转文本）、附件文件名列表、`message_id`
- 使用 `BODY.PEEK[]`，**不会把邮件标记为已读**

### 3. 发送新邮件

```bash
python3 scripts/send_mail.py --to a@b.com --subject "主题" --body "正文"
python3 scripts/send_mail.py --to a@b.com,b@c.com --cc d@e.com --subject "..." --body-file /tmp/body.txt
```

### 4. 回复邮件

```bash
python3 scripts/reply_mail.py --uid 123 --body "回复内容"
python3 scripts/reply_mail.py --uid 123 --body "..." --all   # 回复全部
```

- 自动加 `Re:` 前缀、原文引用（`>` 前缀）、`In-Reply-To`/`References` 线程头
- 回复完成后建议顺手标记已读：`organize_mail.py --uid 123 --action mark-read`

### 5. 整理邮件

```bash
python3 scripts/organize_mail.py --uid 1,2,3 --action mark-read     # 标已读
python3 scripts/organize_mail.py --uid 1 --action mark-unread       # 标未读
python3 scripts/organize_mail.py --uid 1 --action flag              # 加星标
python3 scripts/organize_mail.py --uid 1 --action move --target Archive  # 移动
python3 scripts/organize_mail.py --uid 1 --action delete            # 删除（优先移入 Trash）
python3 scripts/organize_mail.py --action mkdir --target "归档/2026"     # 新建文件夹
```

## 典型工作流

**查未读并汇报**：`list_mail.py --unread` → 逐封 `read_mail.py --uid`（按需）→ 用中文向用户汇总发件人/主题/要点

**回复邮件**：`list_mail.py --search 关键词` 找到邮件 → `read_mail.py` 读全文 → **把拟好的回复内容给用户确认** → `reply_mail.py --body-file` 发送 → `organize_mail.py --action mark-read`

**整理收件箱**：`list_mail.py --limit 50` → 按用户规则分类 → 批量 `organize_mail.py --uid ... --action move --target ...`

## 铁律

- **发送/回复前必须把收件人、主题、正文展示给用户确认**，得到明确同意后再执行（可用 `--body-file` 写长文）
- 禁止编造邮件内容或收件人地址；正文、地址必须来自用户或已读到的邮件
- 删除、移动等不可逆操作前，向用户说明影响范围（几封、哪些主题）再执行
- 脚本报错（登录失败/连接失败）时如实转述错误，不要假装操作成功
- 读取邮件用 PEEK 模式，除非用户要求，不改变邮件已读状态

## 降级策略

1. IMAP/SMTP 登录失败 → 提示检查授权码/是否开启服务，附配置文件路径
2. 中文搜索服务器不支持 → 脚本自动回退客户端过滤并在输出 `note` 中说明
3. 某文件夹打不开 → 先 `--folders` 列出真实文件夹名再重试

## 验证

配置完成后自检：`list_mail.py --folders` 能列出文件夹、`list_mail.py --limit 1` 能取到邮件，即配置正确。
