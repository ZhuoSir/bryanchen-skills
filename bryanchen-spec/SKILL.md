---
name: bryanchen-spec
description: "四阶段规格开发流程编排器：Specify（EARS 需求定义）→ Plan（技术方案）→ Tasks（带验收标准的任务拆解）→ Implement（按规范编码）。三重人工确认后才允许写代码；产物带语义化版本号，需求变更全程可追溯；内置 git 分支/提交规范与双层 changelog；支持里程碑发版管理（多需求汇总成大版本，SQL/配置按版本聚合为 Flyway 风格升级件，含升级说明/升级操作/回滚）；支持存量项目 init 接入（项目体检+项目画像 profile+规范路由，只读不回填）。全局规范在本 skill 的 standards/ 目录（代码规范分前端/后端、接口、数据库、git、版本）。触发词：新需求、新功能、开始做、开发功能、需求开发、做一下xxx功能、spec流程、继续功能、新建里程碑、纳入里程碑、冻结版本、汇总升级件、发版、初始化spec、spec init、接入spec机制、建基线。NOT for: 明显的单点 bug 修复（直接修）、单文件小改动、纯技术问答。"
---

# bryanchen-spec —— 四阶段规格开发流程

需求 → 方案 → 任务 → 实现，每阶段产物落盘、人工确认后才推进。
**核心信条：没有三重确认，不写一行生产代码；没有验证证据，不声称完成。**

## 0. 铁律（优先级最高，与其他条款冲突时以本节为准）

1. **三重确认门**：requirements.md、plan.md、tasks.md 三份文档的版本头必须全部为
   `状态: 已确认` 且确认人非空，才允许进入 Implement。缺任何一份 → 明确告知缺哪份，停住。
2. **agent 不得代确认**：确认人名字必须由用户给出；只有用户明确说「确认/通过/OK」才可写入。
3. **生产代码保护**：三重确认之前，只允许写 `specs/` 下的文档，禁止创建/修改任何源码文件、
   禁止升级依赖、禁止改 CI/构建配置。
4. **确认后改内容 = 确认作废**：已确认文档被修改后，版本头改回 `状态: 待重确认`，
   版本按规则 bump，须重新走确认。
5. **诚实性**：不得声称「测试通过/验证通过/完成」除非贴出真实命令输出。
   lint/build 通过只是兜底，不是行为验证。无法验证时明说原因。
6. **中途发现问题就停**：Implement 期间发现需求/设计缺陷 → 停止编码 → 回改对应文档 →
   版本 bump → 重新确认 → 再继续。禁止「先写了再说」。
7. **铁律不受规范源覆盖**：本节是流程纪律，不是技术规范。任何项目规范
   （AGENTS.md、规范类 skill、.specrc.yml 声明的源）都不得豁免 1~6 条。
   技术规范冲突按 .specrc.yml 路由裁决（见 §8），流程纪律没有裁决空间。

## 1. 触发与初始化（Phase 0）

用户消息含「新需求 / 新功能 / 开始做 / 开发功能 / 需求开发」等意图时启动。

1. 从需求提炼功能名（小写连字符，如 `add-member-discount`）；提炼不出或需求太模糊 → 先追问，不臆测。
2. 检查 `specs/` 下是否已有同名/同主题目录：
   - 有 → 问用户是「继续做」（走 §7 续传）还是「新建」（换名或确认覆盖）。
3. 创建目录与四个文件（模板见 `references/templates.md`）：

```
specs/{YYYYMMDD}_{功能名}/
├── requirements.md    版本头 v0.1.0 | 状态: 草稿
├── plan.md            版本头 v0.1.0 | 状态: 草稿
├── tasks.md           版本头 v0.1.0 | 状态: 草稿
└── changelog.md       记录 v0.1.0 创建
```

