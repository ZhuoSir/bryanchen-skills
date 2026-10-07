# 里程碑与发版管理（releases/）

解决一个问题：**多个需求（spec）汇总成一个大版本时，升级项、升级说明、升级操作、SQL、配置
按版本聚合成一套可查、可执行、可回滚的交付物**——不是一个需求散一份。

三层版本模型：**spec 版本**管单需求文档演进（standards/versioning.md）；
**里程碑**管发版交付（本文件）；**git tag** 管代码快照（standards/git-workflow.md）。

---

## 一、目录结构（规矩固定，所有版本一致）

```
releases/v1.3.0/
├── MILESTONE.md          清单：纳入的 spec、状态、升级项、目标日期、汇总进度
├── RELEASE-NOTES.md      升级说明（用户/运维视角：新增/变更/已知问题）
├── UPGRADE.md            升级操作手册（部署顺序、SQL 执行顺序、配置变更、验证、回滚）
├── checklist.md          发版检查单（含演练项，人工逐项勾选）
├── sql/
│   ├── V1.3.0_01__member_discount_ddl.sql      ← Flyway 风格：版本号_两位序号__描述
│   ├── V1.3.0_02__member_discount_dml.sql
│   └── rollback/
│       ├── R1.3.0_02__member_discount_dml.sql  ← 同名逆序，R 前缀
│       └── R1.3.0_01__member_discount_ddl.sql
└── config/
    └── changes.md        配置变更汇总（dataId/文件、key、旧值→新值、来源 spec）
```

模板见 `references/templates.md` 的 MILESTONE / RELEASE-NOTES / UPGRADE / artifacts 四节。

## 二、SQL 规范（Flyway 风格）

1. **命名**：`V<里程碑版本>_<两位执行序号>__<snake_case描述>.sql`，如 `V1.3.0_03__report_export_ddl.sql`。
   回滚脚本 `R<版本>_<同序号>__<同描述>.sql` 放 `sql/rollback/`，**与正向脚本一一配对**（无回滚意义的
   纯新增字典数据可豁免，但要在文件头注明「回滚: 不需要，原因: …」）。
2. **序号即执行顺序**：跨 spec 重排——建表先于改数据、前置字典/基础数据先于依赖它的 DML、
   同表变更合并相邻。序号在 M3 汇总时统一分配，**分配后不再变动**（新增插队用补号如 `_03a` 并在
   UPGRADE.md 说明，避免重排已评审的顺序）。
3. **文件头注释块（强制）**：
   ```sql
   -- ============================================
   -- 版本: v1.3.0  序号: 01  类型: DDL|DML
   -- 来源: specs/20260926_add-member-discount (T-02)
   -- 前置: 无 | V1.3.0_00__xxx.sql
   -- 可重入: 是（IF NOT EXISTS / WHERE NOT EXISTS）| 否（原因）
   -- 预估: <1s | 大表(约N行)需低峰执行
   -- 回滚: rollback/R1.3.0_01__member_discount_ddl.sql
   -- ============================================
   ```
4. **幂等优先**：DDL 用 `IF NOT EXISTS` / 存在性判断包裹；DML 用 `INSERT ... WHERE NOT EXISTS`
   / `INSERT IGNORE` / 带状态条件的 UPDATE。确实不可重入的，文件头显式标注并写进 UPGRADE.md 注意事项。
5. **大表变更**：标注行数量级与预估时长；百万行以上按 database-design 规范走 online DDL 工具或低峰窗口。
6. **冲突合并**：两个 spec 改同一张表/同一配置 key → M3 汇总时人工裁决合并为一条，
   文件头「来源」列出全部出处，MILESTONE.md 备注裁决理由。

## 三、配置变更规范

`config/changes.md` 表格逐条列：

