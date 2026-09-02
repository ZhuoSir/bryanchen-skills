# 导出规则（PNG / 透明底 / 纯图）

图表默认交付物是**自包含 HTML**。用户要图片时用 `scripts/export_png.py` 导出 PNG。

## 用法

```bash
python3 scripts/export_png.py <diagram.html> [-o out.png] [--bare] [--transparent] [--scale 2]
```

| 参数 | 说明 |
|---|---|
| `--bare` | **纯图模式**：只截 `<svg>` 区域，去掉页面标题/眉题/图例/留白。适合贴聊天、嵌入其他页面 |
| `--transparent` | **透明背景**：alpha 通道 PNG，可贴到任意底色（PPT/文档/深色页） |
| `--scale` | 缩放倍数（默认 2，高清） |

组合示例：`--bare --transparent` = 纯图透明贴图（发微信/贴 PPT 的最佳形态）。

## 渲染管线

HTML → **puppeteer（headless-shell）** 截图。本机直接调 Chrome 常被沙盒/崩溃上报拦截；
puppeteer 的 headless-shell 是为无头场景设计的，稳定。脚本自动在常见位置查找 puppeteer
（mermaid-cli 自带依赖优先），找不到时给出安装指引。

## 透明底适配规则（透明化时必做）

直接把背景改成透明会踩三个坑，按此处理：

1. **去掉整幅背景 `<rect>`**（`fill="paper"` 那张全幅底）和 body 背景色
2. **去掉标签遮罩**：标签遵守 6-10px 间隙规则时不压线，遮罩在透明底上会露出浅色斑块；但若某标签确实压线（违反间隙规则），先挪标签再导透明版，不要靠遮罩遮
3. **可见性补偿**：低透明度填充在透明底上几乎不可见——
   - `ink 3%~5%` 的填充（外部系统/存储节点）→ 改 `#ffffff` 实底
   - `ink 30%` 的描边 → 改 `ink 50%`
   - `accent-tint` 半透明焦点底 → 改实色浅底（如 `#fbeae4`）
4. 导出后**目检一遍**再交付：重点看节点边框是否都可见、标签与连线是否相触

## bare 模式规则

- 只截 `<svg>` 元素的边界框（不是整页）
- 生成阶段就应省略 eyebrow/h1/图例；若已生成完整版，导出前去掉这些元素即可
- `viewBox` 收紧到内容边界 + 24-32px padding（不要带大片空白）

## 交付形态速查

| 场景 | 形态 |
|---|---|
| 正式文档/汇报插图 | 完整版（标题 + 图例）+ 纸面底 |
| 微信/聊天 | `--bare`（纸面底） |
| 贴 PPT/深色页/任意底色 | `--bare --transparent` |
| 二次编辑 | 交付 HTML 源文件 |

## 无浏览器/沙箱环境降级：resvg 渲染

puppeteer 需要启动浏览器进程；沙箱环境（禁止命名管道/进程创建）或精简系统里会 EPERM 失败。
此时用**进程内光栅化**降级路径：

```bash
cd <skill>/scripts && npm install        # 首次安装 @resvg/resvg-js（原生库，无需浏览器）
node scripts/render_svg.js <图.html> [-o out.png] [--scale 2]
```

- 行为等价于 `--bare --transparent`：只渲染 svg 本体、透明底
- `export_png.py` 在 puppeteer 缺失或启动失败时会**自动降级**到该路径（输出 JSON 带 `engine: "resvg"` 与 note）
- 限制：resvg 无 CSS 布局，svg 根必须有数值 width/height（render_svg.js 会从 viewBox 自动补齐）；不支持 HTML 页面包装（标题/图例属于页面层，bare 模式本就不含）
- 位图细节（滤镜、特殊字体连字）与浏览器渲染可能有细微差异，导出后目检

## 文件名可移植性

交付物（要发给他人/导入其他工具的 PNG、HTML）**使用 ASCII 文件名**：中文文件名在部分查看器、
在线编辑器、导入工具中会出现破图或无法识别（实测复现）。

- 工作副本可以用中文命名（如 `订单流程图.html`）
- **交付/发布前**复制一份 ASCII 文件名副本：`order-flow.png`
- 图内部的 `<title>`/`<desc>`/slug 不受影响，保持中文可读
