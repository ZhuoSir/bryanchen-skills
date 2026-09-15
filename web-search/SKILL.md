---
name: web-search
description: "联网搜索：自带完整多引擎搜索代码（复刻 DSH free-search 降级链：首选引擎 → 付费引擎 → 免费引擎），免 Key 零依赖即可用（bing/anysearch/ddg/ddg-lite/searxng/tavily/exa/keenable 全部免 Key），支持时间过滤（day/week/month/year/12h/3d/2mo/YYYY-MM-DD）。默认引擎 exa（非 bing），带引擎画像与结果自检：实体级检索（企业名/人名/site: 定向）加 --strict。不依赖宿主环境是否提供搜索工具。触发词：搜索、搜一下、查一下、帮我查、检索、latest、search the web。NOT for: 晨报/晚报等综合简报（用 morning-report）、邮件内容检索（用 email-skill）、火车票查询（用 12306-skill）。"
---

# Web Search Skill（web-search）

**自带完整搜索代码**的联网检索 skill，引擎链与降级逻辑完整复刻 DSH free-search 插件：
零依赖（Python 3 标准库）、**10 个引擎中 8 个免 Key 可用**，不依赖宿主环境是否提供搜索工具。

## 执行流程

```bash
# 普通检索
python3 scripts/search.py --query "关键词" [--max 5] [--engine exa] [--time week]

# 实体级检索（企业名 / 人名 / site: 定向）—— 推荐加 --strict
python3 scripts/search.py --query "site:pedaily.cn 融资" --strict

# 查看引擎画像
python3 scripts/search.py --list-engines
```

### 引擎降级链

```
首选引擎（默认 exa）→ 其他付费引擎（tavily/keenable/perplexity/deepseek-official，无 Key 的走免费通道）→ 免费引擎（bing/anysearch/ddg/ddg-lite/searxng）
```

- **10 个引擎**：bing、anysearch、ddg、ddg-lite、searxng（多实例轮询）、tavily、exa、keenable、perplexity、deepseek-official
- **免 Key**：bing / anysearch / ddg / ddg-lite / searxng / tavily(keyless) / exa(MCP) / keenable(MCP)
- **需 Key**（从环境变量读取）：`PERPLEXITY_API_KEY`、`DEEPSEEK_API_KEY`；`EXA_API_KEY`/`TAVILY_API_KEY`/`KEENABLE_API_KEY` 配了走账号档（更快更稳）
- 首选引擎可用环境变量 `WEB_SEARCH_ENGINE` 覆盖（默认 `exa`；国内网络建议 `tavily`）
- 整条链共享 **30s 总预算**；首选失败自动降级，输出带 Note 说明原因
- **单引擎预算**：抓 HTML 的引擎（bing/ddg/ddg-lite/searxng）单独限时 **8s**。实测 ddg 耗时
  **39.5s**、searxng **48.4s**（都超过 30s 总预算，因为重试各自计时），不设上限会吃光整条链、
  把后面的 precision 引擎饿死，最终报"全网搜索失败"——而实际只是第一个引擎不可达。
  限时后同一场景降到约 10s，并**成功降级拿到 exa 结果**（对照：exa 3.4s / tavily 2.2s /
  keenable 4.8s / anysearch 1.6s / bing 0.8s）
- 带 `--time` 时，支持时间过滤的引擎（tavily/exa/keenable/searxng/ddg/ddg-lite）排在前面；首选不支持则**跳过**（Note 写明 "does not support time filtering"）

> **默认引擎与 DSH 不同**：DSH free-search 插件默认 bing，本 skill **有意改为 exa**。原因是
> bing 的失败是**静默**的——会让"看起来成功"的假结果直接进入下游结论。详见下节实测。

### 引擎画像（`--list-engines` 可查）

引擎质量按**实测**维护，不是凭印象。改这张表前请先按本节末尾的方法复测。

