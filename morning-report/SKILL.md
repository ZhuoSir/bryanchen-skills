---
name: morning-report
description: "生成每日晨报/晚报：国内主要城市天气预报（北京/深圳/上海/杭州/通辽/崇礼，晨报看今日、晚报看明日）、当日国际/国内综合新闻（5-10条）、AI 行业动态（量子位/TechCrunch/InfoQ RSS）、虎扑足球与篮球新闻及赛程、全网热榜聚合（微博/知乎/抖音/头条）。触发词：晨报、早报、晚报、今日新闻简报、晚间简报、morning report、evening report、daily briefing。NOT for: 深度专题调研、历史新闻检索、实时比分查询。"
---

# 晨报/晚报 Skill（morning-report）

零依赖（Python 3 标准库 + 免费新闻 API/RSS），不使用任何 API Key，**不通过搜索引擎抓新闻**。

## When to Use

✅ 用户说：晨报 / 早报 / 今日新闻 / 每日简报 / morning report / "给我一份今天的晨报"
✅ 用户说：晚报 / 晚间简报 / evening report / "给我一份今天的晚报"（走下方「晚报模式」）

❌ 不适用：历史日期的新闻回顾、单一事件的深度调研、实时赛事比分

## 执行流程

所有脚本位于本 skill 目录的 `scripts/` 下，用 bash 运行。**第 1、2、3、4、5 步互相独立，应在同一个消息里并行发起。**

### 第 1 步：国内主要城市天气

```bash
python3 scripts/weather.py
```

- 主源 Open-Meteo（一次请求返回全部城市，~1s），兜底 wttr.in（仅当前天气，无当日高低温）
- 城市固定为：北京、深圳、上海、杭州、通辽、崇礼（改城市改脚本顶部 `CITIES`）
- 输出每城 `now`（当前温度/体感/湿度/风速）与 `today`（高低温/天气/降水概率），已带 emoji
- **天气板块 = 每城一行（带天气图标）+ 下面 5 条天气新闻**：
  ```bash
  python3 scripts/weather_news.py --limit 5 --cities "北京,深圳,上海,杭州,通辽,崇礼"
  ```
  - 源：中国天气网新闻频道（`news.weather.com.cn`，免 Key）；排序＝命中城市 → 预警 → 其余
  - 这些条目也**过 `sent_log.py filter`**，并在内容 JSON 里作为 `news` 块、`nav` 填 `天气`（与天气表同属一个 Tab）

### 第 2 步：综合新闻（国际 + 国内）

```bash
python3 scripts/news_api.py --max 15
```

- 免费新闻 API，免 Key。脚本内置降级链（按实测速度排序，**经常超时的放最后**）：
  1. `60s API` 镜像 ×2（每天60秒读懂世界 JSON，~1-2s）
  2. `yyxw.com` 每日早报页（HTML，~0.5s）
  3. `Google News 中文 RSS`（国内网络经常超时，仅作最后兜底）
- 输出 `items` 为国际/国内混合条目，**由你按内容归类到"国际新闻"和"国内新闻"两个板块**
- 条目链接为百度搜索链接（源本身无独立文章链接）；digest 原文在顶层 `source_link`，可在晨报末尾注明
- 从中选 **5–10 条，保底 5 条**（国际/国内尽量兼顾）；注意 `warning` 字段（数据日期非今天时需在晨报中注明）
- **需要原文链接 / 去重后条数不够 / news_api 全挂**（见 8.6）时，追加（晨报同样适用） `python3 scripts/news_web.py --limit 20` 抓频道页头条：
  中华网、人民网、光明网、中新网，条目带真实原文链接与 `outlet`（原媒体名）

### 第 3 步：AI 行业新闻

```bash
python3 scripts/fetch_rss.py --days 2 --per-source 3
```

- 源：量子位、TechCrunch AI、InfoQ 中文（RSS，按发布时间过滤最近 N 天）
- 从合并结果中选 **约 5 条**，中英文源都要兼顾；某源 `ok: false` 时降低该源配额即可，不必重试超过 1 次

### 第 4 步：体育新闻 + 当日赛程（虎扑）

```bash
python3 scripts/hupu.py --per-section 5
```

