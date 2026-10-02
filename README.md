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
| 10 引擎降级链 | 首选引擎 → 付费引擎 → 免费引擎；bing/anysearch/ddg/ddg-lite/searxng/tavily/exa/keenable 共 8 个**免 Key 可用** |
| 时间过滤 | `--time day/week/month/year/12h/3d/2mo/YYYY-MM-DD`，不支持的引擎自动跳过并在 Note 说明 |
| 降级透明 | Note 严格区分"不支持时间过滤被跳过""被引擎画像规则跳过"与"失败（含原因）" |
| 引擎画像 | 按**实测**维护每引擎的质量档位（precision/standard/broad）与 `site:` 支持；`--list-engines` 可查 |
| 结果自检 | 校验 `site:` 是否真生效 + 结果与查询有无词面交集；不通过时输出 `warning`，`--strict` 下换引擎 |
| API Key（可选） | 配 `EXA/TAVILY/KEENABLE/PERPLEXITY/DEEPSEEK_API_KEY` 走账号档；perplexity/deepseek-official 需 Key |

**特点**：零依赖；30s 总预算，且抓 HTML 的引擎（ddg/searxng 等）单独限时 8s；snippet 自动清洗登录/付费墙噪音。

**默认引擎为 exa（有意偏离 DSH 的 bing）**：降级链只在「失败或 0 结果」时才往后走，因此一个
**能返回结果、但结果与查询无关**的引擎永远不会被跳过——这是最危险的形态。实测 bing 搜
「高升控股股份有限公司 首席技术官 CTO」返回的是足球运动员「高升」的百科页与「高升」的汉语词典
释义，而 `engine` 字段照报成功、无 error、无 note；`site:` 定向也实测被它忽略（`site:pedaily.cn`
下 0/3 条来自目标域）。同一检索词下 exa 准确命中真实 CTO。另实测 ddg/searxng 不可达时耗时
39.5s/48.4s，会独自吃光整条链把后面的引擎饿死（报"全网搜索失败"），限时后降到约 10s 并成功降级。

用环境变量 `WEB_SEARCH_ENGINE` 可覆盖默认引擎（国内网络建议 `tavily`）。
**实体级检索（企业名 / 人名 / `site:` 定向）请加 `--strict`**——自检不通过即换引擎，宁可无结果不用错结果。

**触发词**：搜索、搜一下、查一下、检索、search the web

### 📰 rss-skill — RSS 订阅整理与全文搜索

对接自部署 **WeWe RSS（wewe-rss）** 服务，把公众号订阅文章同步到本地 SQLite 全文索引库（FTS5），离线可搜索、浏览、阅读；也可挂任意通用 RSS/Atom 源。零依赖（Python 3 标准库），`/feeds` 接口免 AUTH_CODE。

| 能力 | 脚本 | 说明 |
|---|---|---|
| 订阅源管理 | `feeds.py` | 列出全部订阅源 + 本地入库条数；`--update` 触发源立即更新（服务端异步） |
| 同步 | `sync.py` | 增量同步（按 source+guid 去重），默认全文模式；`--deep` 翻页回溯历史，`--no-fulltext` 快速只同步标题 |
| 全文搜索 | `search.py` | SQLite FTS5 + BM25；中文 bigram 预切分（二字词也能精确命中），带【】高亮片段；支持 `--feed` / `--days` 过滤 |
| 浏览阅读 | `articles.py` | `--recent` 按时间浏览、`--read <id>` 读全文（纯文本/HTML）、`--stats` 库统计 |
| 导出 | `export.py` | JSON / JSONL / Markdown / 纯文本四种格式，可按源/时间过滤、可只导元数据 |

**特点**：中文全文搜索做了 bigram 切分（内置 unicode61 分词器不会切中文）；全文模式下大 limit 响应慢属正常（服务端逐篇抓正文）；FTS5 不可用时自动降级 LIKE。

**触发词**：RSS、订阅、公众号文章、同步文章、全文搜索、rss、wewe-rss、订阅源、最近有什么文章

### 📄 pdf-recognition — 本地 PDF 理解

理解任意 PDF（合同、论文、财报、报告、扫描件），全程本地运行，**无需 OCR 服务器**。

