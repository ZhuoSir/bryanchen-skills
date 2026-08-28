---
name: rss-skill
description: "整理与检索 RSS 订阅文章：对接自部署 WeWe RSS（wewe-rss）服务同步公众号文章全文到本地 SQLite 全文索引（FTS5），支持订阅源列表/触发更新、增量同步（含历史翻页回溯）、本地全文搜索（标题+正文，中文友好、带命中片段）、按源/时间浏览与阅读全文；也可挂任意通用 RSS/Atom 源。零依赖（Python 标准库）。触发词：RSS、订阅、公众号文章、同步文章、整理订阅、搜文章、全文搜索、rss、wewe-rss、werss、订阅源、最近有什么文章。NOT for: 新增/删除公众号订阅（需在 wewe-rss 网页端操作）、无服务地址时的首次连接（需先配置 base_url）。"
---

# RSS 订阅整理 Skill（rss-skill）

把自部署 **WeWe RSS（wewe-rss）** 服务里的订阅文章同步到本地 SQLite 全文索引库，离线可全文搜索、浏览、阅读。零依赖（Python 3 标准库 + SQLite FTS5），数据全部存在本机。

## 首次配置（仅一次）

```bash
mkdir -p ~/.config/rss-skill
cp config.example.json ~/.config/rss-skill/config.json
# 编辑填入 base_url = 用户的 wewe-rss 服务地址，如 http://127.0.0.1:4000
```

- `base_url`：wewe-rss 服务地址（必填，除非只用自定义源）。`/feeds` 路径不需要 AUTH_CODE
- `feeds`：可选，额外的通用 RSS/Atom/JSON Feed 源（与 wewe-rss 无关的公开订阅源）
- `db_path`：可选，默认 `/tmp/rss-skill/articles.db`（索引只是缓存，重启丢失后重新 sync 即可；想持久保存可改到 `~/.local/share/rss-skill/articles.db` 等位置）
- 也可用环境变量覆盖：`RSS_SKILL_BASE_URL` / `RSS_SKILL_CONFIG` / `RSS_SKILL_DB`
- 自检：`python3 scripts/feeds.py --list` 能列出订阅源即配置正确

## When to Use

✅ 用户说：同步一下我的 RSS / 整理订阅文章 / 搜我订阅的文章 / 公众号文章里搜"xx" / 最近有什么新文章 / 列出我的订阅源 / 全文搜索文章

❌ 不适用：新增/删除公众号订阅源（wewe-rss 网页端扫码操作，本 skill 只做读取与本地整理）；抓取非订阅的任意网页

## 脚本一览（均在 scripts/ 下，JSON 输出到 stdout）

### 1. 订阅源管理 feeds.py

```bash
python3 scripts/feeds.py --list                # 列出 wewe-rss 全部订阅源 + 本地已入库条数
python3 scripts/feeds.py --update MP_WXS_123   # 触发指定源立即更新（服务端异步，约 30s）
python3 scripts/feeds.py --update all          # 触发所有源更新（每源间隔 30s+，很慢，慎用）
```

- wewe-rss 服务端本身有定时更新（默认每天 5:35 / 17:35），一般不需要手动 `--update`
- 触发更新后**稍等片刻再 sync**，否则拉到的还是旧数据

### 2. 同步文章 sync.py

```bash
python3 scripts/sync.py                        # 全部订阅源最新一页（全文模式）
python3 scripts/sync.py --feed MP_WXS_123      # 只同步指定源
python3 scripts/sync.py --deep --max-pages 5   # 翻页回溯历史文章（每源最多 5 页）
python3 scripts/sync.py --no-fulltext          # 快速模式：只同步标题/链接（不取全文，快很多）
python3 scripts/sync.py --custom               # 只同步配置文件里的自定义 RSS 源
python3 scripts/sync.py --limit 50             # 每页条数（默认 30；全文模式下大值响应慢）
```

- 默认**全文模式**（`mode=fulltext`，逐篇取正文，响应较慢属正常，脚本已设长超时与重试）
- 按 `(源, guid)` 去重：重复运行是增量同步，不会重复入库；已入库的文章不会被空正文覆盖
- 首次使用建议 `--deep --max-pages 3` 建基础库，之后日常增量用默认即可

### 3. 全文搜索 search.py

