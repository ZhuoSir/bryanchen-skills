---
name: diagram-skill
version: "1.3.0"
description: "绘制编辑级中文图表：架构图、流程图、时序图、ER 图、甘特图、状态机、泳道图、树状图、象限图、时间线、柱状图、折线图、饼图/环形图，输出自包含 HTML+内联 SVG（可浏览器直接打开，可导出 PNG/透明底）。中文字体优化（苹方/微软雅黑/Noto Sans SC）、4px 网格、正交连线、焦点色克制、数据图按公式换算坐标。触发词：画图、画个图、架构图、流程图、时序图、ER图、甘特图、泳道图、状态机、树状图、象限图、时间线、柱状图、折线图、饼图、数据图表、diagram、bar chart、line chart、pie chart。NOT for: 快速草图/纯文本图（用 mermaid-skill 或文字）、海报/视觉设计（用 canvas-design）、PPT 文件（用 bez-ppt-skill）。"
---

# Diagram Skill（diagram-skill）

编辑级中文图表生成：**自包含单 HTML + 内联 SVG**，无构建步骤、无外部依赖（字体全用系统栈）。
10 种图表类型，布局细节按需从 `references/type-*.md` 加载。

借鉴 diagram-design 的架构：**本 skill 没有渲染代码——图是你按规则手写 SVG 画出来的，脚本只负责质检。**

## 0. 什么时候用 / 不用

✅ 读者从图形比从文字/表格能学到更多时（架构、流程、时序、关系）

❌ 不用画的情况：
- 3 行表格能说清的 → 用表格
- 快速示意/终端场景 → 用 mermaid-skill
- 单个框的"图" → 直接写一句话

画之前自问：*这张图比一段写得好的话更有信息量吗？* 不是就别画。

## 1. 设计哲学

**最高质量的修改通常是删除。**

- 每个节点代表一个独立的点子；永远一起出现的两个节点应合并成一个
- 每条连线必须携带信息；布局已经能说明的关系，删掉那根线
- 焦点色（蓝）是**编辑手段**：每张图最多 1–2 个焦点元素，到处用等于没用
- **目标密度 4/10**：技术上完整，但不需要图例导读。超过 9 个节点，就该拆成两张图

## 2. 选型路由

| 你要展示什么 | 类型 | 参考文件（画前必读） |
|---|---|---|
| 系统组件 + 连接关系 | **架构图** | [references/type-architecture.md](references/type-architecture.md) |
| 带分支的决策逻辑 | **流程图** | [references/type-flowchart.md](references/type-flowchart.md) |
| 角色间按时间顺序的消息 | **时序图** | [references/type-sequence.md](references/type-sequence.md) |
| 实体 + 字段 + 关系 | **ER 图** | [references/type-er.md](references/type-er.md) |
| 任务/阶段在时间轴上排期 | **甘特图** | [references/type-gantt.md](references/type-gantt.md) |
| 状态 + 迁移 + 条件 | **状态机** | [references/type-state.md](references/type-state.md) |
| 跨职能流程 + 交接 | **泳道图** | [references/type-swimlane.md](references/type-swimlane.md) |
| 父子层级关系 | **树状图** | [references/type-tree.md](references/type-tree.md) |
| 双轴定位/优先级 | **象限图** | [references/type-quadrant.md](references/type-quadrant.md) |
| 事件在时间轴上 | **时间线** | [references/type-timeline.md](references/type-timeline.md) |
| 跨类别数值比较 | **柱状图** | [references/type-bar.md](references/type-bar.md) |
| 连续趋势/时间序列 | **折线图** | [references/type-line.md](references/type-line.md) |
| 部分占整体比例 | **饼图/环形图** | [references/type-pie.md](references/type-pie.md) |

- 数据图表（柱状/折线/饼）的**数值→像素换算必须严格按类型参考里的公式**逐步计算，禁止目测估算

- 两种类型都沾边 → 选主导轴的那个；超预算 → 拆"总览 + 细节"两张
- **画之前用一句话说明计划**：类型 + 画布尺寸 + 因预算要砍掉什么。用户在场就让他先确认

## 3. 设计系统（摘要，全文见 references/style-guide.md）

颜色用语义角色，不写死色值：`paper / paper-2 / ink / muted / soft / accent / accent-tint / link / rule`。
默认皮肤：**白色纸面 + 蓝白黑灰主调**（白底、蓝黑墨、蓝焦点，无米白）。换肤改 `assets/template.html` 的 `:root` 或按 style-guide.md 定制。

**图标**（可选）：节点内可放图标做语义锚点——模板 `<defs>` 自带 35 枚内联 16×16 线性 `<symbol>`（`icon-user / icon-server / icon-database / icon-code / icon-network / icon-search …`），目录与槽位/取色规则见 [references/icons.md](references/icons.md)。每节点 ≤1 枚、颜色随 `currentColor`、仅语义不装饰。

**节点处理**（fill / stroke）：

