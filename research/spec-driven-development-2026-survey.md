# Spec-Driven Development / Spec Coding 主流方案机制对照（2026-10 核对）

> **核查方式与限制**：本次 `web_search` 不可用（provider `ddg` 未注册），全部结论来自 `web_fetch`/`curl` 直接抓取**官方仓库 README、官方文档站、官方文档的 Markdown 源**。凡「未核实」处均明确标注，未做推测填充。
> **官方 vs 社区**：文中标「官方」为项目自身仓库/文档陈述；标「社区」为第三方文章或社区 schema。
> **时效**：GitHub API 显示的 `pushed_at` 多在 2026-10-06~07，各项目均活跃；spec-kit `v1.1.1`、OpenSpec `v1.14.1` 为最新 release。

---

## 一、逐对象机制提取

### 1. GitHub Spec Kit（官方，140k★）

**独有机制**
- **入口与阶段解耦**：三个**互相独立**的入口，非强制串行——SDD（构建）/ bug 修复 / idea assessment。官方原文："These are independent entry points, not three mandatory phases"。
- **命令链**：`/speckit.constitution → specify → clarify → plan → checklist → tasks → analyze → implement → converge`（另有 `taskstoissues`）。
- **`converge` 收敛环（关键差分）**：评估代码 vs spec/plan/tasks，**append-only**——绝不改删代码，唯一可写动作是往 `tasks.md` 追加任务；输出二值结果 `Converged` / `Tasks appended`，循环 implement→converge 直到 Converged。
- **bug 扩展**：`specify extension add bug` → `/speckit-bug-assess → bug-fix → bug-test`，报告落在 `.specify/bugs/<slug>/`，终审 verdict 为 `verified | partial | failed`，官方明说"Missing verification is not a successful fix"。
- **assess 扩展**：`intake → research → define → shape → decide`，产物在 `.specify/assessments/<slug>/`，结论 `go / needs-clarification / kill`；**在无源码的空项目也能跑**。
- **扩展/preset/workflow/bundle 四层定制**；git 分支与 GitHub issue 同步已**移出核心**，变成 opt-in 扩展（`agent-context`、`git`、`github`、`selfest`…，见 `extensions/catalog.json`）。

**防漂移**：`converge` 增量收敛 + `analyze` 只读跨产物一致性分析 + `checklist` 作为"需求的单元测试"（`[x]` 表示**评审人**确认需求质量，`implement` 只读不写该标记，未勾选会询问后再继续）。`spec-persistence.md`（官方）明确三模型——Flow-back / Flow-forward / Living spec，并承认 Flow-back 的风险就是"silent divergence"。
**存量项目**：官方 `existing-projects.md` —— `specify init --here --force`，**不回填、不为既有行为反推 spec**，只从"下一个有界变更"开始；先巩固 baseline 分支再 init。
**并行/多人**：`tasks` 标 `[P]` 并行标记并给安全并行组；`taskstoissues`（或 github 扩展）转 issue 分派；spec 可评审、可分支、可合并。
**强制力**：**纯提示词 + 模板约束**，无 validate 命令、无 CI 强制。官方模板靠 `[NEEDS CLARIFICATION]` 标记、Phase -1 门（Simplicity / Anti-Abstraction / Integration-First Gate）、"≤3 projects"、"No speculative features"、文件创建顺序 contract→integration→e2e→unit 等来约束模型。
**需求质量规则**：**不用 EARS**（未在官方文档中出现），用"用户故事 + 验收标准 + `checklists/requirements.md` 内建质量清单"；宪法九条（Library-First / CLI Mandate / Test-First / 项目自定义 IV-VI / Simplicity / Anti-Abstraction / Integration-First）。

### 2. OpenSpec（Fission-AI，官方，71k★）