| 引擎 | 档位 | `site:` | 说明 |
|---|---|---|---|
| exa / tavily / keenable | **precision** | ✅ 实测遵守 | 适合实体级检索；exa 无 Key 走 MCP 免费通道 |
| perplexity / deepseek-official | precision | 未验证 | 需 Key |
| anysearch | standard | ✅ 实测遵守（2/3） | |
| searxng / ddg / ddg-lite | standard | 未验证 | 国内网络常整体超时不可用 |
| **bing** | **broad** | ❌ **实测忽略** | **会把实体名当普通词处理**，结果不可直接采信 |

**broad 档为什么危险**——实测（在本仓库复现过，非推测）：

```
$ python3 scripts/search.py -q "高升控股股份有限公司 首席技术官 CTO" --engine bing
→ 百度百科「高升（中国足球运动员）」
→ 百度百科「高升（汉语词语）」（拼音 gāo shēng 的词典释义）
→ 前国脚高升的新闻
→ 而 engine 字段报 "bing"，无 error、无 note          ← 这就是静默错配

同一检索词 --engine exa  → 命中真实 CTO 唐文（腾讯云 TVP 页 + CNUTCon 讲者页）
```

`site:` 被忽略同样实测：`site:pedaily.cn 融资` 在 bing 下 3/3 条结果来自 baike / zhihu，
**0 条**来自 pedaily.cn；exa / tavily / keenable 均 3/3 落在目标域。

**为什么降级链兜不住它**：降级只在「失败或 0 结果」时触发，而静默错配**返回了结果**，
所以链永远不会往后走。这正是需要结果自检的原因。

**复测方法**（改上面这张表之前先跑，别凭印象）：

```bash
# ① 实体级精确匹配：拿一个已知答案的企业名/人名，看各引擎能否命中
python3 scripts/search.py -q "<已知企业名> 首席技术官 CTO" --max 3 --engine <引擎>

# ② site: 是否遵守：看结果是否全部落在目标域
python3 scripts/search.py -q "site:<目标域> <关键词>" --max 3 --engine <引擎>
```

③ 耗时：抓 HTML 的引擎在不可达网络下会明显超时（>8s 说明已被单引擎预算兜住）。

判据：① `self_check.relevance.level == "none"`（结果与查询词面完全无交集）即为**错配**；
② `self_check.site_filter.honored == false` 即为**不遵守 `site:`**。二者都不需要人工读结果，
直接看字段即可。

### 结果自检（`self_check` / `warning`）

每次成功检索都会跑两项自检，结果写入输出的 `self_check`：

| 自检 | 判定方式 | 触发条件 |
|---|---|---|
| `site_filter` | **确定性**：比对结果 URL 的 host 是否落在 `site:` 目标域 | query 含 `site:` 且 **0 条**来自目标域 → `honored=false` |
| `relevance` | **保守**：只判「完全无交集」——query 的关键词项在标题+摘要里一个都没出现 | `level="none"` |

判定阈值刻意保守（**宁漏不误伤**）：

- `relevance` 在 query 词项 **少于 2 项**时不判定（单词查询没有判别力，直接返回 `null`）
- CJK 长词按**整词**计，所以「企业全称 vs 简称」这类部分命中**不会**被误判为失败
  （实测：exa 返回 `matched=1/3` → 判 `ok`；bing 返回 `0/3` → 判 `none`）
- `coverage`（CJK bigram 覆盖率）只作参考、**不参与判定**：实测错配 0.08 / 正确 0.54 虽有
  区分度，但样本太少，拿它做门禁有误伤风险

**两种模式**：

| 模式 | 自检不通过时 |
|---|---|
| 默认 | 照常返回结果，但输出 `warning` 说明问题（**不静默**，也不拦路） |
| `--strict` | **视为该引擎失败，继续降级**（宁可无结果，不用错结果） |