- 新闻源：虎扑移动端频道页 `m.hupu.com/nba`（篮球）、`m.hupu.com/soccer`（足球），静态 HTML 免 Key
- 赛程源：`m.hupu.com/nba/schedule`、`m.hupu.com/soccer/schedule`（页面内嵌 JSON，按当天日期过滤）
- 输出 `sections.basketball` / `sections.football`（新闻）：**置顶帖全量保留在前并标注 `"pinned": true`，普通帖取前 5–10 条**（`--per-section` 控制）
- 输出 `matches.basketball` / `matches.football`（当日比赛）：每条含时间、赛事、主客队、比分、状态（未开始/已结束）；**空列表表示今日无比赛，晨报中如实写"今日无 NBA 比赛"等，不要省略**
- 新闻页**不含发布时间**，按最新活跃排序；在晨报体育板块注明"虎扑实时热帖"，置顶条目用 📌 标出

### 第 5 步：全网热榜聚合

```bash
python3 scripts/hot_rank.py --top 5
```

- 源：60s API 镜像（与 news_api.py 同源、同一降级链），聚合**微博热搜 / 知乎热榜 / 抖音热点 / 头条热榜**，每榜取前 5 条
- 输出 `boards.<key>.items`（`title`/`link`/`hot` 热度值）；单榜失败 `ok: false` 不阻塞，直接从模板省略该榜
- 注意：B 站端点（/v2/bili）上游长期故障，**不要收录 B 站**
- 热榜条目**不需要写摘要**，直接列标题 + 链接 + 热度即可（标题本身就是梗概）

### 第 5.5 步（推荐）：一条命令装配报告 `build_report.py`

前面 1–5 步的 8 个取数脚本可以并行跑完再手工拼 JSON —— 现在有了装配器，**一次调用直接产出内容 JSON**：

```bash
# 晨报（不传 --dedup）
python3 scripts/build_report.py --mode morning --out /tmp/morning_report.json --web 20

# 晚报（传 --dedup，自动排除当日晨报已发内容）
python3 scripts/build_report.py --mode evening --out /tmp/evening_report.json --web 20 --dedup
```

默认配额**已经放开**（要更多就调参数）：

| 参数 | 默认 | 含义 |
|---|---|---|
| `--news` | 8 | 国际/国内各最多几条 |
| `--ai` | 9 | AI 动态最多几条 |
| `--finance` | 12 | 财经要闻最多几条 |
| `--weather-news` | 8 | 天气新闻最多几条 |
| `--sports` | 6 | 足球/篮球热帖各最多几条 |
| `--hot` | 10 | 每个热榜平台最多几条 |
| `--sectors` | 8 | 领涨/领跌各几个板块 |
| `--web` | 0 | news_web 频道页补充条数（建议 20，拿原文链接做备选） |

- 脚本并行跑 8 个源（约 10 秒），**自动填好**：天气行+图标、天气新闻、国际/国内、大盘表、
  财经要闻、AI、体育赛程与热帖、热榜，以及每块的 `nav`（导航自动生成）
- **模型只需补 `summary`**（每条一句话中文摘要，英文标题翻译成中文）
- `--dedup` 会直接调用 `sent_log.py filter`（晚报必开）
- `--raw-dir DIR` 把各源原始输出落盘，便于排查

### 第 6 步：组装输出

阅读各脚本 JSON，为每条新闻写**一句话中文摘要**（英文标题需翻译），按模板输出：

```markdown
# ☀️ 晨报 · <YYYY-MM-DD 周X>

## 🌤️ 今日天气
- **北京** ⛅ 25~32°C（当前 30°C，体感 35°C，湿度 60%）
- ……逐城一行，格式：<emoji> 最低~最高°C（当前 xx°C，降水概率 xx%）；有雨/雷暴时加 ☔ 提醒带伞

## 🌍 国际新闻
1. **标题** — 一句话摘要 [来源](url)

## 🇨🇳 国内新闻
（同上）

## 🤖 AI 动态
（同上，标注来源媒体名）

## ⚽ 足球
**今日赛程**（来自 matches.football，无比赛则写"今日无焦点赛事"）
- 19:35 中超第24轮 上海海港 vs 青岛海牛（未开始）/ 国际米兰 4-1 蒙扎（已结束）
**热帖**（虎扑实时热帖，置顶用 📌）
1. **标题** — 一句话摘要 [来源](url)

## 🏀 篮球
**今日赛程**（同上；NBA 休赛期为"今日无 NBA 比赛"）
**热帖**
1. **标题** — 一句话摘要 [来源](url)

## 🔥 全网热榜
**微博热搜** 1. [标题](link)（热度 114万）
**知乎热榜** 1. [标题](link)（1158 万热度）
**抖音热点** / **头条热榜**（同上；某榜失败则整榜省略）

---
> 💌 **今日寄语**：<一句温暖的激励话语；若 news_api.py 输出了 tip 字段（60s API 每日一句）优先采用，否则自己写一句原创的>
>
> —— 爱你的悠悠
```