**独有机制**
- **Delta specs**：`## ADDED / MODIFIED / REMOVED Requirements` 描述相对变更，而非重述全量 spec；**archive 时语义合并进 `openspec/specs/` 主 spec**，change 目录移到 `changes/archive/<date>-<slug>/`。这是 brownfield 的一等公民设计。
- **schema 作为工作流依赖图**：`openspec/schemas/<name>/schema.yaml` 声明 artifact 的 `requires`，`openspec schema fork|init|validate|which`；官方强调"**dependencies are enablers, not gates**"。
- **config.yaml**：`context`（注入所有 artifact 提示）、`rules`（**仅**注入匹配 artifact）、`operations.apply/archive.guidance`（**advisory**，官方明说"Neither field is an enforceable check"）；`openspec instructions apply|archive --json` 在执行时取新鲜快照。
- **Stores（beta）**：`openspec/` 可独立成仓库，`--store <id>` 让跨仓库 feature 共享一份规划；"platform team 拥有 specs，product team 只读引用"。
- 并行：**"You can work on multiple changes in parallel without conflicts"**——不同 requirement 的 delta 不会冲突。
- 命令两档 profile：默认 `/opsx:propose`（+explore），扩展档 `/opsx:new / continue / ff / verify / bulk-archive / onboard`。

**防漂移**：delta→archive 的强制合并路径 + `/opsx:verify`（扩展档）+ archive 前读取 specs rules 快照，JSON 无效**即中止写入**（官方明确是 fail-stop 语义）。
**存量项目**：`docs/existing-projects.md`；philosophy 首条即 "built for brownfield not just greenfield"。
**强制力**：schema `validate` 只管结构（语法/模板存在/无环）；**内容不强制**。官方对社区 schema `anvil` 的描述赤裸承认："OpenSpec only checks that artifacts exist, so enforce the gate with your own CI or hook"。
**需求质量**：RFC 2119 关键词（SHALL/MUST/SHOULD/MAY）+ Requirement/Scenario 结构 + Given/When/Then；**Lite / Full 两档 rigor**（渐进严格度）。

### 3. Amazon Kiro（官方）

**独有机制**
- 三件套 `requirements.md / design.md / tasks.md`；**EARS 记法**（官方原文 `WHEN [condition/event] THE SYSTEM SHALL [expected behavior]`），官方给出的四条收益：Clarity / Testability / **Traceability** / Completeness。
- **Bugfix Specs**：不写 requirements 而写 `bugfix.md`，含三段强制结构——Current Behavior(Defect)、Expected Behavior、**Unchanged Behavior（`SHALL CONTINUE TO`，回归防护）**。
- **Steering 四种 inclusion mode**（官方）：`always`（默认）/ `fileMatch`（glob 匹配才载入）/ `manual`（`#name` 或 slash 唤起）/ `auto`（按 `description` 语义匹配，类似 skill）；作用域 workspace `.kiro/steering/`、global `~/.kiro/steering/`（可团队/企业通过 MDM 分发），冲突时 **workspace 覆盖 global**。内置 `product.md / tech.md / structure.md`。支持 `#[[file:path:line]]` **引用活文件**保持 steering 不过期。
- **Hooks**：`.kiro/hooks/<id>.json`，trigger + matcher(regex) + action（`command` 走 shell、STDIN 收 JSON 上下文；或 `agent` 注入 prompt）。官方列举用途：改文件后自动 lint/format/typecheck、**PreToolUse 门禁危险操作**、生成配套测试/文档、提交前校验。
- **Correctness / 属性测试（PBT）**：把 EARS 需求转成**全称属性**，生成成百上千随机输入去找反例，官方定位为"从检查个例到验证整个输入空间"；EARS↔PBT 是官方点名的映射关系。
- **并行执行**：跑全部 task 时 Kiro 对 `tasks.md` 建依赖图，分 **wave**：无依赖任务同 wave 并发，wave 间串行。
- Quick Spec（跳过审批门一次生成三件套）、Plan mode、Analyze Requirements（查逻辑矛盾/歧义/冲突/缺口）、Design-First 与 Requirements-First 双变体。

