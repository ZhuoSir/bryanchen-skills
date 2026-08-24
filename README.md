# bryanchen-skills

个人维护的 Agent Skills 集合（适用于支持 SKILL.md 规范的 AI Agent，如 DeepSeek Harness / Claude Code 等）。

## Skills 列表

### 🌅 morning-report — 每日晨报/晚报生成

生成一份完整的每日晨报或晚报，包含七个板块：

| 板块 | 数据源 | 说明 |
|---|---|---|
| 🌤️ 天气 | Open-Meteo（兜底 wttr.in） | 北京 / 深圳 / 上海 / 杭州 / 通辽 / 崇礼；晨报看**今日**，晚报看**明日**预报 |
| 🌍 国际新闻 | 60s API ×2 → yyxw → Google News RSS（内置降级链） | 当日综合新闻 5–10 条 |
| 🇨🇳 国内新闻 | 同上 | 与国际新闻同源，由模型按内容归类 |
| 🤖 AI 动态 | 量子位 / TechCrunch AI / InfoQ 中文（RSS） | 最近 2 天行业新闻约 5 条 |
| ⚽🏀 体育 | 虎扑移动端（m.hupu.com/nba、/soccer） | 置顶帖 📌 + 最新热帖前 5–10 条 + 当日赛程 |
| 🔥 全网热榜 | 60s API（微博/知乎/抖音/头条） | 四平台热榜各 Top5，含热度值 |

晨报末尾附「今日寄语」（优先采用 60s API 每日一句）；晚报寄语为原创晚安主题，落款均为"爱你的悠悠"。晚报差异：天气改明日、赛程改"今晚有比赛"视角、标题 🌙。

**特点**：

- 零依赖：纯 Python 3 标准库，无需安装任何包
- 免 API Key：全部使用免费 API / RSS / 静态页面，不通过搜索引擎抓新闻
- 自带降级链与重试，易超时的源排在最后
- 铁律：禁止模型凭记忆编造新闻，每条必须附来源链接

**触发词**：晨报、早报、今日新闻简报、morning report、daily briefing

### 📧 email-skill — 邮箱收发与整理

基于 IMAP/SMTP 的个人邮箱管理，零依赖（Python 3 标准库 imaplib/smtplib/email），支持 QQ / 163 / 126 / Gmail / Outlook / iCloud / 新浪 / 阿里 / 139 等常见邮箱（按域名自动推断服务器，可覆盖）。

| 能力 | 脚本 | 说明 |
|---|---|---|
| 查看/搜索 | `list_mail.py` | 列文件夹、最近邮件、仅未读、关键词搜索（服务器不支持中文搜索时自动回退客户端过滤） |
| 阅读 | `read_mail.py` | 按 UID 读全文，HTML 自动转文本，列出附件；PEEK 模式不误标已读 |
| 发送 | `send_mail.py` | 新邮件，支持多人、抄送、正文文件 |
| 回复 | `reply_mail.py` | 自动 `Re:` 前缀、原文引用、In-Reply-To 线程头，支持回复全部 |
| 整理 | `organize_mail.py` | 标已读/未读、星标、移动文件夹、删除（优先移入 Trash）、新建文件夹 |

**安全设计**：发信/回复前须经用户确认；配置含授权码，`config.json` 已被 `.gitignore` 排除；读取用 PEEK 不改变已读状态。

**触发词**：查邮件、发邮件、回复邮件、整理邮件、未读邮件、email、inbox

### 🚄 12306-skill — 火车票余票、票价与时刻查询

零依赖（Python 3 标准库）、免登录免 Key，数据源为 12306 官网网页版公开查询接口。**只查询，不订票**（12306 无官方开放 API，下单必须官方 App/网站手动操作）。

| 能力 | 脚本 | 说明 |
|---|---|---|
| 余票查询 | `tickets.py` | 指定日期/区间查全部车次余票，支持按 G/D/C/K/T/Z 过滤或指定车次 |
| 票价查询 | `price.py` | 某趟车指定区间的各席别票价 |
| 时刻表 | `schedule.py` | 某趟车全程经停站到发时刻、停留时长 |

**特点**：自动管理会话 Cookie；余票端点不定期迁移时按 `c_url` 自动跟随；车站代码表自动缓存；座位余票如实转述（有/数字/无/候补）。