### 第 7 步（可选）：邮件投递（固定 H5 模板 · 样式唯一）

用户要求"把晨报发到邮箱"时，用 `email-skill` 发送。**必须走固定模板渲染，禁止再用
`--markdown-file` 直接投递 Markdown** —— 样式由 `templates/email.html` + `scripts/render_email.py`
唯一决定，模型只填内容，因此每次发送的排版/配色/字号完全一致，换模型也不会跑版。

**7.1 写内容 JSON**（结构见 `scripts/render_email.py` 顶部注释）：

```json
{
  "mode": "morning", "date": "2025-09-05", "weekday": "周五",
  "quote": "今日寄语……",
  "blocks": [
    {"type": "weather", "label": "今日天气", "en": "WEATHER",
     "rows": [{"city": "北京", "cond": "晴", "text": "16~28°", "note": "现在 24° · 体感 25°", "alert": "建议带伞"}]},
    {"type": "news", "label": "国际新闻", "en": "WORLD",
     "items": [{"title": "…", "summary": "…", "url": "https://…", "source": "量子位", "pinned": true}]},
    {"type": "schedule", "label": "足球", "en": "FOOTBALL", "note": "虎扑实时热帖",
     "schedule": [{"time": "19:35", "text": "中超 · 上海海港 vs 青岛海牛", "state": "未开始"}],
     "items": [{"title": "…", "summary": "…", "url": "https://…"}]},
    {"type": "hot", "label": "全网热榜", "en": "TRENDING",
     "boards": [{"board": "微博热搜", "en": "WEIBO", "items": [{"title": "…", "url": "https://…", "hot": "114万"}]}]}
  ]
}
```

- 板块顺序即输出顺序：天气在最上、热榜在最后（与第 6 步一致）
- `en` 可省略，会自动按中文名匹配（天气/国际/国内/AI/足球/篮球/热榜）
- ⚠️ **不要写 emoji**：图标由模板内置 Tabler 线性图标承担，内容里的 emoji 会被自动剥离
- 某板块失败就整块不写进 JSON，模板不会留空壳

**7.2 渲染固定 HTML**：

```bash
python3 scripts/render_email.py --data /tmp/report.json --out /tmp/report.html
```

- 晨报 = 浅色底，强调色按**北京（天气板块第一行）的天气**自动选：
  晴 #F4511E 橘红 / 多云 #D97706 琥珀 / 阴 #8A8A8E 白灰 / 雨 #2563EB 靛蓝 /
  雷 #7C3AED 紫 / 雪 #0891B2 冰青 / 雾霾 #94A3B8 灰蓝
- 晚报 = 恒定**暗黑底**（`mode: "evening"`），同族强调色自动调亮
- 临时改色：`--accent "#F4511E"`；图标内嵌方式：`--img-mode file`（默认，交 send_mail 转 CID）

**7.3 发送**（用 `--html-file`）：

```bash
python3 <email-skill>/scripts/send_mail.py --to <收件人> \
  --subject "晨报 · <YYYY-MM-DD> 周X" --html-file /tmp/report.html
```

- send_mail.py 会自动把 HTML 里的本地图标转成 **CID 内嵌**（multipart/related），
  Gmail / QQ / 163 都能正常显示，不依赖外链图床
- 主题与 render 输出的 `subject` 保持一致（`晨报 · 2025-09-05 周五`），补跑任务的幂等检查靠它
- 发送前向用户确认收件人；发送后清理临时 json/html

**7.4 自包含样张**：`samples/morning.html` / `samples/evening.html`（图标已转 base64，可直接双击打开）
用来核对固定样式是否跑版；`samples/*.json` 是配套的内容 JSON 示例（照它填即可）。样张不参与发送。

**7.5 图标资源**：`assets/icons/png/{light,dark}/*.png`（Tabler Icons，MIT，可商用）。
缺失或想换图标时重建：`python3 scripts/build_icons.py`（需联网 + cairosvg），
图标名与配色表在 `scripts/build_icons.py` 顶部。

**降级**：若模板渲染失败，先在晨报/晚报正文里说明，再退回 Markdown 投递，不要静默改变样式。

**7.6 布局规范（导航式，v2）**：固定结构为 **顶部天气 → 导航条 → 内容板块**。

