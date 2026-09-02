# diagram-skill 今日实战复盘与修改建议

**日期**：2026-09-02
**场景**：Harness 讲义 23 张中文图表批量绘制（HTML + 内联 SVG → 透明底 PNG）
**环境**：Windows + DSH 沙箱
**产出**：`Harness图表\`（html\ 23 张、png\ 23 张、src\ 23 份 .mmd、scripts\ 工作副本）
**结论**：发现 **4 个缺陷**（2 阻断 + 1 环境增强 + 1 交付规范），修改方案已写好、**尚未应用到技能目录**，待确认后实施

---

## 一、今日使用概况

用 diagram-skill 手绘 23 张中文流程图（四层架构、Agent Loop 七环节、五种推理范式、循环控制、上下文组成/管理、工具类型/接入/治理、任务分解、记忆四层/读写时机、四种多智能体协作、自主级别光谱、端边云、一页纸记忆图），全部按技能规则手写 SVG、过自检、导出透明 PNG，并嵌入 PPT。

过程中技能本身暴露 4 个缺陷：**2 个阻断级**（Windows 下脚本直接不可用）、1 个环境适应性（沙箱无浏览器导出链路失效）、1 个交付规范（中文文件名导致破图）。均已在工作区副本上验证修复有效。

---

## 二、需要修改的问题清单

| # | 模块 | 缺陷 | 严重度 |
|---|------|------|--------|
| P1 | `scripts/export_png.py` | Windows 下找不到 puppeteer：候选路径只列了 unix（~/.nvm、/usr/local、/opt/homebrew），无 Windows 位置；兜底 `subprocess.run(["npm",...])` 在 Windows 上应写 `npm.cmd`，`shell=False` 时直接 FileNotFoundError 被吞 → 「未找到 puppeteer」 | 🔴 阻断 |
| P2 | `scripts/self_check.py` | Windows 中文系统控制台默认 cp936/GBK，打印 ✅/❌/⚠️ 时 `UnicodeEncodeError` 崩溃——自检实际通过却表现为失败，结果完全拿不到 | 🔴 阻断 |
| P3 | `scripts/`（新增） | 沙箱/无浏览器环境（DSH 禁止程序开命名管道）puppeteer 启动 EPERM，PNG 导出链路整体失效 → 新增 `render_svg.js`（resvg-js 进程内光栅化，零子进程）作为降级路径 | 🟠 增强 |
| P4 | `references/export.md` | 交付物用中文文件名，部分查看器/在线编辑器/导入工具破图（本轮实测复现）→ 建议交付发布前复制 ASCII 文件名副本 | 🟡 建议 |

---

## 三、修改方案（M1~M5，已写入 `Harness图表\skill-patches\`）

| # | 对象 | 类型 | 内容 |
|---|------|------|------|
| M1 | `scripts/export_png.py` | 修改 | `find_puppeteer()` 增加 Windows 候选（NVM_SYMLINK/NVM_HOME/APPDATA\npm\node_modules）+ `npm.cmd` 兜底（完整 patch 见 P1 文件，本机已验证命中 `C:\nvm4w\nodejs\node_modules\@mermaid-js\mermaid-cli\node_modules\puppeteer`） |
| M2 | `scripts/self_check.py` | 修改 | `main()` 开头加 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` 一行；`export_png.py` 同步加上（中文提示在 GBK 下会乱码） |
| M3 | `scripts/render_svg.js` + `scripts/package.json` | 新增 | resvg-js 进程内渲染：提取 HTML 内联 `<svg>` → 默认透明底 bare（等价 `--bare --transparent`）、`scale` 参数；依赖 `@resvg/resvg-js ^2`；注意 svg 根必须带数值 width/height（resvg 无 CSS 布局） |
| M4 | `references/export.md` | 修改 | 追加两节：「无浏览器/沙箱环境降级：resvg 渲染」（何时用/命令/限制）、「文件名可移植性」（交付物用 ASCII 文件名） |
| M5 | `SKILL.md` / `CHANGELOG.md` | 修改 | version 1.0.0 → 1.1.0，追加变更记录 |

**实施顺序**：M1→M2→M3→M4→M5（前三项互不依赖）；先备份技能目录（`diagram-skill.bak`）再改；用 `Harness图表\html\01_四层架构_AI技术栈.html` 做端到端回归，抽样 2~3 张对比 PNG 像素尺寸。
**回滚**：全部可逆——M1/M2 函数级替换、M3 纯新增、M4/M5 纯文档。

---

## 四、当前状态

- ✅ 方案已成型（`Harness图表\skill-patches\`：README.md + 修改方案.md + P1~P4 补丁文件）
- ⏸️ **技能目录 `C:\Users\KypCa\.dsh\skills\diagram-skill\` 尚未应用**（已核查：export_png.py 无 Windows 候选、self_check.py 无 reconfigure、scripts 下无 render_svg.js）
- 📁 工作区 `Harness图表\scripts\` 下的验证版脚本保留不动，作为补丁验证参照

## 五、不在修改范围内的事项

- 技能默认皮肤（米白 + 砖红）不改——本轮蓝白黑灰是项目级换肤，属于正确使用方式，无需沉淀
- 已交付的 23 张图与 PPT 不受影响（本次修复针对技能本身，不回溯改图）

---

## 六、建议下一步

1. 确认本方案后，按 M1→M5 应用到技能目录（约 1 小时工作量含回归）
2. 应用后生成行为固化：Windows 直接出 PNG、沙箱走 resvg 降级、交付物自动用 ASCII 文件名
3. 若近期不再出图，可暂缓；但建议下次使用前先应用 P1/P2（必炸），否则 Windows 上 export 与 self_check 仍不可用

---

*版本记录：diagram-skill 1.0.0 → 建议 1.1.0；方案材料位于 `Harness图表\skill-patches\`。*