**触发词**：查火车票、查余票、高铁票、还有票吗、车次时刻、经停站、12306

### 🔍 web-search — 自带代码的联网搜索

与纯提示词型搜索 skill 不同：**自带完整搜索脚本**，引擎链与降级逻辑完整复刻 DSH free-search 插件，不依赖宿主环境是否提供搜索工具。

| 能力 | 说明 |
|---|---|
| 10 引擎降级链 | 首选引擎 → 付费引擎 → 免费引擎；bing/anysearch/ddg/ddg-lite/searxng/tavily/exa/keenable 全部**免 Key 可用** |
| 时间过滤 | `--time day/week/month/year/12h/3d/2mo/YYYY-MM-DD`，不支持的引擎自动跳过并在 Note 说明 |
| 降级透明 | 输出 Note 严格区分"首选不支持时间过滤被跳过"与"首选失败（含原因）" |
| API Key（可选） | 配 `EXA/TAVILY/KEENABLE/PERPLEXITY/DEEPSEEK_API_KEY` 走账号档；perplexity/deepseek-official 需 Key |

**特点**：零依赖；30s 总预算防超时累积；snippet 自动清洗登录/付费墙噪音。

**触发词**：搜索、搜一下、查一下、检索、search the web

## 目录结构

```
morning-report/
├── SKILL.md            # skill 说明与执行流程
└── scripts/
    ├── weather.py      # 六城市天气（--tomorrow 明日预报）
    ├── news_api.py     # 综合新闻（免费 API 降级链）
    ├── fetch_rss.py    # AI 行业 RSS
    ├── hupu.py         # 虎扑足篮球热帖 + 赛程
    └── hot_rank.py     # 全网热榜（微博/知乎/抖音/头条）

email-skill/
├── SKILL.md            # skill 说明与典型工作流
├── config.example.json # 配置模板（真实配置放 ~/.config/email-skill/config.json）
└── scripts/
    ├── mail_lib.py     # 共享库：配置加载/IMAP/SMTP/MIME 解析
    ├── list_mail.py    # 列文件夹/邮件列表/搜索
    ├── read_mail.py    # 读邮件全文（PEEK，不标已读）
    ├── send_mail.py    # 发送新邮件
    ├── reply_mail.py   # 回复（引用 + 线程头）
    └── organize_mail.py# 已读/星标/移动/删除/建文件夹

12306-skill/
├── SKILL.md            # skill 说明与查询流程
└── scripts/
    ├── lib12306.py     # 共享库：会话 Cookie/车站代码/端点跟随/行解析
    ├── tickets.py      # 余票查询（日期/区间/类型过滤/指定车次）
    ├── price.py        # 票价查询（车次+区间 → 各席别价格）
    └── schedule.py     # 经停站时刻表

web-search/
├── SKILL.md            # skill 说明与输出格式
└── scripts/
    └── search.py       # 搜索引擎抓取（Bing → DDG Lite 降级链）
```

## 安装

将对应 skill 目录复制到本地 skills 目录即可：

```bash
cp -R morning-report ~/.agents/skills/
cp -R email-skill ~/.agents/skills/
cp -R 12306-skill ~/.agents/skills/
```

email-skill 首次使用需配置邮箱凭据：

```bash
mkdir -p ~/.config/email-skill
cp ~/.agents/skills/email-skill/config.example.json ~/.config/email-skill/config.json
# 编辑填入 email 和授权码（QQ/163 在网页设置中开启 IMAP/SMTP 时生成）
```

之后在会话中说"给我一份今天的晨报"即可触发。

## 使用示例

```
用户：获取一下今天的晨报 / 给我一份晚报
Agent：并行运行 5 个脚本 → 组装输出晨报/晚报（可邮件投递，HTML 超链接格式）
```

输出示例（节选）：

```markdown
# ☀️ 晨报 · 2026-08-23 周日

## 🌤️ 今日天气
- **北京** 🌦️ 25~32°C（当前 31.4°C，降水概率 88%）☔ 午后有雷阵雨
...

---
> 💌 **今日寄语**：人心贵在适度留白……
>
> —— 爱你的悠悠
```