**防漂移**：task 追溯回 requirement 编号 + Bugfix 的 Unchanged Behavior + hooks 在文件/工具事件上做确定性门禁。
**存量项目**：官方有 brownfield 定位；**未核实**是否有专门的存量迁移流程文档。
**强制力**：**有**——hooks 是可执行的 shell/门禁，这是全表中最接近"强制"的机制（其余多为提示词）。

### 4. BMAD-METHOD（官方，53k★）

**独有机制**
- **命名 agent + 菜单码**：`bmad-agent-analyst/pm/architect/dev/ux-designer`，码如 `BD`(Build)、`QA`、`CR`(Code Review)、`ER`(Epic Retrospective)、`TK`(Ticket)、`PRD`、`CA`(Correct Course)、`PC`(Project Context)。**同一码在不同 agent 下含义不同**（`CR` 对 Analyst 是竞品拆解，对 Dev 是 code review）。
- **`bmad-spec` 作为"实现读取的契约"**，产物 `spec-<slug>.md`；**PRD 不替代 spec**，官方原文"every epic still ends up as a spec-<slug>.md that Build reads"。
- **`bmad-ticket` 票树**：`tickets.toml` 分层（initiative → epic → entry，稳定 id），`backlog/` 放独立故事与 bug；plan 落在 `story-<slug>-plan.md`，**记录 `baseline_revision`**，状态与 tracker 状态分离。
- **三道 review lens**（官方点名）：Blind Hunter（随便找 10 个要修的点）、Edge Cases Hunter（被遗忘的角落）、Verification Gap Finder（这被测试覆盖了吗）；review 可 patch / 退回 plan 或 clarify / void / defer 到 `deferred_work.md`。
- `bmad-prfaq`（Amazon Working Backwards 挑战）、`bmad-advanced-elicitation`（命名推理法二次审视自己的输出）、`bmad-correct-course`（需求/架构重大变更时，需 PRD）、`bmad-build-auto`（每 ticket 一次调用，**自己不挑下一个 ticket**）、`bmad-loop`/Epic Retrospective。

**防漂移**：build 先调查仓库并**写下"复用什么、不要改什么"**再动手；review 读 plan + `baseline_revision` 做基线对比；`bmad-spec` 契约定位。
**存量项目**：官方 `existing-codebases/start-in-an-existing-codebase` —— **"大多数关于应用的知识已编码在源码里"，要抑制喂文本描述**，原始 greenfield PRD 归档且"小改动时 agent 不该偶然翻到"；`bmad-project-context` 把**已验证**的小段项目上下文写进 `AGENTS.md`，有则跳过。
**强制力**：提示词 + ticket/plan 状态机（`built` / `done` / `review`），无独立 validate 命令。
**需求质量**：`[ASSUMPTION]` 标签（fast path）+ PRFAQ 质询 + "done-when checks" 信封；**不使用 EARS**（未在官方页面出现）。

### 5. Tessl（官方）—— 重要发现：已转型

- **现状（2026-10）**：Tessl 公开产品是 **Registry & package manager + Governance + Evals + Observability + Context/Findings**。核心单位是 **Rule / Skill / Plugin**（"Context as software"，版本化、可 eval、可回滚）。
  - **Verifiers**：`verifiers/*.json` 存"仓库级不变量"，`tessl.json` 的 `verify.groups` 定 include/exclude 与 **level: warn|error**；`tessl change verify lint/--dry-run/--all/--sample`；可设 CI **阻塞检查**。
  - **Evals**：`tessl scenario generate` → `tessl eval run`，**默认跑两遍（有 skill / 无 skill）比分数差**，声称"skill 的价值 = 分数差"；场景 feasibility check 后才保存，可当回归测试。
  - **自动漂移检测**：官方 automations 里含 **docs-audit**（"检查文档是否仍与代码一致，漂移就开 PR"）、review-miner（把反复出现的 review 意见转成 lint 规则）、release-check。