```markdown
| # | 类型 | 位置(dataId/文件) | key | 旧值 | 新值 | 来源 spec | 需重启 |
|---|---|---|---|---|---|---|---|
| 1 | Nacos | bot-order-dev.yaml | member.discount.rate | （无） | 0.95 | add-member-discount | 否(热更) |
```

- 新增 key 旧值写「（无）」；删除 key 新值写「（删除）」
- 多环境差异（dev/test/prod 值不同）在「新值」列分环境写清
- 需要整文件的（如新 nginx conf 片段）放 `config/files/` 并在 changes.md 登记路径

## 四、artifacts.md 登记（spec 侧的轻量义务）

**仅当该 spec 的实现产生了库表变更或配置变更时**，在 `specs/{目录}/artifacts.md` 登记
（纯代码需求不创建此文件）：

```markdown
# 升级件登记
| 类型 | 内容摘要 | 来源任务 | 草案位置 |
|---|---|---|---|
| DDL | 新表 member_discount_log | T-02 | plan.md §数据模型 |
| 配置 | Nacos member.discount.rate=0.95 | T-03 | plan.md §依赖 |
```

登记时机：Implement 收尾汇报时一并完成（SKILL.md §5）。这是 M3 汇总的**防漏数据源**之一。

## 五、里程碑生命周期（M0~M4）

### M0 立项 —— 双触发：「新建里程碑 vX.Y.Z」口令，**或** spec 启动版本问询中
用户选择「新开」（SKILL.md §1 步骤3）
1. **双建**：`releases/vX.Y.Z/` 台账目录（MILESTONE.md 状态头「进行中」+ 纳入需求表 + 纳入缺陷表）
   + **裸号版本分支 `X.Y.Z`**（基点：上一版已合 main → main；上一版悬空 → 悬空分支 tip 链式切，
   台账记「基于」；细则 git-workflow §一）
2. 定号按 standards/versioning.md §二 决策表给建议；跳号需用户明确
3. 前置处置：台账有悬空账或未收口在途版 → 先走 SKILL.md §1.3 拦截清单，处置完才建
4. 更新版本台账 version.md：该版「在途」+ 分支字段
5. 铁律：两条触发路径都必须有用户明确选择；未获选择**目录与分支都不建**（含"顺手先建"）

### M1 挂接 —— 触发:「把 <spec> 纳入 vX.Y.Z」/「把 BUG-xx 纳入 vX.Y.Z」
1. MILESTONE.md 表格加一行（spec 目录、当前 spec 版本、状态、SQL/配置件数暂记 0）
2. 单个 spec 的 Implement 收尾时主动问一句「纳入哪个里程碑？可跳过」——不强制、不阻塞
3. 一个 spec 只属于一个里程碑；要移出去需用户明确说，两处 MILESTONE.md 都更新
4. **bug 挂接**：「把 BUG-xx 纳入 vX.Y.Z」→ bugs.md 该行状态翻「已规划(vX.Y.Z)」+
   MILESTONE.md 的 bug 表登记（细则 references/bugs.md §五）
5. spec 有 completion.md 经批准的「延期→本里程碑」项时，登记进表格备注

### M2 冻结 —— 触发:「冻结 vX.Y.Z」
前置检查（不满足则列出差距，不冻结）：
- [ ] 表格内所有 spec 状态 = 已合并（Implement 完成且 merge 进**版本分支**）
- [ ] 各 spec 的 tasks.md 全勾、验证证据齐；**未勾项必须已出现在 completion.md 中
      写明原因+处置（延期目标=本里程碑的除外，那属于规划缺陷应回 M1 修）**，且经用户批准
- [ ] 本里程碑「已规划(vX.Y.Z)」的 **P0/P1 bug 全部达「已验证」**（bugs.md 核对）
- [ ] **账证初对**：本版分支已合并提交中的 `Bug:` footer 全部能在 bugs.md 找到对应行
      且状态 ≥ 已修复——把「修了没记」消灭在冻结时，不留到 M4 收网才暴雷
