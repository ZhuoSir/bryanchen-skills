# bryanchen-skills

个人维护的 Agent Skills 集合（适用于支持 SKILL.md 规范的 AI Agent，如 DeepSeek Harness / Claude Code 等）。

## Skills 列表

### 🌅 morning-report — 每日晨报生成

生成一份完整的每日晨报，包含五个板块：

| 板块 | 数据源 | 说明 |
|---|---|---|
| 🌤️ 今日天气 | Open-Meteo（兜底 wttr.in） | 北京 / 深圳 / 上海 / 杭州 / 通辽 / 崇礼，含高低温、体感、湿度、降水概率 |
| 🌍 国际新闻 | 60s API ×2 → yyxw → Google News RSS（内置降级链） | 当日综合新闻 5–10 条 |
| 🇨🇳 国内新闻 | 同上 | 与​​国际新闻同源，由模型按内容归类 |
| 🤖 AI 动态 | 量子位 / TechCrunch AI / InfoQ 中文（RSS） | 最近 2 天行业新闻约 5 条 |
| ⚽🏀 体育 | 虎扑移动端（m.hupu.com/nba、/soccer） | 置顶帖 📌 + 最新热帖前 5–10 条 |

晨报末尾附「今日寄语」（优先采用 60s API 每日一句），落款"爱你的悠悠"。

**特点**：

- 零依赖：纯 Python 3 标准库，无需安装任何包
- 免 API Key：全部使用免费 API / RSS / 静态页面，不通过搜索引擎抓新闻
- 自带降级链与重试，易超时的源排在最后
- 铁律：禁止模型凭记忆编造新闻，每条必须附来源链接

**触发词**：晨报、早报、今日新闻简报、morning report、daily briefing

## 目录结构

```
morning-report/
├── SKILL.md            # skill 说明与执行流程
└── scripts/
    ├── weather.py      # 六城市天气
    ├── news_api.py     # 综合新闻（免费 API 降级链）
    ├── fetch_rss.py    # AI 行业 RSS
    └── hupu.py         # 虎扑足篮球热帖
```

## 安装

将对应 skill 目录复制到本地 skills 目录即可：

```bash
cp -R morning-report ~/.agents/skills/
```

之后在会话中说"给我一份今天的晨报"即可触发。

## 使用示例

```
用户：获取一下今天的晨报
Agent：并行运行 4 个脚本 → 组装输出晨报
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
