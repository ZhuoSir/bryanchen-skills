---
name: web-search
description: "联网搜索：自带完整多引擎搜索代码（复刻 DSH free-search 降级链：首选引擎 → 付费引擎 → 免费引擎），免 Key 零依赖即可用（bing/anysearch/ddg/ddg-lite/searxng/tavily/exa/keenable 全部免 Key），支持时间过滤（day/week/month/year/12h/3d/YYYY-MM-DD）。不依赖宿主环境是否提供搜索工具。触发词：搜索、搜一下、查一下、帮我查、检索、latest、search the web。NOT for: 晨报/晚报等综合简报（用 morning-report）、邮件内容检索（用 email-skill）、火车票查询（用 12306-skill）。"
---

# Web Search Skill（web-search）

**自带完整搜索代码**的联网检索 skill，引擎链与降级逻辑完整复刻 DSH free-search 插件：
零依赖（Python 3 标准库）、**全部引擎免 Key 可用**，不依赖宿主环境是否提供搜索工具。

## 执行流程

```bash
python3 scripts/search.py --query "关键词" [--max 5] [--engine bing] [--time week]
```

### 引擎降级链（与 DSH web_search 一致）

```
首选引擎（默认 bing）→ 其他付费引擎（exa/tavily/keenable 无 Key 走免费通道）→ 免费引擎（bing/anysearch/ddg/ddg-lite/searxng）
```

- **10 个引擎**：bing、anysearch、ddg、ddg-lite、searxng（多实例轮询）、tavily、exa、keenable、perplexity、deepseek-official
- **免 Key**：bing / anysearch / ddg / ddg-lite / searxng / tavily(keyless) / exa(MCP) / keenable(MCP)
- **需 Key**（从环境变量读取）：`PERPLEXITY_API_KEY`、`DEEPSEEK_API_KEY`；`EXA_API_KEY`/`TAVILY_API_KEY`/`KEENABLE_API_KEY` 配了走账号档（更快更稳）
- 整条链共享 **30s 总预算**；首选失败自动降级，输出带 Note 说明原因
- 带 `--time` 时，支持时间过滤的引擎（tavily/exa/keenable/searxng/ddg/ddg-lite）排在前面；首选不支持则**跳过**（Note 写明 "does not support time filtering"）

### 参数

| 参数 | 说明 |
|---|---|
| `--query` | 搜索关键词（2–6 个词，长问句先提炼） |
| `--max` | 最多返回条数（默认 5） |
| `--engine` | 首选引擎（默认 bing；国内网络 ddg 系基本不可用，仅作兜底） |
| `--time` | `day`/`week`/`month`/`year`、`12h`/`3d`/`2mo`/`1y`、`YYYY-MM-DD`（该日期之后） |

### 输出

```json
{"query": "...", "engine": "exa", "note": "Note: bing unavailable or failed (...), using exa.",
 "results": [{"title", "url", "snippet", "publishedAt"?}], "answer"?: "perplexity/deepseek 引擎附答案摘要"}
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
- 输出含 `note` 时（发生了降级），向用户如实转述实际使用的引擎
- 若运行环境恰好有宿主 `web_search` 工具：优先用宿主工具（引擎更多更快），本 skill 作兜底或交叉验证

## 验证

`python3 scripts/search.py -q "测试" --max 1` 返回非空 results 即正常。