| 能力 | 脚本 | 说明 |
|---|---|---|
| 探测 | `probe.py` | 判断 PDF 类型（文字层/扫描件/混合）、页数、元数据 |
| 文本提取 | `extract_text.py` | 有文字层的 PDF 直接提取（最快路径） |
| 页面渲染 | `render_pages.py` | 扫描件渲染为图片，交给多模态模型读图 |
| 本地 OCR | `ocr_pages.py` | 兜底：RapidOCR 离线识别（pip 库，零服务器） |

**特点**：三级降级链（文字层直取 → 多模态读图 → 本地 OCR），对模型能力自适应；OCR 依赖见 `scripts/requirements.txt`。

**触发词**：理解PDF、读PDF、解析PDF、PDF总结、PDF转文字、扫描件识别、这份PDF讲了什么

### 📐 diagram-skill — 编辑级中文图表

借鉴 [diagram-design](https://github.com/cathrynlavery/diagram-design) 架构的自研中文版：**无渲染代码**，LLM 按规则手写 SVG，脚本只做质检。输出自包含 HTML + 内联 SVG，浏览器直接打开。

| 能力 | 说明 |
|---|---|
| 13 种图表类型 | 结构图 10 种（架构/流程/时序/ER/甘特/状态机/泳道/树状/象限/时间线）+ 数据图 3 种（柱状/折线/饼图环形图，按公式换算坐标） |
| 按需加载 | 主 SKILL.md 只做路由；布局语法在 `references/type-*.md`，选中才读 |
| 中文排版 | 系统字体栈（苹方/雅黑/Noto Sans SC）；中文按 1em/字估算宽度，最小 12px |
| 设计系统 | 语义令牌（paper/ink/accent…）可换肤；焦点色 ≤2、4px 网格、正交圆角连线、标签遮罩 |
| 质量门 | `scripts/self_check.py` 交付前必过：a11y 契约（role/title/desc slug 前缀）、单文件安全、网格纪律 |
| 导出 PNG | `scripts/export_png.py`：`--bare` 纯图 / `--transparent` 透明底 / `--scale` 高清；透明适配规则见 `references/export.md` |

**与 mermaid-skill 的分工**：mermaid 快速出草图；本 skill 出"能放进正式文档/汇报"的精美图。

**触发词**：画图、架构图、流程图、时序图、ER图、甘特图、泳道图、状态机、树状图、象限图、时间线、柱状图、折线图、饼图、数据图表

### 📋 bryanchen-spec — 四阶段规格开发流程

自建 spec coding 流程编排器：**Specify（EARS 需求定义）→ Plan（技术方案）→ Tasks（带验收标准的任务拆解）→ Implement（按规范编码）**。核心信条：没有三重确认，不写一行生产代码；没有验证证据，不声称完成。

| 机制 | 说明 |
|---|---|
| 三重人工确认门 | requirements / plan / tasks 三份文档逐一展示、逐一等你「确认」并落盘确认人+日期，全确认才允许开分支写代码 |
| 版本追溯 | 产物带语义化版本头（v1.0.0 已确认…）；`R-xx`（需求）/`T-xx`（任务）编号永久不复用；追溯链 R→T→commit footer→发版 CHANGELOG |
| 双层 changelog | spec 级 `changelog.md`（需求演进到编号级）+ 项目根 `CHANGELOG.md`（发版汇总，`git log --grep "Spec:"` 零成本聚合） |
| git 规范 | **一版一分支**：版本分支用裸号 `1.4.0`（与 tag `v1.4.0` 差一字母天然区分），feature/fix 从版本分支切、合回版本分支；main 只收用户确认合并的已发布版；一任务一 commit、Conventional Commits + `Spec:`/`Task:`/`Bug:` footer；**版本分支默认永久保留**，**agent 永不自主合 main、永不自主 push**（只问不做） |
| 规范源路由 | 项目根 `.specrc.yml` 按领域声明规范来源（`global` 内置底线 / `file:` 项目自己的规范 / `skill:` 其他规范 skill / `none`），一次探测落盘、领域级整文件替换；流程铁律不受任何规范源豁免 |
| 内置全局规范 | `standards/` 七份：代码（前端 Vue / 后端 Java 分册）、接口、数据库、git 工作流、版本规则 |
| 断点续传 | 说「继续 \<功能名\>」自动定位第一个未确认文档或未完成任务续做 |
| 里程碑发版 | 多需求汇总成大版本：`releases/v1.3.0/` 下 MILESTONE 清单 + SQL/配置按版本聚合为 Flyway 风格升级件，含升级说明/升级操作/回滚。三层版本模型：spec 版本管文档演进、里程碑管发版交付、git tag 管代码快照 |
| 版本台账与归属 | 产品版本规则 `v a.b.c`（a 破坏性 / b 需求迭代 / c 纯修复，升位低位归零，初始 v1.0.0）+ 项目级台账 `specs/_project/version.md`；**每个 spec 启动必问一次挂哪个版本**（agent 不得代选、不得静默挂版），选「新开」则**双建**（`releases/v{号}/` 目录 + 裸号版本分支）；**在途唯一**，有未合 main 的「悬空」版时先报账处置，未获明确选择不建目录不建分支 |
| 存量项目 init | 「spec init」一次跑完：项目体检 + 机制骨架 + 项目画像（profile，供后续 Specify 直接引用），**只读不回填**——明确不把存量代码反推成 specs（无变更驱动的 spec 会立刻腐烂），specs 只为将改动的部分积累 |
| Bug 管理 | 项目级唯一清单 `specs/_project/bugs.md`，`BUG-xx` 编号永久不复用、**状态必绑版本**（新建→已规划→已修复→已验证→已发布）；`Bug: BUG-xx` 写进 commit footer；小 bug 直接修、大 bug 升级为 `fix-xxx` spec 走完整四阶段；冻结时校验 P0/P1 必须达「已验证」 |
| 发版对账 | M4 强制 **Bug 台账三步对账**：`git log <上一tag>..X.Y.Z --grep "Bug:"` **收网**（治「修了没记」）→ 本版「已验证/已修复」**翻账**为「已发布」（治「记了没翻」）→ `git merge-base --is-ancestor <修复commit> X.Y.Z` **反核**（治「翻了没随版」），footer 是账证勾稽的唯一硬锚 |
| 共享面回归纪律 | 改 nginx/网关/路由/DB 共享列/依赖版本/全局配置等共享面时，自检「**还有谁依赖这个路径/列/配置？**」→ 在 plan 建**身份矩阵**（对象 × 身份(方法×调用方×端点) × 变更后预期行为），每个既有身份都要有断言；**commit body 必须同时贴「改好了」+「没改坏」双面实测输出**，只有一面不得提交；M4 要求每个共享面变更在回归载体中有配对断言，无配对不发版 |

**触发词**：新需求、新功能、开始做、开发功能、需求开发、做一下xxx功能、spec流程、继续功能、新建里程碑、纳入里程碑、冻结版本、汇总升级件、发版、初始化spec、spec init、接入spec机制、建基线、记录bug、修复BUG-xx、bug列表、完成清单
**不适用**：明显单点 bug 修复（直接修，但**完成后强制在 `bugs.md` 补登记一行**）、单文件小改动、纯技术问答。

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
    └── search.py       # 多引擎搜索（复刻 DSH free-search 降级链，10 引擎）

rss-skill/
├── SKILL.md            # skill 说明与典型工作流
├── config.example.json # 配置模板（真实配置放 ~/.config/rss-skill/config.json）
└── scripts/
    ├── rss_lib.py      # 共享库：配置/Feed 解析（JSON Feed/RSS/Atom）/SQLite+FTS5/中文 bigram 切分
    ├── feeds.py        # 订阅源列表 / 触发更新
    ├── sync.py         # 增量同步（全文/快速模式，--deep 历史回溯）
    ├── search.py       # 全文搜索（FTS5 BM25 + 命中片段）
    ├── articles.py     # 浏览 / 读全文 / 库统计
    └── export.py       # 导出（JSON/JSONL/Markdown/纯文本）

pdf-recognition/
├── SKILL.md            # skill 说明与三级降级链
└── scripts/
    ├── probe.py          # PDF 探测（类型/页数/元数据）
    ├── extract_text.py   # 文字层直接提取
    ├── render_pages.py   # 页面渲染为图片（多模态读图用）
    ├── ocr_pages.py      # 本地离线 OCR（RapidOCR）
    └── requirements.txt  # OCR 依赖清单

diagram-skill/
├── SKILL.md            # 路由表 + 设计系统摘要 + 通用规则 + 自检清单
├── CHANGELOG.md        # 版本记录
├── assets/
│   └── template.html   # 中文优化模板（系统字体栈 + SVG 骨架）
├── references/
│   ├── style-guide.md  # 设计令牌 + 中文排版规则 + 换肤
│   ├── type-*.md       # 13 种图表类型的布局语法（按需加载，数据图含换算公式）
│   └── export.md       # 导出规则（PNG/纯图/透明底适配）
└── scripts/
    ├── self_check.py   # 交付前自检（a11y 契约/单文件安全/网格纪律，UTF-8 强制）
    ├── export_png.py   # HTML → PNG（puppeteer；失败自动降级 resvg）
    ├── render_svg.js   # 降级渲染：resvg-js 进程内光栅化（无浏览器/沙箱环境）
    └── package.json    # resvg 依赖声明（按需 npm install）

bryanchen-spec/
├── SKILL.md            # 主协议：四阶段 + 三重确认铁律 + .specrc.yml 路由 + 断点续传 + 里程碑/init/bug 概要
├── references/
│   ├── templates.md    # requirements/plan（含共享面身份矩阵）/tasks/changelog/.specrc.yml + MILESTONE/RELEASE-NOTES/UPGRADE/artifacts 模板
│   ├── standards-routing.md  # 规范源路由：声明表语法/探测顺序/裁决规则/完整示例
│   ├── milestone.md    # 里程碑与发版：releases/vX.Y.Z/ 结构、Flyway 风格 SQL 规范、升级件汇总流程
│   ├── init.md         # 存量项目接入：I1~I7 七步（快照/体检/基线/画像/路由/骨架/报告）+ baseline-capture
│   └── bugs.md         # Bug 管理：BUG-xx 编号与字段、状态机（状态绑版本）、修复分级、里程碑联动
└── standards/          # 内置全局规范（.specrc.yml 领域声明为 global 时的默认源）
    ├── README.md       # 规范索引 + 四层裁决规则
    ├── code-style-backend.md   # 后端代码底线（Java/Spring）
    ├── code-style-frontend.md  # 前端代码底线（Vue/Element）
    ├── api-design.md   # RESTful/响应包装/错误码/幂等
    ├── database-design.md      # 命名/公共字段/索引/迁移回滚
    ├── git-workflow.md # 分支模型/commit 格式/tag/合并
    └── versioning.md   # spec 版本头/产品版本 v a.b.c 与版本台账/编号永久制/双层 changelog
```

> 在目标项目运行时会长出（非 skill 包内容）：`specs/{日期}_{功能名}/`（四文档，收尾另有 `completion.md`/`artifacts.md`）、`specs/_project/profile.md`（项目画像）、`specs/_project/version.md`（版本台账）、`specs/_project/bugs.md`（bug 清单）、`.specrc.yml`（规范路由）、`releases/vX.Y.Z/`（里程碑升级件目录）；git 侧还会长出**裸号版本分支** `X.Y.Z`（与 tag `vX.Y.Z` 配对）、`feature/<功能名>`、`fix/...`、`hotfix/...`。

## 安装

将对应 skill 目录复制到本地 skills 目录即可：

```bash
cp -R morning-report ~/.agents/skills/
cp -R email-skill ~/.agents/skills/
cp -R 12306-skill ~/.agents/skills/
cp -R rss-skill ~/.agents/skills/
cp -R web-search ~/.agents/skills/        # 可选：宿主无搜索工具的环境用
cp -R pdf-recognition ~/.agents/skills/   # 需 OCR 时先 pip install -r pdf-recognition/scripts/requirements.txt
cp -R diagram-skill ~/.agents/skills/
cp -R bryanchen-spec ~/.agents/skills/      # 或 ~/.dsh/skills/；项目首次触发会探测并生成 .specrc.yml 规范路由
```

email-skill 首次使用需配置邮箱凭据：

```bash
mkdir -p ~/.config/email-skill
cp ~/.agents/skills/email-skill/config.example.json ~/.config/email-skill/config.json
# 编辑填入 email 和授权码（QQ/163 在网页设置中开启 IMAP/SMTP 时生成）
```

rss-skill 首次使用需配置 wewe-rss 服务地址：

```bash
mkdir -p ~/.config/rss-skill
cp ~/.agents/skills/rss-skill/config.example.json ~/.config/rss-skill/config.json
# 编辑填入 base_url（你的 wewe-rss 服务地址，如 http://127.0.0.1:4000）
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