- **导航条由内容块的 `nav` 字段自动生成**：给块加 `"nav": "财经新闻"`，导航就多一个入口；
  同名 `nav` 的多个块（如大盘 + 财经要闻）归为**同一入口**，首块自动成为锚点，点击 `#nav-N` 直达
- **新增模块不用改模板**：新板块给一个新的 `nav` 名即可（导航项少于 2 个时不显示）
- ⚠️ 关键词分流（国际/国内）不完美：出现明显错位时（如外国政要进了国内），
  发送前**手工把条目挪到正确板块**（装配器只做初筛）
- **页头两栏并列**：左=刊名（MORNING/EVENING REPORT + 晨报/晚报 + 日期），右=**寄语 + 落款**（右对齐）
- 页头下方依次是 **导航 → 内容**；寄语不再单独占一行、也不在底部重复
  - 天气是导航第一项 + 内容第一个板块（邮件无法切换，所以邮件版天气直接展示在导航下方；H5 版可切换）
  - H5 在窄屏（< 640px）自动把页头两栏改为上下堆叠
- `quote` 类型的块（如去重说明）仍留在正文末尾，不参与导航；`data.quote`（每日寄语）由模板放进页头右侧
- 标准顺序与 `nav` 取值：

| 顺序 | 块 | `nav` |
|---|---|---|
| 1 | 天气（`weather`）+ 天气新闻（`news`） | 两块都填 `天气`（同属第一个 Tab） |
| 2 | 国际新闻（`news`） | `国际新闻` |
| 3 | 国内新闻（`news`） | `国内新闻` |
| 4 | A股大盘（`market`，half）+ 龙虎榜（`lhb`，half）+ 财经要闻（`news`） | `财经新闻` |
| 5 | AI 动态（`news`） | `AI 动态` |
| 6 | 足球 / 篮球 / 其他体育（`schedule` ×N） | `体育新闻`（同一个 nav 名） |
| 7 | 全网热榜（`hot`） | `热榜` |

- **早晚两套风格**（同一模板、同一数据，只换 mode）：
  - `mode: "morning"` → 浅色底（白卡 + `#f6f6f5` 页面底），强调色按北京天气（晴橘红 / 多云琥珀 / 阴白灰 / 雨靛蓝 / 雷紫 / 雪冰青 / 雾霾灰蓝）
  - `mode: "evening"` → 暗黑底（`#141417` 卡），同族强调色自动调亮；天气板块写「明日天气」
- 版面宽度：**邮件 `max-width:900px`、H5 `max-width:960px`**（`width:100%`，窄屏自动收窄）
- **H5 必须预留滚动条宽度**：`html{scrollbar-gutter:stable;overflow-y:auto}` + `body{overflow-x:hidden}` ——
  否则切到内容更高的板块（财经/体育）时竖向滚动条出现，整页会被挤左
- **导航条满宽**：邮件用等分 `<table>`（7 项均分整行）；H5 用 `flex:1 0 auto` 等分撑满，
  空间不足时**横向可滑动**（`overflow-x:auto` + `scroll-snap` + 细滚动条）
- **天气表每行带天气图标**：图标与「天气情况」**同一列**，放在文字前面
  （按该城 `cond` 选 `w-<天气族>.png`，图标本身按天气着色）
- **左右两栏（half 布局）**：内容 JSON 里给块加 `"half": true`，**相邻两个 half 块自动并排各占 50%**
  - 财经面板就是这种：左＝`A股大盘`（指数 + 领涨领跌 + 成交额），右＝`龙虎榜`（净买入额排序前 8）
  - 邮件用 `table-layout:fixed` 锁死 50/50；H5 用 `.duo` grid，窄屏自动堆叠
- **热榜每平台保留 5 条**（`--hot 5`，默认值）

**7.65 栏目点缀色（避免整封黑白）**：主色（页头粗线/kicker/热榜热度值）由**天气**决定，
阴天会偏灰；因此每个栏目另有**固定点缀色**，任何天气下都有颜色：

| 栏目 | 点缀色（浅色版 / 暗黑版） | 用在 |
|---|---|---|
| 天气 | `#0E7C86` / `#4DD0E1` 青 | 导航圆点、图标、天气现象文字（晴=琥珀、雨=蓝、雷=紫、雪=青） |
| 国际新闻 | `#3B5BDB` / `#8FA2FF` 靛蓝 | 同上 |
| 国内新闻 | `#C2255C` / `#FF7AA2` 洋红 | 同上 |
| 财经新闻 | `#B7791F` / `#FFC13B` 琥珀 | 同上（大盘涨跌另用红涨绿跌） |
| AI 动态 | `#7048E8` / `#B197FC` 紫 | 同上 |
| 体育新闻 | `#0E8A4F` / `#4ADE80` 绿 | 同上 |
| 热榜 | `#E8590C` / `#FF9F45` 橙 | 同上（前三名名次也用它） |