```bash
python3 scripts/search.py 世界模型                    # 全文搜索（标题+正文+源名）
python3 scripts/search.py "世界模型 具身智能"          # 多词 = AND
python3 scripts/search.py 大模型 --feed 量子位         # 限定订阅源
python3 scripts/search.py 机器人 --days 30            # 只搜最近 30 天发布的
python3 scripts/search.py 'title:世界模型'             # 只搜标题（FTS5 列语法）
```

- 引擎为 SQLite FTS5（BM25 排序）；中文采用 bigram 预切分（CJK 二字组 + 拉丁整词），二字词（如"肝癌"）也能精确命中；输出带【】高亮标记的命中片段；FTS 不可用时自动降级 LIKE 并在 `engine` 字段体现
- 每条结果带 `id`，**用 `articles.py --read <id>` 读全文**

### 4. 浏览与阅读 articles.py

```bash
python3 scripts/articles.py --recent                  # 最近文章（默认 20 条，按发布时间倒序）
python3 scripts/articles.py --recent --feed 量子位 --days 7
python3 scripts/articles.py --read 123                # 阅读全文（纯文本）
python3 scripts/articles.py --read 123 --html         # 原始 HTML
python3 scripts/articles.py --stats                   # 库统计：总条数 / 各源分布 / 时间范围
```

- `--recent` 输出里 `has_fulltext=false` 的条目表示是 `--no-fulltext` 同步进来的，只有标题/摘要

### 5. 导出 export.py

```bash
python3 scripts/export.py                        # 全部文章 → JSON（默认 /tmp/rss-skill/export_<时间>.json）
python3 scripts/export.py --format markdown      # Markdown（含全文，按订阅源分组）
python3 scripts/export.py --format text          # 纯文本
python3 scripts/export.py --format jsonl         # JSON Lines（每行一条，适合导入其他系统）
python3 scripts/export.py --feed 量子位 --days 7  # 按源/时间过滤
python3 scripts/export.py --no-content           # 只导出元数据（标题/链接等，文件很小）
python3 scripts/export.py --out ~/Desktop/rss.json  # 指定输出路径
```

- JSON 结构：`{exported_at, count, with_content, articles: [...]}`，单条含 `title/url/published/feed_name/content_text/content_html` 等字段

## 典型工作流

**回答"最近订阅有什么新文章"**：`sync.py`（增量同步）→ `articles.py --recent --days 2` → 用中文按主题分组汇总，附标题/公众号名/链接

**主题调研（如"我订阅的文章里关于世界模型的内容"）**：`sync.py`（保证库新）→ `search.py 世界模型` → 对高相关结果逐个 `articles.py --read <id>` → 综合多篇文章写报告，**标注出处（公众号名 + 标题 + 链接）**

**定期整理**：用户要求"每天同步"时，建议配合 cron 任务：先 `sync.py` 再汇总 `--recent --days 1`

## 铁律

- 搜索/阅读的是**本地库**：发现结果明显过时（`--stats` 里 latest 很旧）时，先跑 `sync.py` 再回答，不要拿旧库硬答
- 文章标题、正文、出处必须来自库中真实记录，**禁止编造**；正文为公众号原文，转述时注明来源公众号
- sync 失败（连不上服务）时如实报错，提示检查 base_url 与 wewe-rss 服务状态，不要假装已同步
- `--update all` 会逐源触发且服务端每源强制等待 30s，只在用户明确要求"立即刷新全部"时使用

## 技术备忘（排查用）

- wewe-rss 接口：`GET /feeds`（源列表，JSON）；`GET /feeds/{all|<id>}.json?limit&page&mode=fulltext&update=true`，返回 JSON Feed 1.0
- 全文模式逐篇抓正文，大 limit 会慢且占服务端内存——日常同步保持默认 limit=30
- 正文入库前会清洗：提取 `js_content` 容器（JS 渲染的空容器页面退化为 body 兜底）、去 script/style/base64——原始整页 3~4MB/篇，清洗后约 30KB/篇
- 正文同时存 `content_html` 与纯文本 `content_text`，FTS 索引建在纯文本上
- 库文件默认在 `/tmp/rss-skill/articles.db`，删库后重新 sync 即可重建
- wewe-rss 有每分钟请求限流（默认 60/min），`--deep` 翻页过快可能触发 429，脚本重试失败后减小页数重跑即可
