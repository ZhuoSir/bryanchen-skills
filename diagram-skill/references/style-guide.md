# 设计系统（style-guide）

所有颜色/字体/间距的**单一信源**。SKILL.md 和类型参考里说"ink""accent"时，到这里查当前值。
默认皮肤：**白色纸面 + 蓝白黑灰主调**（白底黑灰墨 + 蓝焦点），适合直接出图；品牌化时改令牌即可。

## 颜色令牌

| 角色 | 默认值 | 用途 |
|---|---|---|
| `paper` | `#ffffff` | 页面底色、标签遮罩填充 |
| `paper-2` | `#f4f7fb` | 区域容器底/浅底（白纸上的极浅蓝灰） |
| `ink` | `#1f2937` | 主文本、主描边（蓝黑） |
| `muted` | `#5b6b80` | 次要文本、默认箭头（蓝灰） |
| `soft` | `#8a919c` | 弱文本、辅助线 |
| `accent` | `#2563eb` | 蓝焦点色，每图 ≤2 个元素 |
| `accent-tint` | `rgba(37,99,235,0.10)` | 焦点节点填充 |
| `link` | `#0e7490` | HTTP/外部调用箭头（青蓝，区别于 accent） |
| `rule` | `rgba(31,41,55,0.14)` | 细分隔线、图例分隔 |

## 字体栈（中文优化，全系统字体、零外部加载）

```css
--font-sans:  "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", system-ui, sans-serif;
--font-serif: "Noto Serif SC", "Songti SC", "SimSun", serif;
--font-mono:  ui-monospace, "SF Mono", Menlo, Consolas, monospace;
```

| 用途 | 字体 | 字号 | 字重 |
|---|---|---|---|
| 页面标题 | serif | 28px | 400 |
| 节点名 | sans | 12px | 600 |
| 副标题/说明 | sans | 12px | 400（muted） |
| 技术子标签（端口/URL/字段类型） | mono | 9px | 400 |
| 眉题/轴标签/图例 | mono 大写加字距 0.14em | 8px | 500 |
| 连线标注 | mono | 8px | 400 |
| 编辑性批注（可选） | serif 斜体 | 14px | 400 |

## 中文排版规则

1. **文本宽度估算**：中文每字 = 1em，英文/数字按 0.55em 估算。节点宽度 = 最长文本估算 + 左右各 12px padding，再向上取 4 的倍数
2. **中文最小 12px**（节点名）；等宽 8-9px 仅限纯 ASCII 技术标签（端口、URL）
3. 长中文标签优先换行（`<tspan>`）而不是缩字号
4. 中英混排时空格可加可不加，但全文要统一

## 间距与网格

- 一切坐标/尺寸/字号为 **4 的倍数**；字号从 {8, 12, 16, 20, 24, 28, 32} 选
- 节点间距 {20, 24, 32, 40, 48}；盒内 padding {8, 12, 16}
- 节点宽从 {80, 96, 112, 128, 144, 160, 180, 200, 240} 选

## 图标（可选，内联 symbol 库）

模板 `assets/template.html` 的 `<defs>` 自带 35 枚 16×16 线性图标（目录与绘制规范见 `references/icons.md`）。规则：

1. **只做语义辅助**：每节点 ≤1 枚；装饰性图标不许加，能省则省（密度 4/10）
2. **不单独设色**：图标描边用 `currentColor`，取色随 `<use style="color:…">`——默认 `var(--color-ink)`，焦点/警示节点用 `var(--color-accent)`，次要信息用 `var(--color-muted)`
3. **槽位**：带图标节点改**左对齐文字**——图标 16×16 放 `x = 盒左 + 12`、`y = 盒心y − 8`；文字起点 `x = 盒左 + 36`；节点宽按 `36 + 文本宽 + 右 padding` 重算并取 4 的倍数
4. **新增图标只允许 `<path>` / `<symbol>` 构造**（rect/circle/line 会产生 self_check 网格告警）；画布 0–16、`stroke-width 1.2`、`fill="none" stroke="currentColor"`
5. 模板注释块内的 `<use>` 示例仅作语法参考，正文按第 3 条槽位摆放

## 品牌化（换肤）

用户提供品牌色时：
1. 主色 → `accent`；若品牌色偏冷（蓝/绿），把 `link` 也一并调整
2. 深色品牌 → 整体反转为 dark 皮肤：`paper` 用深灰 `#16181d`、`ink` 用 `#e6e8eb`，其余角色同思路取反
3. 换完在图底部 colophon 注明皮肤来源（如「配色：客户品牌 VI」）；默认皮肤（白底蓝白黑灰）不需要 colophon