4. **规范源解析（仅项目首次触发时执行一次）**：
   - 项目根已有 `.specrc.yml` → 直接读取使用，**不再探测、不再询问**。
   - 没有 → 按 `references/standards-routing.md` 的探测顺序生成草稿
     （探测项目 AGENTS.md / docs/conventions/ / catalog 里的规范类 skill / 技术栈），
     展示给用户确认（可改任何一行）→ 写入项目根 `.specrc.yml` → 建议提交进 git（团队共享）。
   - 之后所有阶段加载规范时，一律按此表路由，不再自行猜测。

5. 输出启动摘要：功能名、目录路径、规范源（一行概括，如「code/api/db → skill:code-standards，git/版本 → global」）、「进入 Phase 1: Specify」。

## 2. Phase 1 — Specify（requirements.md）

写之前先做：读 `specs/_project/profile.md`（项目画像，存在时必读——技术栈/命令/既有约定/技术债/测试基线都在里面）、项目 README/AGENTS.md、看相关模块现状，不要求用户重复可查证的事实。profile 与现实不符时顺手更新 profile 并在回复中说明（不算 spec 变更）。

内容要求（完整模板见 references/templates.md）：
- **背景与目标**：为什么做，成功长什么样
- **需求条款**：`R-01` 起编号，**编号永久不复用**（删除标 `[已删除 vX.Y.Z]`）
- **EARS 句式**（强制）：`WHEN/IF/WHERE/WHILE <触发条件>, 系统 SHALL <可观察行为>`
  - ❌「系统应该很快」 ✅「WHEN 发起查询请求, 系统 SHALL 在 95% 的请求中于 500ms 内返回」
  - 需求只写「做什么」，禁止实现细节（库名/框架/算法参数 → 留给 plan.md）
- **验收场景**：每条 R 至少 1 个场景（GIVEN/WHEN/THEN），重要需求覆盖正常 + 异常/边界
- **Non-goals（范围外）**：明确不做什么，与做什么同等重要
- **假设显式列出**：`## 我正在做的假设` 一节逐条列出，结尾写「现在纠正，否则按此执行」
- **待确认问题**：阻塞性问题列在回复末尾「需确认后再继续」；非阻塞的记为假设

**门控**：展示全文 → 等用户回复「确认」→ 版本头改
`v1.0.0 | 状态: 已确认 | 确认人: <用户给的名字> | 确认日期: <今天>` → changelog 追加确认记录 → 进入 Phase 2。

## 3. Phase 2 — Plan（plan.md）

**先加载规范**（按 `.specrc.yml` 路由）：涉及接口 → `api-design` 领域的声明源；涉及库表 → `database` 领域的声明源（路由规则见 §8）。

内容要求：
- 采用方案 + 选择理由
- 涉及模块、数据流、接口与数据模型概要（遵守上述规范）
- **被拒绝的替代方案 + 拒绝理由**（每个关键决策必须有，防默默选了烂方案）
- 风险与规避
- 不复制 requirements 内容，只写 how

**门控**：同 Phase 1（确认② → 落盘 → 进 Phase 3）。

## 4. Phase 3 — Tasks（tasks.md）

**先加载规范**：`standards/versioning.md` 的编号规则节。

内容要求：
- `T-01` 起编号，按组划分（如 1.基础 / 2.核心 / 3.接入），编号永久不复用
- 每个任务必含五项：
  ```
  - [ ] T-03 <动词开头的具体描述>
    关联: R-01            ← 指回需求，每条 R 至少被一个 T 覆盖
    依赖: T-01, T-02      ← 只能指向更小编号，禁止循环
    验证方式: <测试/命令/人工步骤，lint/build 只能兜底不得为唯一>
    验收标准: <可判定的完成条件>
  ```
- 粒度：一个任务一次会话可完成、可独立验证与回滚；总数 3~20，超 20 → 建议拆需求
- 禁止占位任务（「待定」「TODO」「添加适当的错误处理」= 计划缺陷）
- **自检**：每条 R 都有 T 覆盖吗？有 T 找不到对应 R 吗（超范围）？