| 节点类型 | 填充 | 描边 |
|---|---|---|
| 焦点（≤2 个） | accent-tint | accent |
| 常规（服务/步骤） | #ffffff | ink |
| 存储/状态 | ink 5% 透明 | muted |
| 外部系统/云 | ink 3% 透明 | ink 30% 透明 |
| 可选/异步 | ink 2% 透明 | ink 20% 透明，虚线 4,3 |

**字体规范（中文优化）**：

| 用途 | 字体 | 大小 |
|---|---|---|
| 页面标题 H1 | 衬线（Noto Serif SC/宋体） | 28px |
| 节点名（人读） | 无衬线（苹方/雅黑） | 12px，600 |
| 技术标签（端口/URL/类型） | 等宽 | 9px |
| 眉题/轴标签 | 等宽，大写，加字距 | 8px |
| 连线标注 | 等宽 | 8px |

**中文排版铁律**：中文每字按 1em 宽估算文本长度；中文不小于 12px（节点名）；不要把大段中文放等宽字体。

## 4. SVG 通用规则（不可协商）

1. **正交圆角连线**：不同轴的节点之间禁止斜线。拐弯用四分之一圆弧（r=8，紧凑处 r=6）
2. **连线标注**：必须有纸色不透明遮罩 rect，且遮罩底边与连线**保持 6–10px 可见间隙**；标注 ≤14 字，居中于线段中点上方
3. **连线不重叠**：两条线不得共用路径/平行贴合；同边多线进入同一节点时，连接点沿边均匀分散（间距 ≥12px）
4. **连线不得穿越非端点节点**——绕路；确实绕不开时改虚线且标注放在可见端
5. **绘制顺序**：背景 → 区域容器 → 箭头 → 标签 → 节点（先画线后画框）
6. **图例**：底部横条 + 细分隔线，禁止浮在图区里
7. **箭头 marker 三种常备**：`arrow`（muted 内部）/ `arrow-accent`（焦点）/ `arrow-link`（外部调用）

**反模式（AI 味清单）**：阴影、大圆角(>8px)、深色底+荧光、全部节点同款框、焦点色滥用、斜线、标签骑线、竖排文字、图例浮在图内。

## 5. 复杂度预算

| 限制 | 值 |
|---|---|
| 节点 | ≤9 |
| 连线 | ≤12 |
| 焦点色元素 | ≤2 |
| 时序图生命线 | ≤5 |
| 泳道 | ≤5 |
| ER 实体 | ≤8 |
| 甘特任务 | ≤12 |
| 树深度 | ≤4 |
| 象限条目 | ≤12 |
| 柱状图 | 单系列柱 ≤8；多系列类目 ≤6 × 系列 ≤3 |
| 折线图 | 每系列点 ≤12、系列 ≤3、关键点标注 ≤4 |
| 饼图/环形图 | 切片 ≤6（超出合并"其他"），标签右排列表 |

超出 → 拆图。4px 网格：所有坐标/尺寸/字号必须被 4 整除（描边宽 0.8/1/1.2 和透明度豁免）。

## 6. 输出契约

- 单文件 `.html`：内联 CSS + 内联 SVG，**无 JS、无外部资源**（字体用系统栈）
- 从 `assets/template.html` 复制起步：替换 eyebrow / h1 / `[slug]` / `<title>` / `<desc>` / SVG 正文
- **可访问性契约**：`<svg role="img" aria-labelledby="<slug>-title <slug>-desc">`；`<title>` 必须是 svg 第一个子元素；id 带 slug 前缀（禁止裸 `title`/`desc`）
- `<desc>` 写内容不写几何：「展示订单从下单到履约的跨系统流转」，不是「上面一个框下面五个框」

## 6.1 导出 PNG（用户要图片/发微信/贴 PPT 时）

```bash
python3 scripts/export_png.py <图.html> [-o out.png] [--bare] [--transparent] [--scale 2]
```

- `--bare`：纯图（只截 svg 区域，去标题/图例）；`--transparent`：透明背景
- **导出前必读** [references/export.md](references/export.md)：透明底需做可见性补偿（低透明度填充会消失）、bare 模式 viewBox 收紧等规则
- 发微信/IM：用 `--bare --transparent` 或 `--bare` 出 PNG 后直接发
- 导出 PNG 是被动行为：用户没要图片就只交付 HTML

## 7. 交付前自检

1. 过一遍：类型选对了吗？有节点/连线/标签能删吗？焦点色 ≤2？预算内？
2. 技术项：箭头先于节点绘制？标签遮罩 6-10px 间隙？无斜线？无阴影？字号坐标全是 4 的倍数？title/desc 已填且带 slug 前缀？
3. **运行自检脚本**：

```bash
python3 scripts/self_check.py <生成的html>
```

通过后才能交付。不通过逐条修复，不要绕过。

## 8. 换肤

用户给了品牌色/网站时，读 [references/style-guide.md](references/style-guide.md) 定制令牌；默认皮肤可直接用，无需询问。