- 彩色图标由 `build_icons.py` 生成（`cat-<栏目>-<图标>.png`）；改色改 `CATEGORY_ICONS` 后重跑该脚本
- 邮件与 H5 用同一套色表（`render_email.py` 的 `CAT_COLORS` / `render_h5.py` 的 `CAT_COLORS`），改色要**两处一起改**

**7.68 邮件 vs H5 的分工（重要）**

| | 邮件正文 | H5 页面 |
|---|---|---|
| 结构 | **纯竖版单栏**（无导航、无左右两栏） | 导航 Tab（真切换）+ 财经左右两栏 |
| 原因 | ① 163/QQ/Gmail 等客户端**拦截页内锚点**，导航点了没反应 ② 两栏表格在窄屏会被不可断行内容撑宽，手机上横向拉扯 | 浏览器里 JS/CSS 都可用，能真正切换与自适应 |

- 邮件里 `half: true` 的块会被**忽略并全宽堆叠**（渲染器不再配对两栏）
- **移动端适配三原则**（踩过的坑，别重犯）：
  1. 不要用 `&nbsp;&nbsp;` 连接一排 chips/标签 —— 整行变成不可断行，窄屏直接溢出（实测把 500px 视口撑到 814px）
  2. 容器不要写 `width:100%` + 左右 padding（无 border-box 时会溢出 2×padding）；用 `max-width` 即可
  3. 窄屏微调用 `@media only screen and (max-width:640px)` + `!important` 覆盖内联样式；
     但**不要**把表格单元格改成 `display:block`（天气行会被拆成三行）
- 自检方法：把 `@media` 视口探针脚本注入渲染结果，检查 `document.documentElement.scrollWidth == window.innerWidth`

**7.7 可切换的 H5 版（`render_h5.py`）**：邮件客户端禁 JS，正文做不到「点导航切内容」；
需要真 Tab 时用同一份内容 JSON 另渲染一个 H5：

```bash
python3 scripts/render_h5.py --data /tmp/report.json --out /tmp/report.html   # 默认 img-mode=data，单文件自包含
```

- 导航 = 可点击 Tab（`天气/国际新闻/国内新闻/财经新闻/AI 动态/体育新闻/热榜`，同样由 `nav` 字段派生），
  点击只显示对应面板；支持 `#tab-3` 直达、←/→ 键切换、导航吸顶、手机自适应
- 与邮件共用配色（morning 浅色 / evening 暗黑）、图标、红涨绿跌规则
- 交付方式（二选一，按用户偏好）：① 邮件顶部放入口链接（需本机静态服务常驻）
  ② 作为邮件附件（需 send_mail.py 支持附件）③ 邮件仍为完整堆叠版，H5 单独发/存本地

### 第 8 步：晨晚去重（晚报不得重复晨报内容）

同一天里晨报与晚报同源（60s 新闻 API / RSS / 虎扑 / 热榜），候选几乎一样。
**铁律：当日晨报已发过的条目，晚报一律不再发，必须换成别的。**

台账工具 `scripts/sent_log.py`，状态落在 `data/sent/YYYY-MM-DD.json`（自动清理 3 天前）。

**8.1 晨报发送成功后登记**（补跑路径也要执行；幂等，重复跑不会重复记）：

```bash
python3 scripts/sent_log.py record --data /tmp/morning_report.json --mode morning
```

**8.2 晚报组装前先过滤**。关键：晚报要抓**更大的候选池**，才有得换：

> ⚠️ **踩过的坑（已修）**：只「过滤掉」不「补位」= 晚报几乎空掉。
> 装配器 `build_report.py` 现在的做法是 **先过滤候选池、再取目标条数**，并按 **2–4 倍**抓取
> （天气新闻 3×、财经要闻 3×、热榜 4×、RSS 每源 8 条、虎扑 3×），去重后自动由余量补齐。
> 实测：晨报 77 条入账后，晚报仍能出 **85 条**（去重跳过 77 条，全部补位成功）。
> 手工拼候选池时也必须**每块多写 3–5 条**，否则去重后会出现空板块。

