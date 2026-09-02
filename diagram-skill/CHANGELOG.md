# CHANGELOG

## 1.1.0（2026-09-02）

跨平台与沙箱环境修复（依据 Windows 实战复盘，23 张图表批量绘制中暴露）：

- **修复** `export_png.py`：Windows 下找不到 puppeteer——新增 Windows 候选路径（NVM_SYMLINK / NVM_HOME / APPDATA\npm / C:\nvm4w），npm 兜底改用 `npm.cmd`；macOS nvm 路径不再硬编码 node 版本号（通配所有版本）
- **修复** `self_check.py` / `export_png.py`：Windows 中文控制台（GBK）打印 emoji/中文 UnicodeEncodeError——`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`（带兼容性保护）
- **新增** `scripts/render_svg.js` + `scripts/package.json`：无浏览器/沙箱环境的 resvg-js 进程内渲染降级（等价 `--bare --transparent`）；`export_png.py` 在 puppeteer 缺失或启动失败时自动降级
- **文档** `references/export.md`：追加「无浏览器/沙箱环境降级：resvg 渲染」「文件名可移植性（交付物用 ASCII 文件名）」两节

## 1.0.0（2026-09-01）

- 首版：13 种图表类型（结构图 ×10 + 数据图 ×3）、设计令牌可换肤、中文排版优化、self_check 质检、PNG 导出（--bare/--transparent/--scale）
