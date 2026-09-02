# CHANGELOG

## 1.3.0（2026-09-02）

图标库扩充（18 → 35 枚）：

- **新增 17 枚高频图标**：`icon-users / mobile / monitor / cpu / network / cart / building / bank / lock / key / search / bell / calendar / flag / target / box / download`，沿用既有规范（16×16、全 path、currentColor、无 self_check 告警）
- **文档**：`references/icons.md` 目录补 17 行、体量上限 24 → 40；SKILL.md / style-guide.md 数量与示例 slug 同步
- 模板 `assets/template.html` 图标库扩至 35 枚，新增图标风格与几何图标集一致（锐角矩形、圆环/圆弧 path 构造）

## 1.2.0（2026-09-02）

默认皮肤改版 + 新增内联图标能力：

- **换肤（默认 = 白底 + 蓝白黑灰）**：`paper` 白纸、`paper-2` 极浅蓝灰容器底、`ink` 蓝黑、`accent` 蓝、`link` 青蓝；全局替换 SKILL.md / style-guide.md / 全部类型参考里的旧色值与"米白/砖红"措辞（含图表内透明底色值），无残留旧令牌
- **新增内联图标库**：`assets/template.html` `<defs>` 自带 18 枚 16×16 线性 `<symbol>`（user/home/star/code/server/database/globe/folder/doc/chart/gear/clock/shield/mail/wallet/check/alert/send），全 `<path>` 构造（不触发 self_check 网格告警）、`currentColor` 随用取色
- **文档**：新增 `references/icons.md`（图标目录 + 节点槽位公式 + 取色/新增规则）；style-guide.md 增补「图标」节并更新令牌表/换肤说明

## 1.1.0（2026-09-02）

跨平台与沙箱环境修复（依据 Windows 实战复盘，23 张图表批量绘制中暴露）：

- **修复** `export_png.py`：Windows 下找不到 puppeteer——新增 Windows 候选路径（NVM_SYMLINK / NVM_HOME / APPDATA\npm / C:\nvm4w），npm 兜底改用 `npm.cmd`；macOS nvm 路径不再硬编码 node 版本号（通配所有版本）
- **修复** `self_check.py` / `export_png.py`：Windows 中文控制台（GBK）打印 emoji/中文 UnicodeEncodeError——`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`（带兼容性保护）
- **新增** `scripts/render_svg.js` + `scripts/package.json`：无浏览器/沙箱环境的 resvg-js 进程内渲染降级（等价 `--bare --transparent`）；`export_png.py` 在 puppeteer 缺失或启动失败时自动降级
- **文档** `references/export.md`：追加「无浏览器/沙箱环境降级：resvg 渲染」「文件名可移植性（交付物用 ASCII 文件名）」两节

## 1.0.0（2026-09-01）

- 首版：13 种图表类型（结构图 ×10 + 数据图 ×3）、设计令牌可换肤、中文排版优化、self_check 质检、PNG 导出（--bare/--transparent/--scale）