`--strict` 还会做三件「失败关闭」的事：排除 broad 档引擎；query 含 `site:` 时只用**实测遵守**
`site:` 的引擎（`site` 为 `null`＝未验证的也排除，因为无法确认它是否真做了定向）；排除**画像表
里没有登记**的引擎（质量未知，不放进结果）。

> **实体级检索请用 `--strict`**：企业名、人名、`site:` 定向，以及任何要写进结论的事实。

### 参数

| 参数 | 说明 |
|---|---|
| `--query` | 搜索关键词（2–6 个词，长问句先提炼） |
| `--max` | 最多返回条数（默认 5） |
| `--engine` | 首选引擎（默认 `exa`，可用 `WEB_SEARCH_ENGINE` 覆盖；国内网络 ddg 系基本不可用，仅作兜底） |
| `--time` | `day`/`week`/`month`/`year`、`12h`/`3d`/`2mo`/`1y`、`YYYY-MM-DD`（该日期之后） |
| `--strict` | 精度优先：排除 broad 档、`site:` 定向时排除未验证引擎、自检不通过即继续降级 |
| `--list-engines` | 打印引擎画像（档位 / `site:` 支持 / 时间过滤引擎）后退出 |

### 输出

```json
{"query": "...", "engine": "exa",
 "note"?: "Note: bing skipped (ignores site: operator ...), using exa.",
 "warning"?: "引擎 \"bing\" 为 broad 档（...） | 结果与查询无词面交集（0/3：...）",
 "self_check"?: {"site_filter": {"domains": ["pedaily.cn"], "matched": 3, "total": 3, "honored": true},
                 "relevance": {"terms": 3, "matched": 1, "level": "ok", "coverage": 0.54, "missing": [...]}},
 "results": [{"title", "url", "snippet", "publishedAt"?}],
 "answer"?: "perplexity/deepseek 引擎附答案摘要"}
```

## 结果整理

按以下格式向用户呈现（筛选掉广告和明显无关条目，保留 3-5 条）：

```markdown
🔍 **关于「关键词」的检索结果：**

### 📌 核心发现
（1-2 句话总结最重要的发现）

### 📋 详细信息
1. **标题**
   - 要点：……
   - 来源：[链接]

### 💡 建议
（1 条实用建议）
```

## 铁律

- 所有结论必须来自脚本实际返回的 `results`，**禁止凭模型记忆编造信息或链接**
- 结果为空或全失败（`error` 字段）时如实告知，可建议换关键词重试
- 输出含 `note` 时（发生了降级或被规则跳过），向用户如实转述实际使用的引擎
- **输出含 `warning` 时，不得把该结果作为事实依据**。按 `warning` 的具体内容处置：
  - `self_check.relevance.level == "none"`（结果与查询无词面交集）→ **极可能是语义错配**，
    改用 `--strict` 重试；仍不行就如实告知"未查到可靠来源"，**不要**将就使用
  - `self_check.site_filter.honored == false`（`site:` 没生效）→ 结果可能来自其他站点，
    改用 `--strict` 或换 precision 档引擎重试
  - broad 档警告 → 实体级结论需用 precision 档引擎复核后再采信
- **实体级检索必须加 `--strict`**：企业名、人名、`site:` 定向，以及任何将写入报告/画像的事实
- 若运行环境恰好有宿主 `web_search` 工具：优先用宿主工具（引擎更多更快），本 skill 作兜底或交叉验证；
  但其默认引擎若为 bing，**同样存在本节的静默错配问题**（宿主侧"0 结果才降级"也救不了它）
- 引擎画像表（档位 / `site:`）是按实测维护的结论，**不要凭印象改动**；要改先复测并在本文件记录实测

## 验证

```bash
python3 scripts/search.py -q "测试" --max 1        # 返回非空 results 且无 warning 即正常
python3 scripts/search.py --list-engines           # 应报出 default=exa，bing 为 broad 档
```