**门控**：确认③ → 落盘 → **三重确认自检**（读三份版本头，全部已确认+确认人非空）→
通过后执行 `git checkout -b feature/<功能名>`（细则见 standards/git-workflow.md）→ 进入 Phase 4。

## 5. Phase 4 — Implement

**开工前加载规范**（按 `.specrc.yml` 路由，必然加载）：`code-backend` / `code-frontend` 领域的声明源（按改动内容选一或都选）+ `git-workflow` 领域的 commit 节。

**规范裁决**：`.specrc.yml` 的 `project_files`（AGENTS.md 等）永远最高；其余按各领域声明的源执行；某领域声明为 `global` 时才读本 skill 的 standards/；声明 `none` 则跟随所在文件周边风格。冲突细则见 standards/README.md。

逐任务执行（按依赖序）：
1. 读任务 + 关联的 R 条款 + plan 相关节
2. 最小改动实现；注释解释「为什么」，单次使用的简单逻辑不抽象
3. 跑任务标注的验证方式，**保留真实输出**
4. 勾选 `- [x] T-xx`（勾选不升版本——进度不是内容）
5. commit：`<type>(<scope>): <中文描述≤50字>` + footer `Spec: specs/<目录> vX.Y.Z` 和 `Task: T-xx`
6. 每完成一组任务向用户简报：完成项、验证输出、下一步

全部任务完成后汇报：任务清单勾选状态、各项验证证据、是否满足合并条件
（合并流程见 standards/git-workflow.md §合并）。

**Implement 收尾附加两件事**（与汇报同轮完成）：
1. **升级件登记**：若本 spec 产生了库表变更或配置变更 → 创建/更新 `specs/{目录}/artifacts.md`
   登记（类型/摘要/来源任务/草案位置，格式见 references/milestone.md §四）。纯代码需求不创建。
2. **里程碑归属**：问一句「本需求纳入哪个里程碑（releases/vX.Y.Z）？可跳过」。
   用户指定 → 在对应 MILESTONE.md 表格登记；跳过 → 不阻塞任何事。

**发版时**：走里程碑流程（§9），项目根 CHANGELOG.md 条目从 MILESTONE.md 升级项表生成。

## 6. 版本号规则（摘要，细则必读 standards/versioning.md）

- 版本头格式：`> 版本: v1.0.0 | 状态: 已确认 | 更新: YYYY-MM-DD | 确认人: xxx`
- v0.x = 草稿期；三文档首次全确认 = v1.0.0
- MAJOR = 删需求/改范围/方向推翻（触发重审）；MINOR = 新增条款；PATCH = 措辞澄清
- 目录级统一版本：三个文档共用一个版本序列，changelog.md 集中记到编号级

## 7. 断点续传与异常处理

- 用户说「继续 <功能名>」→ 扫目录：定位第一个状态非「已确认」的文档从对应 Phase 续做；
  三份全确认 → 按 tasks.md 未勾选项继续 Implement；续做前先简报当前位置，等用户确认。
- 需求太模糊 → 追问澄清，不臆测生成。
- 用户要求跳过某阶段 → 说明风险，用户明确坚持才可跳，changelog 记录该决定及原因。
- 无法写 specs/（权限等）→ 告知并暂停。
- 目录已存在同名 → 见 §1.2，先问再动。

## 8. 规范加载规则（.specrc.yml 路由 + standards/ 索引）

**加载任何规范前先查项目根 `.specrc.yml`**：每个领域声明了什么源，就读什么源；
声明 `global`（或无 .specrc.yml 时的默认）才读下表的本 skill 内置文件。
路由语法、探测顺序、裁决细则、完整示例见 `references/standards-routing.md`。

