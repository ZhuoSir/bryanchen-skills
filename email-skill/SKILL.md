---
name: email-skill
description: "收发与管理个人邮箱：查看收件箱/未读邮件（支持多账号聚合收取）、搜索邮件、阅读全文、发送新邮件（默认主账号）、回复邮件（从收件账号发出，带引用与线程头）、整理邮件（已读/星标/移动文件夹/删除/新建文件夹）。基于 IMAP/SMTP，支持 QQ/163/Gmail/Outlook 等常见邮箱。触发词：查邮件、发邮件、回复邮件、整理邮件、未读邮件、email、inbox。NOT for: 批量营销邮件群发、邮件营销自动化、访问他人邮箱。"
---

# 邮件 Skill（email-skill）

零依赖（Python 3 标准库 imaplib/smtplib/email），基于 IMAP + SMTP，免第三方库。

## 首次配置（仅一次）

复制 `config.example.json` 到 `~/.config/email-skill/config.json` 并填写：

```bash
mkdir -p ~/.config/email-skill
cp config.example.json ~/.config/email-skill/config.json
# 然后编辑填入各账号的 email 和 password
```

**多账号配置（推荐）**：

```json
{
  "primary": "qq",
  "accounts": [
    {"account": "qq",   "email": "a@qq.com",  "password": "授权码", "name": "张三"},
    {"account": "work", "email": "b@163.com", "password": "授权码", "name": "张三"}
  ]
}
```

- `primary`：**主账号**标签，发送新邮件默认从它发出
- `accounts`：每个账号一条，`account` 是账号标签（后续 `--account` 参数用它）；`imap_host`/`smtp_host` 可省略，按邮箱域名自动推断
- 也兼容**旧单账号格式**（顶层直接写 `email`/`password`，无 `accounts`），行为与多账号完全一致（唯一账号即主账号）

**多账号行为约定**：

| 操作 | 默认账号 |
|---|---|
| `list_mail.py` 收取/搜索 | **聚合所有账号**，每条邮件带 `account` 字段，按日期排序；`--account xx` 只看单个 |
| `send_mail.py` 发新邮件 | **主账号**（可用 `--account` 覆盖） |
| `reply_mail.py` 回复 | **必须 `--account` 指定收到该邮件的账号**（回复从该账号发出；UID 跨账号会撞号，故不猜） |
| `read_mail.py` 读全文 | 主账号，找不到时按提示加 `--account` |
| `organize_mail.py` 整理 | **必须 `--account`**；不同账号分批整理 |

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
python3 scripts/list_mail.py --folders                 # 列出所有账号的文件夹
python3 scripts/list_mail.py --limit 20                # 聚合所有账号 INBOX 最近 20 封
python3 scripts/list_mail.py --account work --limit 10 # 只看指定账号
python3 scripts/list_mail.py --unread                  # 仅未读（所有账号）
python3 scripts/list_mail.py --search 发票             # 关键词搜索
python3 scripts/list_mail.py --folder Sent --limit 10  # 指定文件夹
```

输出每封：`account`（所属账号）、`uid`、`date`、`from`、`subject`、`unread`。**后续所有操作都靠 account + uid**。单个账号连接失败不阻塞其他账号，错误在输出 `errors` 字段。

### 2. 阅读邮件全文

```bash
python3 scripts/read_mail.py --uid 123 --account work   # --account 为邮件所属账号（多账号时按 list 输出填写）
```

- 输出正文（优先纯文本，HTML 自动转文本）、附件文件名列表、`message_id`
- 使用 `BODY.PEEK[]`，**不会把邮件标记为已读**

### 3. 发送新邮件

```bash
python3 scripts/send_mail.py --to a@b.com --subject "主题" --body "正文"
python3 scripts/send_mail.py --to a@b.com,b@c.com --cc d@e.com --subject "..." --body-file /tmp/body.txt
python3 scripts/send_mail.py --to a@b.com --subject "..." --markdown-file report.md   # Markdown 渲染为 HTML 邮件
python3 scripts/send_mail.py --to a@b.com --subject "..." --html-file report.html     # 直接发 HTML
python3 scripts/send_mail.py --to a@b.com --subject "..." --body "..." --account qq   # 指定发件账号
```

- **默认从主账号（配置中的 `primary`）发出**，`--account` 可指定其他账号
- 默认纯文本。**正文含链接/排版时用 `--markdown-file`**：`[来源](url)` 渲染成超链接，长 URL 不会裸露刷屏
- Markdown/HTML 模式自动带纯文本兜底（multipart/alternative），老客户端也能读
- Markdown 支持：`#` 标题、`**粗体**`、`[链接](url)`、裸 URL 自动链接、`-`/`1.` 列表、`>` 引用、`---` 分隔线

### 4. 回复邮件

```bash
python3 scripts/reply_mail.py --uid 123 --account work --body "回复内容"   # --account = 收到该邮件的账号
python3 scripts/reply_mail.py --uid 123 --account work --body "..." --all  # 回复全部
```

- 自动加 `Re:` 前缀、原文引用（`>` 前缀）、`In-Reply-To`/`References` 线程头
- **回复从收到该邮件的账号发出**（多账号配置下 `--account` 必填，取 list 输出的 `account` 字段）
- 回复完成后建议顺手标记已读：`organize_mail.py --account work --uid 123 --action mark-read`

### 5. 整理邮件

```bash
python3 scripts/organize_mail.py --account work --uid 1,2,3 --action mark-read     # 标已读
python3 scripts/organize_mail.py --account work --uid 1 --action mark-unread       # 标未读
python3 scripts/organize_mail.py --account work --uid 1 --action flag              # 加星标
python3 scripts/organize_mail.py --account work --uid 1 --action move --target Archive  # 移动
python3 scripts/organize_mail.py --account work --uid 1 --action delete            # 删除（优先移入 Trash）
python3 scripts/organize_mail.py --account work --action mkdir --target "归档/2026"     # 新建文件夹
```

多账号配置下 `--account` 必填；要同时整理多个账号的邮件，按账号分批执行。

## 典型工作流

**查未读并汇报**：`list_mail.py --unread`（自动聚合所有账号）→ 逐封 `read_mail.py --account <账号> --uid <uid>`（按需）→ 用中文向用户汇总发件人/主题/要点（注明来自哪个账号）

**回复邮件**：`list_mail.py --search 关键词` 找到邮件（记下其 `account` 字段）→ `read_mail.py --account ...` 读全文 → **把拟好的回复内容给用户确认** → `reply_mail.py --account ... --body-file` 发送 → `organize_mail.py --account ... --action mark-read`

**整理收件箱**：`list_mail.py --limit 50` → 按用户规则分类 → 按账号分批 `organize_mail.py --account ... --uid ... --action move --target ...`

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

配置完成后自检：`list_mail.py --folders` 能列出各账号文件夹、`list_mail.py --limit 1` 能取到邮件，即配置正确（多账号时确认输出含所有账号，失败账号会出现在 `errors` 字段）。