- **历史 spec-as-source（社区核实，Fowler 2025-10）**：Tessl Framework（当时 private beta，1:1 spec↔code 文件映射，生成代码顶部写 `// GENERATED FROM SPEC - DO NOT EDIT`，`@generate`/`@test` 标签，`tessl build` 生成、`tessl document --code` **从既有代码反向工程出 spec**）。Fowler 逐字实测："Even at this low abstraction level I have seen the non-determinism in action… generating code multiple times from the same spec"。
- **对用户预期的重要修正**：当前 docs.tessl.io（104 条索引）**已看不到 spec-as-source / spec↔code 双向校验的产品文档**；官方博客仍有《How Tessl's Products Pioneer Spec-Driven Development》，其 SDD 表述是 **Plans + Specs + Tests 三类资源**，而非 spec 编译成码。**"Tessl 双向往返校验"这一点：旧路线有社区实证，现行产品文档未核实。**

### 6. cc-sdd / kiro-sdd 类第三方实现

- **gotalab/cc-sdd**（官方 README，3.7k★，最近提交 2026-09-23）：17 个 skill × 8 个 agent host。**明确 Kiro-inspired，Kiro 既有 spec 兼容可迁移**。
  - 入口 `/kiro-discovery` **路由**：扩展既有 spec / 直接实现（无 spec）/ 建一个新 spec / 拆成多 spec / 混合；产出 `brief.md`（+`roadmap.md`）。这解决"Kiro 只有一条路径"的批评。
  - **Boundary-first**：`design.md` 含 **File Structure Plan**，task 带 `_Boundary:_` / `_Depends:_` 注解，review/validation **专查越界**。
  - `/kiro-impl` 长时自主：每 task fresh implementer + **TDD(RED→GREEN) feature flag** + **独立 reviewer + 自动 debug**；无 native subagent 的 host 降级为 inline；经验通过 `tasks.md` 的 `## Implementation Notes` 传播；记录 task 状态以支持**断点续跑**。
  - `/kiro-spec-batch`：roadmap 按依赖波次拆多 spec 并行，**跨 spec review** 抓矛盾/职责重复/接口不匹配。
  - 与 Kiro 的**关键立场差异**（官方 philosophy）："Code remains the source of truth"——spec 是部件之间的**契约**，不是交给 agent 的主控文档。
- **kiro-style-sdd**（79★，2026-05）、**kspec**（22★，2026-09，Kiro CLI 的 SDD 框架）、**scartill-sdd-lite**（Kiro CLI-first 轻量）为同类第三方；未见有项目取名 `kiro-sdd` 且具规模（**未核实**存在权威 "kiro-sdd" 项目）。

### 7. Agent OS（buildermethods，官方 README，5.5k★，pushed 2026-10-07）

- 四项能力：**Discover Standards**（从代码库抽取模式与约定成 standard 文档）/ **Deploy Standards**（按当前任务**智能注入相关 standards**）/ Shape Spec / Index Standards。定位是"注入标准 + 写出更好的 spec"，README 极简，细节全在站点 `buildermethods.com/agent-os`（`llms.txt` 404，未取得全文）。**具体文件布局与命令未核实**。
- 与 Kiro `fileMatch`、Tessl Rules、spec-kit `agent-context` 扩展属于**同一机制族：上下文/标准的按需注入**。

### 8. addyosmani/agent-skills 的 spec-driven-development（官方 SKILL.md，102k★）