| 领域键（.specrc.yml） | global 源（本 skill 内置） | 何时加载 |
|---|---|---|
| （索引与裁决规则） | standards/README.md | 首次使用本 skill 时 |
| code-backend | standards/code-style-backend.md | Implement 改后端代码前 |
| code-frontend | standards/code-style-frontend.md | Implement 改前端代码前 |
| api-design | standards/api-design.md | Plan/Implement 涉及接口时 |
| database | standards/database-design.md | Plan/Implement 涉及库表时 |
| git-workflow | standards/git-workflow.md | 开分支/commit/合并/发版时 |
| versioning | standards/versioning.md | 建目录/改文档/发版时 |

纪律：**按需加载单个领域的源，禁止一次性全读**；同一领域只读声明的那一个源（整文件替换，不叠加合并）。

## 9. 里程碑与发版（概要，细则必读 references/milestone.md）

多个需求汇总成一个大版本时启用；不启用里程碑的项目对本节零感知。

```
M0 立项   「新建里程碑 vX.Y.Z」 → releases/vX.Y.Z/ + MILESTONE.md
M1 挂接   「把 <spec> 纳入 vX.Y.Z」 → MILESTONE.md 表格登记（一个 spec 只属一个里程碑）
M2 冻结   「冻结 vX.Y.Z」 → 前置检查（所有 spec 已合并、任务全勾、证据齐）；
          冻结后新需求默认进下一版本，挤入需用户明确同意
M3 汇总   「汇总 vX.Y.Z」 → 收集各 spec 的 artifacts.md（git log 交叉核对防漏）
          → SQL 合并重排编号（Flyway 风格 V<版本>_<序号>__<描述>.sql + rollback 配对）
          → config/changes.md → RELEASE-NOTES.md（升级项从 R 条款聚合）
          → UPGRADE.md（部署顺序/SQL 顺序/配置/验证/回滚）
M4 发布   「发版 vX.Y.Z」 → checklist 人工逐项勾选（演练必须真做）→ git tag
          → 项目根 CHANGELOG.md 从 MILESTONE.md 生成 → releases/ 产物随 tag 进 main
```

铁律延伸：**M3 未汇总完不得进 M4；checklist 演练项未真做不得打 tag。**
升级件（SQL/配置）只在 M3 按版本整理，禁止单需求完成时私自往 releases/ 塞散件。

## 10. init —— 存量项目接入（概要，细则必读 references/init.md）

触发：「初始化 spec / spec init / 接入 spec 机制」。一次跑完约 10 分钟。

```
I1 安全快照    git 状态确认 + 将触碰路径的 sha256 快照
I2 项目体检    只读扫描 7 类事实（技术栈/模块/既有约定/规范skill/git现状/SQL目录/CI）
I3 测试基线    ⚠️ 默认不跑——先问用户「是否运行测试基线？」；
               跑 → 如实记录绿/红与既有失败清单；不跑 → profile 标注「基线未测」
I4 项目画像    生成 specs/_project/profile.md → 用户核对事实
I5 规范路由    生成 .specrc.yml 草稿（I2 发现直接喂入）→ 用户逐行确认
I6 骨架落地    建 specs/；AGENTS.md 无→写入 / 有→备份+追加（展示后确认）
I7 完成报告    装了什么、profile 在哪、建议的第一个 change、声明未碰任何源码
```

**init 铁律**：
1. **只读 + 只新增**——唯一触碰既有文件的是 AGENTS.md（备份+追加，先展示后写）；
   结束后用 I1 快照复验零破坏。
2. **不回填**——不把存量代码反推成 specs（官方与实测共识：back-fill 的 spec 会腐烂）。
   specs 只为将要改动的部分写。
3. **幂等**——重复跑 init 只刷新 profile 的事实与基线段；`.specrc.yml` 已存在则不动（手工改）。
4. **releases/ 延迟创建**——首次「新建里程碑」时才建。

**可选子流程 baseline-capture**（「给 <模块> 建 spec 基线」）：对高风险且即将大改的
单个模块捕获现状规格，一次只做一个，默认不建议——细则见 references/init.md §五。