```bash
python3 scripts/news_api.py --max 15      # 拿全量，不要只取 5 条
python3 scripts/fetch_rss.py --days 2 --per-source 5
python3 scripts/hupu.py --per-section 8
python3 scripts/hot_rank.py --top 10      # 热榜多取，晚报用没发过的那几条
```

把候选按内容 JSON 结构写宽（每块多写几条）到 `/tmp/evening_candidates.json`，然后：

```bash
python3 scripts/sent_log.py filter --data /tmp/evening_candidates.json --out /tmp/evening_ok.json
```

- 输出 `removed_items` = 晨报已发过、必须换掉的条目；`kept` = 可直接用的条数
- **按 `removed_by_block` 补齐**：用候选池里剩下的条目填空缺，直到各板块条数达标
- 池子不够时**宁少勿重**（该板块条目数减少即可）；确需补量可 `web_search` 1–2 条并在邮件里注明；
  **绝不允许**把晨报发过的内容再发一遍

**8.3 晚报发送成功后同样登记**：`record --data /tmp/evening_report.json --mode evening`

**8.4 不做去重的部分**：

- **天气**：晚报看「明日」，与晨报天然不同，不去重
- **赛程**：晚报只列**今晚未开始**的场次（晨报列全天），靠内容口径区分，不靠去重

**匹配口径**：标题归一化（去空白与标点、转小写）**或 URL 完全一致**即判为重复 ——
所以只改写标题没用，URL 会兜住；同一封邮件内部重复的条目也会被拦掉。

**没发晨报的日子**：台账为空，`filter` 不会剔任何东西，晚报正常按全天内容发。

**8.5 漏登记的补救（补录）**：若晨报是在台账机制上线前发的、或忘了 `record`，可从**收件箱里那封晨报**反解补录：
`read_mail.py --uid <UID>` 拿到正文（`body_format: plain`），正文里链接是 `标题（url）` 格式，
用正则 `([^（）\n]{4,90}?)（(https?://[^）]+)）` 抽出 title/url，写成一个 `{"blocks":[{"type":"news","items":[...]}]}`
再 `sent_log.py record --data that.json --mode morning` 即可（`record` 幂等，重复补录不会重复计）。
实测：补录当天晨报 + 晚报两封共 89 条，晚报候选 93 条过滤后剔除 40 条。

**8.6 池子被榨干时的补充源（`news_web.py`）**：同日两封都已发过时，`news_api.py` 的池子可能只剩 1–2 条。
此时用固定脚本抓**新闻频道页当日头条**（拿到的是**原文链接**，不是百度搜索链接）：

```bash
python3 scripts/news_web.py --sources china-intl,china-dom --limit 20   # 默认：中华网国际+国内
python3 scripts/news_web.py --sources all --limit 30                    # 五个站点一起（更多选择）
python3 scripts/news_web.py --list                                      # 可用站点
```

- 内置站点：`china-intl` 中华网·国际、`china-dom` 中华网·国内、`people` 人民网、
  `gmw` 光明网、`chinanews` 中新网；单站点失败自动用其余站点补齐
- 输出条目带 `title/url/site/outlet/time`，**`outlet` 是页面标注的原媒体**（新华社/央视新闻/人民网…），
  填进内容 JSON 的 `source` 字段即可显示在邮件里
- ⚠️ 抓来的条目**同样要过 `sent_log.py filter`**（写进候选池一起过滤），避免与晨报重复
- 用完后在邮件末尾用 `{"type":"quote"}` 块注明「部分条目来自频道页补充，来源已逐条标注」
- 仅当 `news_web.py` 也失败时，才退回 `web_fetch` 工具手工抓页（第 7 步降级）

### 第 9 步：财经板块（A股大盘 + 财经要闻）

晨报/晚报都建议带一个财经板块，数据由 `scripts/finance.py` 提供（零依赖、免 Key，约 1s）：

```bash
python3 scripts/finance.py --news-limit 8 --sectors 5   # 行情 + 要闻（默认）
python3 scripts/finance.py --no-news                    # 只要行情
python3 scripts/finance.py --breadth                    # 附加涨跌家数（约 56 次请求、~10s，非必须）
```

- **行情**：主源东方财富 `push2.eastmoney.com`（JSON）；兜底新浪 `hq.sinajs.cn`（GBK，需 Referer）
  - 指数：上证指数 / 深证成指 / 创业板指 / 科创50 / 北证50 / 沪深300，含点位、涨跌额、涨跌幅、成交额
  - 另含 `turnover_total`（两市成交额，元）、`sectors_up` / `sectors_down`（行业板块涨跌幅榜）