- **四阶段门控 + Phase 0 例外**：`SPECIFY → PLAN → TASKS → IMPLEMENT`，每阶段结束时 **Human reviews**；**"Stop after writing the spec (CRITICAL). STOP YOUR TURN IMMEDIATELY."**——不允许同一轮里写 spec 又开工。
- **Phase 0 capability map**：当单个需求捆了多个**可独立测试**的能力时，先出模块表（`Module id / Responsibility / Depends on`）+ 构建顺序，**人类批准后才写任何 module spec**；module id 稳定不重命名，spec 命名为 `SPEC-<id>.md`。
- **Spec 六要素**：Objective / Commands（**完整可执行命令而非工具名**）/ Project Structure / Code Style（**一个真实代码片段胜过三段描述**）/ Testing Strategy / **Boundaries 三层（Always / Ask first / Never）**。
- **先surface假设**：`ASSUMPTIONS I'M MAKING: 1..4 → Correct me now or I'll proceed`。
- **把模糊指令改写成成功标准**：`"Make the dashboard faster"` → `LCP < 2.5s on 4G / 初始数据 < 500ms / CLS < 0.1 → Are these the right targets?`。
- **反合理化表（Rationalizations）**：逐条反驳"这很简单不需要 spec""我编码完再补 spec""需求反正会变"等 7 种借口 + Red Flags 清单 + 8 项 Verification 勾选。
- 与外部工具**共存而非重复**：若项目已用 OpenSpec，保留其产物格式，"This skill owns the clarification, content, and approval gates; the external tool owns how the approved spec is represented"。

### 9. mattpocock 的 to-spec / to-tickets（官方 SKILL.md，278k★）

- 链路：`setup-matt-pocock-skills`（一次性配置 **issue tracker / triage 标签词汇 / 领域文档位置**）→ `to-spec` → `to-tickets` → `implement-spec`。
- **`to-spec` 不访谈**："Do NOT interview the user; just synthesize what you already know"——把当前对话合成 spec。模板：Problem Statement / Solution / **User Stories（要求"extremely extensive"长编号列表）** / Implementation Decisions（**禁止写具体文件路径与代码片段**，例外是原型里能精确编码决策的状态机/reducer/schema/type） / Testing Decisions（含**先例 prior art**） / Out of Scope / Further Notes。发布到 tracker 并打 `ready-for-agent` 标签。
- **`to-tickets` 的 seam + 垂直切片**：先**设计测试接缝（seams）**，"优先用既有 seam、用最高的 seam、全代码库 seam 越少越好，理想是 1 个"，**需用户确认 seam 才对**；再切 **tracer bullet**——每片**垂直贯穿所有层**（schema/API/UI/tests）、可独立演示、**能装进一个全新 context window**；每张 ticket 显式声明 **blocking edges**，无阻塞者可立即开工。
- **Wide refactor 例外**：机械式大范围改名/改类型不能垂直切片，改用 **expand–contract**（先并存，再分批迁移且每批保持 CI 绿，最后删除旧形态），极端情况共享 integration branch，绿只承诺在最终 integrate-and-verify。
- **`implement-spec`**：目标是在**单一 integration branch** 上把整个 spec 按 ticket 依赖序做完。
- **词汇纪律**：`codebase-design` 提供 deep module 词汇表（Module / Interface / Implementation / Depth / **Seam** / Adapter / Leverage / Locality），并明说"不要用 component、service、API、boundary 替代"——这直接服务于 seam-based testing。

### 10. 强调验证 / 追溯 / ADR / TDD / 多 agent 评审的主流实践

- **Anvil（社区 schema，OpenSpec 生态）**：`proposal → specs → design → **review** → **test-plan** → tasks → apply → verify`。`review` 由 **fresh-context 只读 reviewer（可用第二个模型）** 写，输出 `VERDICT:` 行用于门控后续阶段；**OpenSpec 只检查 artifact 是否存在，门控需自带 CI/hook**；`test-plan` 把**每个 spec scenario 映射到一个具名测试**，并兼作 red/green 账本供 `verify` 审计。
- **intent-driven（社区 schema）**：把 ADR 做进流程——change-local ADR review manifest，合格的长生命周期决策写成**不可变、可 supersede 的 ADR**。
- **e2e-runbooks（社区 schema）**：能力级 E2E 运行手册，断言**只允许可观察行为**（HTTP 状态、响应体、持久化状态，"never log substrings"），每次运行记录 UTC 起止、时长、token 估算。
- **BMAD Test Architect (TEA)** 独立模块 + `bmad-qa-generate-e2e-tests`。
- **VSDD（社区 gist，HN 211pts/118 评论，2026-02）**：SDD × TDD × VDD 三闸串联，角色分工 = Architect(人) / Builder(LLM) / **Tracker = Chainlink（Epic→Issue→bead 层级分解，每个 spec、测试、实现都映射到 bead = 追溯）** / **Adversary = 超挑剔评审者，fresh context 每一轮**；包含"Purity Boundary Map"（纯核心 vs 副作用外壳）与形式化验证工具选型（Kani/CBMC/Dafny/TLA+）作为**架构约束**。

