# init —— 存量项目接入细则

**定位**：项目体检 + 机制骨架 + 项目画像，一次跑完（约 10 分钟），让后续每个需求的
Phase 1 不再从零认识项目。

**明确不做**：不把存量代码反推成 specs。理由（官方共识 + 实测验证）：
back-fill 的 spec 没有变更驱动，会立刻开始腐烂（*"Those specs go stale"*）；
specs 只为将要改动的部分写，靠里程碑/change 逐个积累。

**触发词**：「初始化 spec」「spec init」「接入 spec 机制」「给这个项目建立 spec」。

---

## 一、七步流程（I1~I7）

### I1 安全快照
1. `git status`：工作区脏 → 提醒用户先提交或明确同意带脏工作区继续（init 只新增文件，
   理论上不冲突，但干净基线便于事后核对）。非 git 仓库 → 警告（分支/commit 机制将不可用，
   流程降级：跳过开分支与 commit 步骤，其余照常），用户明确同意才继续。
2. 记录将触碰路径的现状指纹：`AGENTS.md`（如存在）、`.specrc.yml`（如存在）、
   `specs/`（如存在）→ sha256 清单存对话内，I7 复验用。

### I2 项目体检（纯只读，7 类事实）

| # | 体检项 | 探测方法 | 记录到 profile 哪节 |
|---|---|---|---|
| 1 | 技术栈 | pom.xml / build.gradle / package.json(+lock) / go.mod / requirements.txt / pyproject.toml；框架看依赖清单 | §基本事实 |
| 2 | 模块结构 | Maven 多模块 `<modules>`、pnpm workspace、目录扫描（src/ 布局、前后端分目录） | §基本事实 |
| 3 | 构建/测试/lint 命令 | package.json scripts、Makefile、mvnw/gradlew 存在性；**只识别不执行**（执行在 I3 且需用户同意） | §基本事实 |
| 4 | 既有约定文件 | AGENTS.md、CLAUDE.md、.cursorrules、docs/conventions/、docs/standards/、README 的 contributing/规范章节 | §既有约定（摘录关键条目原文，注明来源文件） |
| 5 | 规范类 skill | 当前会话 catalog 中名字/描述含 standards/规范/conventions/代码标准 的 skill | §既有约定 + 喂给 I5 |
| 6 | git 现状 | 主分支名、最近 tag（`git tag --sort=-creatordate | head -3`）、近 30 条 commit 风格（`git log --oneline -30`，归纳 type(scope) 是否已成习惯）、有无 release/* 分支痕迹 | §git 现状 |
| 7 | SQL/迁移与 CI | flyway/liquibase 目录、db/migration、散置 SQL 目录（docs/sql 等）；.github/workflows、Jenkinsfile、.gitlab-ci.yml | §基本事实 + §已知技术债（SQL 无版本管理时记一笔） |

体检中顺带收集**已知技术债线索**（写死的魔法数字带「没人记得为什么」类注释、TODO/FIXME 密集区、
被标注禁改的目录）→ profile §已知技术债，每条注明「不得顺手改，改需另立 spec」。

### I3 测试基线（默认不跑，先问）

**必须询问**：「是否运行测试基线？（命令: <I2 识别的测试命令>，预计耗时 <估>。
不跑则 profile 标注"基线未测"，之后可随时补。）」

- 用户同意跑 → 执行并如实记录：通过/失败数、**既有失败清单**（逐条：测试名 + 一句话现象）。
  清单的意义：Implement 阶段出现新失败时，对照区分「我改坏的」vs「本来就坏的」。
- 用户拒绝/超时/跑不动 → profile §测试基线 写「未测（init 时跳过，原因: <用户跳过/命令失败>）」，
  不阻塞后续步骤。
- **补测**：任何时候说「补测基线」→ 重跑本步并更新 profile 该节。

### I4 项目画像（specs/_project/profile.md）

按 templates.md 的 profile 模板汇总 I2+I3 → **全文展示给用户核对**：
「以下是项目事实画像，有认错的请指出（尤其：既有约定摘录、技术债、命令）。」
用户核对/修正后落盘。目录 `specs/_project/` 不存在则创建。

### I5 规范路由（.specrc.yml）

I2 的发现直接喂给路由草稿（等价于 SKILL.md §1.4 的探测，但数据已有，不再重扫）：
- 约定文件 → project_files
- 规范类 skill → 按其描述覆盖的领域建议 skill: 源
- 技术栈 → 裁剪领域（纯后端项目 code-frontend 设 none；非 Java 后端提示 global 的
  code-style-backend.md 是 Java 语境，建议 none 或 file: 自建）
展示草稿 → 用户逐行确认 → 写入项目根 `.specrc.yml` → 提醒提交 git。

### I6 目录骨架 + AGENTS.md

1. 建 `specs/`（空目录放 `.gitkeep`）。**releases/ 不建**（首次「新建里程碑」时自动建）。
2. AGENTS.md：
   - 不存在 → 写入精简版（四阶段概要 + 三重确认铁律 + 产物目录 + 「详见 bryanchen-spec skill」，
     ≤40 行，不复制 SKILL.md 全文）
   - 已存在 → 备份 `AGENTS.md.bak.<时间戳>`，把精简版**追加**到原文之后（`---` 分隔），
     追加内容先展示后写。原文件一字不动。

### I7 完成报告

1. 用 I1 快照复验：既有文件零改动（AGENTS.md 为追加、备份存在）。
2. 汇报清单：profile 路径、.specrc.yml 路由一行概括、AGENTS.md 处置方式、测试基线状态。
3. 建议第一个 change：「挑一个小而真实、这周本来就要做的改动」（不选最大最重要的——
   第一次跑流程，仪式成本要低）。
4. 显式声明：init 未修改任何源码、未创建任何 spec、未建 releases/。
5. 提醒提交：`specs/_project/ .specrc.yml AGENTS.md` 进 git（一个 commit：
   `chore(spec): 接入 bryanchen-spec 机制（profile + 规范路由）`）。

---

## 二、幂等规则（重复跑 init）

| 已存在 | 行为 |
|---|---|
| specs/_project/profile.md | **刷新模式**：重跑 I2/I3（I3 仍先问），更新 profile 的事实/基线/技术债节；「既有约定」的人工批注保留不覆盖 |
| .specrc.yml | **不动**。提示用户手工改（它是团队约定，不走 init 刷新） |
| AGENTS.md 已含追加段 | 不重复追加；如追加段是旧版，展示 diff 问用户是否更新 |
| specs/ 已有需求目录 | 完全不触碰 |

---

## 三、init 验收标准（自查清单）

- [ ] profile.md 存在且经用户核对，7 类事实齐全（识别不到的显式写「未发现」而非留空）
- [ ] 测试基线三态之一：已测（含既有失败清单）/ 用户跳过（标注）/ 命令失败（标注原因）
- [ ] .specrc.yml 存在且每行经用户确认
- [ ] AGENTS.md 写入或追加完成，原内容零丢失（有备份）
- [ ] I1 快照复验通过：除新增文件与 AGENTS.md 追加外零变化
- [ ] 完成报告已含「建议的第一个 change」与「未碰源码」声明

---

## 四、与既有流程的衔接

- init 跑过 → 首次「新需求」时 Phase 0 的规范源解析自动跳过（.specrc.yml 已存在，SKILL.md §1.4 天然兼容）
- Phase 1 必读 profile（SKILL.md §2 已挂钩）
- profile §已知技术债 与 spec 的 Non-goals 联动：需求碰到技术债条目时，Non-goals 必须显式排除
- profile §git 现状 供 git-workflow 档位选择参考：已有 release/* 痕迹 → 建议 B 档；否则 A 档

---

## 五、可选子流程：baseline-capture（现状基线捕获）

**触发**：「给 <模块> 建 spec 基线」。
**适用**：高风险且**即将大改**的单个模块。默认不建议做——「马上要改」是唯一正当理由。

流程（走一个特殊 spec，三重确认照常）：
1. 建 `specs/{YYYYMMDD}_baseline-{模块名}/`
2. requirements.md 特殊写法：
   - proposal 性质的头部声明：「本文档为现状基线捕获，描述系统当前实际行为，**不是行为变更**」
   - R 条款按**现有代码的对外可观察行为**写 EARS，**每条标注证据来源**：
     `（证据: test/pricing.test.js「满减档位」用例 / src/pricing.js L3-7 / 2026-09-26 实测）`
   - 与代码不符的「应有行为」**不写进基线**（那是新需求，另立 change）
3. plan.md 写「无——基线捕获不产生实现」；tasks.md 只有一组核对任务
   （逐条 R 对照代码/测试复核，验证方式=证据可复现）
4. 三重确认时用户核对的是「这确实是现状」
5. 确认后该模块有了对照基线，后续改它的 change 可正常使用 MODIFIED 语义
   （在 requirements.md 里引用基线条目编号）

**纪律**：一次只做一个模块；基线 spec 的 R 编号前缀加 `B-`（如 B-R-01）与普通需求区分；
基线捕获中发现的技术债 → 登记进 profile §已知技术债，不在基线里修。