- [ ] **无未合并并行分支**（并行版）：`git worktree list` 除主目录外为空——有活跃
      feature worktree = 还有碎片账未归并（全局账不完整），冻结阻断；确要带并行体冻结，
      先与用户逐个处置（转挂下版/加速收口）
- [ ] **无孤儿 spec**：`grep "挂载:" specs/*/changelog.md` 全部指向本里程碑或已明示转挂；
      存在「已动工/已完结但无挂载归属」的 spec 目录 = 冻结阻断（对账法同 M3 步骤 0）。
      冻结只查表不查目录，漏挂的 spec 会整版蒸发——这一步就是补那个洞
冻结后：MILESTONE.md 状态改「已冻结」；**新需求默认进下一里程碑**，要挤进本版本需用户明确同意
（挤入 = 解冻重走 M2，changelog 记录）。

### M3 汇总 —— 触发:「汇总 vX.Y.Z」/「整理升级件」

0. **里程碑审计（第一动作，双向：spec 挂接 + 汇总进度；MILESTONE 表不可自证，勾选必须是事实推导出来的函数）**：
   ```bash
   # A = 本版分支实际带出的 spec（commit footer 为硬锚）
   git log <上一版tag>..X.Y.Z --grep "Spec:" \
     --format="%(trailers:key=Spec,valueonly)" | sort -u
   # B = 全部 spec 的挂载事实（spec 目录 changelog 的「挂载:」行，§1.3 启动时写入）
   grep -H "挂载:" specs/*/changelog.md
   ```
   对账 A∪B(活跃未完结的) 与 MILESTONE 纳入需求表：
   - **有实无表 = 漏挂** → 当场问用户处置：纳入本版（若内容确已合入本版分支，必须补表并
     继续 M3，否则升级件必然缺失）/ 转挂下版（注明原因）
   - **有表无实 = 空行** → 问：挂起（spec 未开工）还是作废
   - **B 中归属与 A 冲突**（如 spec 挂 v1.4.0 但提交进了 1.4.1 分支）→ 停，向用户报异常，
     以提交实际落点为准改表
   **进度重算**（同一步骤内完成）：对「汇总进度」逐项跑事实判据（见 §五附·审计判据表），
   有实无勾→补勾并报告；有勾无实→**假勾，红字硬阻断**；结果连同挂接对账一起写入
   MILESTONE 变更记录——**账不平不进后续步骤**。
1. **收集升级件**：逐 spec 读 artifacts.md；无 artifacts.md 的 spec 用
   `git log --grep "Spec: specs/<目录>"` 扫 commit + 读 plan.md 数据模型/配置节，交叉核对防漏
1.5 **并行预检（存在并行 spec 时必做）**：跑预检脚本（merge-base 文件集 ∩ ＋枚举
   value diff ＋SQL 序号 diff；skill 模板→项目 `verify/precheck.sh`）→ 冲突清单为零
   或已有 SHARED 仲裁记录才继续；SQL 序号在此统一分配（空间凭证的 M3 兑现点）
2. **整理 SQL**：合并同表变更 → 按依赖重排 → 分配序号 → 写文件头注释块 → 配 rollback
3. **整理配置**：汇总进 config/changes.md
4. **生成 RELEASE-NOTES.md**：升级项从各 spec 的 R 条款聚合（对外口径，去掉内部细节）；
   **「## 修复」节从 bugs.md 过滤「修复版本=本版本」生成**，不靠回忆
5. **编写 UPGRADE.md**：部署顺序（服务依赖序）、SQL 执行顺序（=序号序）、配置变更步骤、
   每步验证方法、整体回滚步骤（逆序）
6. **更新 MILESTONE.md** 汇总进度勾选与件数

### M4 发布 —— 触发:「发版 vX.Y.Z」
**总原则：所有落账在 tag 之前；tag 后修账 = 事故（证明打点顺序错了），必须记 MILESTONE
审计节并回炉流程。账不齐，tag 不打。**