---

## 二、总表：机制 × 方案

图例：`●` 官方明说且为主要机制 ｜ `○` 存在但可选/扩展/间接 ｜ `—` 无或未核实

| 机制维度 | Spec Kit | OpenSpec | Kiro | BMAD | Tessl(2026) | cc-sdd | Agent OS | addyosmani | mattpocock | **自制流程易缺** |
|---|---|---|---|---|---|---|---|---|---|---|
| 项目级"宪法/标准"常驻上下文 | ● constitution | ● config.yaml context | ● steering(4 模式) | ● project-context→AGENTS.md | ● Rules | ● steering | ● standards | ○ 六要素之 Code Style | ○ GLOSSARY/ADR | **是** |
| 阶段顺序 + 人工审批门 | ● (clarify/checklist) | — (反对硬门) | ● 三阶段确认 | ● plan 审批 | ● plan 可编辑 | ● phase gates | — | ● 四阶段门控 | ● seam/breakdown 确认 | **是** |
| 需求语法/质量规则 | ○ 模板+checklist | ● RFC2119+Scenario | ● **EARS** | ○ PRFAQ+[ASSUMPTION] | ○ | ● EARS 兼容 | — | ● 六要素+Boundaries | ● 用户故事清单 | **是** |
| 设计文档/ADR/RFC | ○ plan.md | ○ design.md | ● design.md | ● 架构 spine | ○ | ● design.md+File Structure Plan | — | ○ Plan 阶段 | ● ADR 感知 | **是** |
| 追溯（需求↔任务↔测试↔代码） | ● analyze/converge | ● delta→archive | ● task 回指需求号 + PBT | ● baseline_revision+票树 | ○ verifier/coverage | ● _Boundary_/_Depends_ | — | ○ spec↔PR 链接 | ● seam+blocking edges | **是** |
| 存量/brownfield 明确路径 | ● `init --here`，不回填 | ● delta-first 哲学 | ○ 定位有，流程未核实 | ● "知识在源码里"，抑制喂文档 | ○ 可从代码反向文档 | ● steering→discovery | ○ 从代码抽 standards | ○ 提到外部工具优先 | ● 先探索 repo/ADR | **是** |
| 并行/多人协作 | ● `[P]`+issue | ● 多 change 并存+Stores | ● wave 依赖图并发 | ● 票树/跨仓库 store | ○ 组织级 workspace | ● 多 spec 波次+跨 spec review | — | ○ capability map | ● blocking edges+integration branch | **是** |
| 自动化校验/强制力 | — 纯提示词 | ○ `schema validate`（仅结构） | ● **hooks** 可执行门禁 | ○ ticket/plan 状态机 | ● **CI verifier + eval** | ○ 依赖 host | — | — 纯提示词 | ○ 靠 tracker | **是**（多数方案都缺，全靠约定） |
| 评测/Evals | — | — | ● PBT correctness | ○ TEA/QA 生成 | ● **有/无 skill 分数差** | ○ TDD 红绿 | — | — | ○ tdd skill | **是** |
| 多 agent 独立评审 | ○ analyze 只读 | ○ anvil 社区 | ○ analyze requirements | ● 三角色盲点评审 | ● code review lenses | ● 独立 reviewer+auto-debug | — | — | — | **是** |
| 测试接缝 / 垂直切片 | — | — | — | ○ story 切片 | — | ● 边界优先 | — | ● 能力地图 | ● **seam+tracer bullet** | **是** |
| 失败/回退语义 | ● bug verdict，缺验证不算修复 | ● archive fail-stop | ● Unchanged Behavior | ● void/defer/reject | ● level warn→error 渐进 | ● 自动 debug 重试 | — | ● 反合理化表 | ● expand–contract | **是** |

