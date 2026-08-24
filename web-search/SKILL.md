---
name: web-search
description: "联网搜索：用自带脚本真实抓取搜索引擎（Bing → DuckDuckGo Lite 降级链，免 Key 零依赖），支持时间过滤（24小时/一周/一月）。不依赖宿主环境是否提供搜索工具——本 skill 自带完整搜索代码。触发词：搜索、搜一下、查一下、帮我查、检索、latest、search the web。NOT for: 晨报/晚报等综合简报（用 morning-report）、邮件内容检索（用 email-skill）、火车票查询（用 12306-skill）。"
---

# Web Search Skill（web-search）

**自带搜索代码**的联网检索 skill：`scripts/search.py` 直接抓取搜索引擎 HTML 并解析结果，
零依赖（Python 3 标准库）、免 API Key，**不依赖宿主环境是否提供 web_search 工具**。

## 执行流程

```bash
python3 scripts/search.py --query "关键词" [--max 5] [--time day|week|month]
```

- 引擎降级链：**Bing（国内稳定，~1s）→ DuckDuckGo Lite**（部分网络下会超时，作为兜底）
- `--time`：day=过去24小时 / week=一周内 / month=一月内；用户说"最新/今天/这周"时务必加上
- 输出 JSON：`results[]` 含 `title` / `url` / `snippet`；发生降级时带 `note` 字段说明

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
- 中文长查询容易被搜索引擎分词带偏：关键词**控制在 2-6 个词**，太长的问句先提炼再搜
- 若运行环境恰好有宿主 `web_search` 工具，可作为补充交叉验证，并在结果中注明

## 验证

`python3 scripts/search.py -q "测试" --max 1` 返回非空 results 即正常。