- **龙虎榜**：`--lhb N`（默认 8）取东方财富龙虎榜（`RPT_DAILYBILLBOARD_DETAILSNEW`，按净买入额降序），
  字段含代码/名称/涨跌幅/净买入额/上榜原因；**找不到当日自动往前找最多 7 天**，全失败退回「涨幅榜」
- **要闻**：主源新浪财经滚动（`pageid=153`，`lid=2516` 财经要闻 + `2518` 国际市场）
  → 兜底同花顺 `news.10jqka.com.cn/today_list/`（GBK）→ 兜底证券时报首页
  - 条目含 `title/url/media/time`，**URL 是原文链接**，`media` 是媒体名（环球市场播报/证券时报…）
- **时点口径**：晨报（09:00）A股还没开盘 → 文案写「**昨日收盘**」；晚报（17:30）写「**今日收盘**」
- **大盘用 `market` 板块承载**（模板内置，红涨绿跌自动上色）：

```json
{"type": "market", "label": "A股大盘", "en": "MARKET",
 "indices": [{"name": "上证指数", "point": 3891.60, "chg": 27.32, "pct": 0.71}],
 "footnote": "两市成交额 18,391 亿元 · 数据 2026-09-16 19:08",
 "up": [{"name": "运动服装", "pct": 7.34}], "down": [{"name": "商用载客车", "pct": -2.62}]}
```

- 财经要闻放 `news` 板块，`source` 填脚本给的 `media`
- ⚠️ 财经要闻条目**同样要过 `sent_log.py filter`**（写进候选池一起过滤），否则晚报会重复晨报的财经条目
- ⚠️ 涉及点位/涨跌幅的数字**必须原样引用脚本输出**，不要自己换算或估算

## 晚报模式（evening report）

用户说"晚报/晚间简报/evening report"时，**执行流程与晨报相同**，只有以下三处差异：

### 差异 1：天气改为"明日预报"

```bash
python3 scripts/weather.py --tomorrow
```

- 输出中每日天气字段为 `tomorrow`（date 为明天日期），`now` 仍是当前实况
- 模板板块标题改为 `## 🌤️ 明日天气`，突出"明天出门"视角（如：明早有雨 → 提醒睡前备好伞）

### 差异 2：标题与赛程视角

- 大标题：`# 🌙 晚报 · <YYYY-MM-DD 周X>`（日期仍为**今天**，新闻都是当天发生的）
- 体育赛程：今天已结束的比赛报比分（回顾视角），未开始的晚间场次重点提示"今晚有比赛"

### 差异 3：寄语改为晚间休息主题

- 晨报寄语用 60s API 的 `tip` 每日一句；**晚报寄语由你原创一句温暖的"晚间休息"主题话语**（道晚安、放下疲惫、好好休息一类，不要用 tip 字段）
- 落款不变：`—— 爱你的悠悠`
- 邮件投递：内容 JSON 里写 `"mode": "evening"`（模板自动切成暗黑底），主题 `晚报 · <YYYY-MM-DD 周X>`

### 差异 4：内容必须与当日晨报去重

**晚报的新闻/AI/体育热帖/热榜条目，凡是当天晨报发过的，一律换掉** —— 见「第 8 步：晨晚去重」。
晚报抓候选池时要加大配额（`news_api --max 15`、`fetch_rss --per-source 5`、`hupu --per-section 8`、
`hot_rank --top 10`），过滤后从剩下的条目里挑。

### 晚报模板差异速查

```markdown
# 🌙 晚报 · <YYYY-MM-DD 周X>

## 🌤️ 明日天气
- **北京** ⛅ 24~31°C（明天：xx，降水概率 xx%）……有雨加 ☔ 提醒

（🌍 国际 / 🇨🇳 国内 / 🤖 AI / ⚽ 足球 / 🏀 篮球 / 🔥 全网热榜 板块与晨报完全一致）

---
> 💌 **晚安寄语**：<原创的晚间休息激励话语>
>
> —— 爱你的悠悠
```

### 第 10 步：特别关注（词条全网检索）

**观察名单**：`data/watchlist.json` → `{"keywords": ["电子城高科", "知鱼智联"]}`。
改名单就改这个文件，晨报/晚报自动带上，不用改任何任务。