**公认必备项判定**（≥4 个主流方案以 `●` 或官方主机制实现，且自制流程最容易漏）：①常驻项目标准；②显式阶段门 + 人工审批；③需求质量规则（可测/验收标准）；④追溯链；⑤存量项目的有界起步策略；⑥并行协作的显式依赖声明；⑦独立的验证/评审环节（含测试接缝或 evals）。
**仍未形成共识的**：强制力。除 Kiro hooks 与 Tessl CI verifier 外，**所有方案本质都是提示词约定**；OpenSpec 官方直接承认自己的校验只看"artifact 是否存在"。

---

## 三、已知批评与失效模式（社区，非官方）

主来源：[Marmelab《Spec-Driven Development: The Waterfall Strikes Back》](https://marmelab.com/blog/2025/11/12/spec-driven-development-waterfall-strikes-back.html)（HN 225pts/191 评论）与 [Fowler《Understanding SDD: Kiro, spec-kit, and Tessl》](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)（HN 128pts）。

1. **Context blindness**：agent 仍靠文本搜索找上下文，常漏掉"需要改的既有函数"→ 重造轮子。Fowler 亲历：spec-kit 做了研究并写下"这些是既有类的描述"，agent 仍把它们当新 spec 重新生成，**产生重复实现**。
2. **Markdown madness**：一个小功能产出 8 文件 1300 行；开发者 80% 时间在读 Markdown 而非思考；**双份 code review**（技术 spec 里已含代码，实现后还得再 review 一遍）。
3. **Sledgehammer**：Kiro 修一个小 bug 被扩成 4 个"user story"、16 条验收标准；Fowler 对两者都判断"对多数真实规模的问题是过重"。
4. **False sense of security**：agent 把"verify implementation"任务勾完成却没写任何单测（Marmelab 实例）；Fowler 同时观察到**忽略指令**与**过度遵令**两种失效（被某条宪法条款带跑偏）。
5. **Brownfield 最弱**：Marmelab 断言"对大型既有代码库，SDD 基本不可用"；Fowler 说两个工具的存量引入成本更高，因此"更难评估其在 brownfield 的价值"。
6. **spec 生命周期定义混乱**：Fowler 指出 spec-kit 每个 spec 建一个分支，暗示其只把 spec 当"一次变更请求的生命"，属于 **spec-first 而非 spec-anchored**（官方 `spec-persistence.md` 现承认不强制任何模型，把选择权交团队）。
7. **非确定性**：同一 spec 多次生成代码结果不同——Tessl spec-as-source 实测。这也是 spec-as-source 概念在现行产品里退场的原因之一（推断，非官方声明）。

---

## 四、如果我方要补齐（结论性建议，非官方）

对照本工作区的自制四阶段流程，缺口按优先级：
1. **spec↔code 收敛环**（对应 `converge`）：需要 append-only 的"实现后对账"步骤，只往任务清单追加缺口，反复跑到收敛，否则纯粹依赖人肉 review。
2. **需求→测试的具名映射**（对应 anvil `test-plan`、Kiro PBT）：每个 scenario 必须点名一个测试，并可红/绿记账。
3. **显式依赖边**（对应 `[P]`、wave、blocking edges）：并行分支/工单要有声明式 blocked-by，而非口头约定。
4. **可执行的强制点**（对应 hooks/CI verifier）：至少把 lint/typecheck/单测挂到"文件保存后"与"提交前"，把提示词约定升级为确定性门禁。
5. **独立评审者**（fresh context 的只读 reviewer + VERDICT 门控）：自查不算评审。
6. **存量项目的有界起步**（对应 `--here` + `converge`）：只对"下一个有界变更"写 spec，**不为既有行为反推全量 spec**——所有主流方案的官方立场在此一致。