0. **自动里程碑审计（基线，发版口令一到即跑）**：挂接+进度双向，假勾/漏挂 = 硬阻断处置完才继续
1. `checklist.md` 人工逐项勾选（**演练必须真做**；演练踩的过程坑当场记 lessons.md）
2. **变更↔断言配对核验**：本版每个触碰共享面的变更，回归载体有对应断言并列入 checklist；无配对 = 不过
3. **发版落账批处理（tag 前！一次写全，不许分批发散写）**：
   - bugs.md 本版「已验证」→「已发布(vX.Y.Z)+日期」
   - backlog.md 本版「已立项」spec 对应行翻「已交付(vX.Y.Z)」去向补全
   - MILESTONE：每个纳入 spec 状态列翻**终态「已发布(vX.Y.Z)」**（生命周期终点，
     禁止停在「已合并」中间态）＋纳入缺陷表终态＋状态头「已发布」＋汇总进度全勾
   - version.md 翻「已发版」；项目根 CHANGELOG.md 条目（来源 = MILESTONE 升级项表）
   - RELEASE-NOTES/UPGRADE 注明「部署基线 = tag vX.Y.Z」
4. **四步核验（tag 硬门，全过才许打）**：
   a) **逐条 grep 回验＋表格闸**：步骤 3 每一项落账在文件里 grep 到才算数（治 L-01 静默脱靶——
      写了 commit message 不等于改了文件，账目以文件为准）；本版全部被改过的 md 跑
      `scripts/mdtable_check.py` 退出码 0（落账改的多是表格行——错一格整表乱，必须机器过）
   b) **再跑一遍里程碑审计**：必须全绿（此时"进度"含步骤 3 的新账）
   c) **工作树干净**：`git status --porcelain` 为空；落账已 commit
   d) 三条齐绿 → 才进 5；任何一条不过 → 补账重验，**不许"先打了 tag 再修"**
5. **tag 打在版本分支的落账 tip 上**：`git checkout X.Y.Z && git tag -a vX.Y.Z -m "<摘要+spec清单>"`
   —— 此刻 tag 内容 = 账实一致的最终态，这是它作为历史凭证的资格
6. **问「合并到 main？」**（口令才动）→ merge --no-ff 后**即时验证**：
   `git diff vX.Y.Z main -- releases/vX.Y.Z/ specs/_project/version.md` **应为空**；
   非空 = 账滞后事故（tag 后还有账改），当场记审计节+回炉
7. **问「push？」** → 推后远端复核：`git ls-remote` 对齐 + `git show origin/main:<MILESTONE路径>`
   抽看终态确已在远端
8. 收口：悬空账（若用户选择不合 main 则挂账）；施工分支按用户示下去留

## 五附、里程碑审计判据表（勾选 = 从事实重算，不靠记忆）