**机制**（装配器自动做）：
- `build_report.py` 自动读名单（也可用 `--watch "A,B"` 覆盖），每个词条跑 `watch_news.py`
- `watch_news.py`：Google News RSS 搜索 → Bing News RSS 降级；**标题必须含词条片段**
  （全称 → 去公司后缀 → 前 2 字），清掉蹭词垃圾；按发布时间排序，只保留近 3 天（`--watch-days`）
- 板块名「特别关注 · <词条>」（`nav` = `特别关注`，玫红星标 Tab），紧跟天气板块之后；
  条目来源字段带 `来源 · MM-DD HH:MM`（一眼看出新不新）
- 同样进去重台账，晚报不会重发晨报已发的关注条目
- **没搜到就是 0 条**（板块整块省略），绝不允许编造

**临时单查**（不改名单）：

```bash
python3 scripts/watch_news.py --kw "某公司" --limit 10 --days 7          # 临时查一家
python3 scripts/watch_news.py --kw "某公司" --no-strict                  # 词条很短/易歧义时关相关性过滤
python3 scripts/watch_news.py --list                                     # 看当前名单
```

**可选增强**：若运行环境有企业信息类工具（如企查查 MCP），可顺带补一段该公司工商/舆情摘要，
以 `source: "企查查"` 写入同一板块 items —— 只作补充，不能替代搜索源输出。

## 降级策略

1. `news_api.py` 内置降级链（60s API ×2 → yyxw → Google News RSS），全部失败时在对应板块注明"今日综合新闻暂无法获取"；**池子不够（去重后不够条数）时用 `news_web.py` 抓频道页补充**（见 8.6）
2. `finance.py` 行情双源全失败 → 省略大盘板块（财经要闻仍照发）；`weather.py` 双源全失败 → 晨报省略天气板块并注明；`fetch_rss.py` / `hupu.py` / `hot_rank.py` / `news_web.py` 个别源失败 → 用其余源补齐，不阻塞整体；热榜单榜失败整榜省略
3. 脚本整体异常（如网络不通）→ 直接告知用户哪一步失败及报错，**不要编造新闻**
4. 若运行环境中恰好有 `web_search`/`advanced_search` 工具，允许作为最终兜底手段，并在晨报末尾注明

## 铁律

- 所有条目必须来自脚本实际输出，**禁止凭模型记忆编造新闻或链接**
- 每条必须附可点击的来源链接
- 条目数量不达标时优先换查询词/放宽时间重搜，而不是编造凑数
- **晚报不得重复当日晨报已发过的内容**（见第 8 步）；去重后条数不足就少发，不许重发

## 验证

完成后自检：① 国际国内合计 ≥5 条 ② 六个板块齐全（天气在最上、热榜在最后） ③ 每条有链接 ④ 日期正确 ⑤ 发邮件时 `mode`/天气/日期正确，且内容里没有 emoji（模板会剥离，但别写） ⑥ **晨报发完跑过 `sent_log.py record`；晚报发前跑过 `sent_log.py filter` 且 `removed_items` 已全部换掉** ⑦ 有财经板块时，指数点位/涨跌幅与 `finance.py` 输出逐字一致

## 定时任务运行经验（2026-08~09 实战沉淀）

每日定时发送（晨报 09:00 / 晚报 17:30）时适用：

1. **任何单源失败都不阻塞发送**：脚本超时/报错 → 对应板块写"今日暂无法获取"并继续，失败源最多重试 1 次，"有多少发多少"
2. **macOS 没有 `timeout` 命令**：禁止用它包裹脚本（会直接 command not found 导致脚本根本没运行）；超时控制用 bash 工具调用的 `timeoutMs` 参数（建议 100000）
3. **整任务可能因 LLM API 传输故障等原因整体崩掉**（数据抓完但没走到发送）——单靠任务内加固防不住，需配合**补跑任务**（见下）
4. **补跑机制（幂等检查型）**：主任务后 5/10/15 分钟各设一个补跑任务，先查收件箱（subject 含"晨报/晚报"+当天日期），已送达则立即退出，未送达才执行完整流程；发送前再查一次防重复；3 次均失败则报告放弃原因
5. **RSS 订阅源（wewe-rss 类）不要并入本流程**：全文同步慢且会与其他任务争抢服务限流，曾导致整任务被拖死；RSS 同步应独立成任务、与报告任务错开时间
6. **定时任务也必须走第 7 步的固定模板**（`render_email.py` → `send_mail.py --html-file`）。历史上直接投 Markdown，换模型后样式会跑版；固定模板就是为了消灭这种漂移