| 勾选项 | 事实判据（可自动核） |
|---|---|
| spec 挂接表 | `git log <上一tag>..X.Y.Z --grep "Spec:"` footer 集合 ∪ `specs/*/changelog.md` 挂载行，对照 MILESTONE 纳入表（三态处置见 M3 步骤 0） |
| SQL 汇总编号 | `releases/vX.Y.Z/sql/V*.sql` 件数 == Σ 已挂 spec 的 artifacts SQL 行数；rollback/ 一一配对 |
| 配置汇总 | `config/changes.md` 存在且覆盖全部 artifacts 配置行 |
| RELEASE-NOTES | 文件存在且「包含需求」覆盖纳入表全部 spec |
| UPGRADE | 文件存在且执行序条数与 sql/ 件数一致、含回滚逆序节 |
| **演练** | **唯一不可推导项 → 强制留证字段**：MILESTONE「演练: 验证人/日期/结论」，空 = 不通过 |
| tag / 台账 | `git tag -l vX.Y.Z` 存在；version.md「最近已发」指向本版 |
| BL 互核 | backlog 三查：①「已立项/已交付」行去向列的 spec 目录与 MILESTONE 互点存在；②「**已交付但 MILESTONE 该 spec 未发布**」或「spec 已合并发布而 BL 仍待办/已立项」= 滞后行 → 报出纠正；③「待办」行意图与在途 spec 撞面 → 提示反查关联（SKILL 待办节锚点①） |
| **worktree 互核** | `git worktree list` ↔ MILESTONE 状态列：表有「开发中」而无树无分支=幽灵行；有树而表已终态=孤儿树未收尾——各问用户处置 |
| SHARED 协商 | SHARED.md 同一对象 ≥2 spec 声明且设计结论不一致、无仲裁记录 → **确认②硬阻断**；仲裁后须双 follow 复核 |
| 碎片滞留 | fragments/ 有未落账条目而 MILESTONE 对应 spec 已是合并/终态 → 落账欠尾，当场补 |
| 审计基线 | 审计/问句输出必须带「@<HEAD短hash>+工作区态」；动作前 HEAD 变 → 结论过期自动重跑 |
| 空间段核验 | SHARED 命名空间节无两队相交；段外取值（预检枚举 diff）命中 → 报，凭证违规 |
| 指纹核对 | `shasum -c .authoritative/<spec>.sha256`（勾选归一化）不符 = **硬停**，以树内重出快照＋记责任批次 |
| 覆盖缺口 | 每处「未测且本分支测不了」有 owner＋回补时点（known-failures.md 承载），M3 核零裸挂 |
| 环境新鲜 | profile 环境时间戳 vs 实测不一致 → 点名受影响 spec 走外部事实同步 PATCH，不装看不见 |

**三向差异处置**：漏挂→问处置（纳入/转挂）；漏勾→自动补勾并报告；**假勾→硬阻断**
（有勾无实说明账上有假话，比漏勾更严重，必须当面裁决；不允许"提醒后可跳过"）。
**自修复**：老 spec 缺「挂载:」行 → 以 git footer 为准补写，事实源就此补齐。
**触发点（全自动，口令仅补充）**：① spec 启动问版前（有在途版必跑）② M3 收尾报告必附
③ M4 步 0 自动执行 ④ 任意时刻用户喊「审计 vX.Y.Z」。

## 六、触发词速查

| 你说 | 动作 |
|---|---|
| 新建里程碑 vX.Y.Z | M0 |
| 把 xxx 纳入 vX.Y.Z | M1（bug 同：把 BUG-02 纳入 vX.Y.Z） |
| xxx 从 vX.Y.Z 移出 | M1 逆操作（两边表都更新） |
| 冻结 vX.Y.Z | M2（前置检查不过会列差距） |
| 汇总 vX.Y.Z / 整理升级件 | M3 |
| 发版 vX.Y.Z | M4（**先自动全量审计，账不平不进 checklist**；tag 后必问「合 main 吗」「push 吗」） |
| 审计 vX.Y.Z | 随时手动跑（M2/M3/M4 与 spec 启动时其实已自动跑过） |
| vX.Y.Z 状态 | 读 MILESTONE.md 汇报 |

## 七、与现有机制的关系

- **不改变四阶段**：单需求流程原样；里程碑是外挂层，不做里程碑的项目零感知
- **spec 版本与里程碑版本互不干扰**：spec v1.1.0 指文档版本；里程碑 v1.3.0 指发版批次，
  MILESTONE.md 表格里记录挂接时的 spec 版本，spec 后续再改需重新确认并更新表格行
- **CHANGELOG.md（项目级）生成来源变更**：v3 起从 MILESTONE.md 汇总（此前从 git log 拼），
  git log --grep "Spec:" 仅作核对手段
- **.specrc.yml 不管里程碑**：里程碑流程与规矩全在本文件，无项目差异（有差异就改本文件）
