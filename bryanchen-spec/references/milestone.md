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

### M0 立项 —— 触发:「新建里程碑 vX.Y.Z」
1. 建 `releases/vX.Y.Z/`，从模板初始化 MILESTONE.md（目标日期、负责人、空表格）
2. 版本语义按 standards/versioning.md §二（MAJOR/MINOR/PATCH）确定 X.Y.Z 是否合理，不合理提醒用户

### M1 挂接 —— 触发:「把 <spec> 纳入 vX.Y.Z」
1. MILESTONE.md 表格加一行（spec 目录、当前 spec 版本、状态、SQL/配置件数暂记 0）
2. 单个 spec 的 Implement 收尾时主动问一句「纳入哪个里程碑？可跳过」——不强制、不阻塞
3. 一个 spec 只属于一个里程碑；要移出去需用户明确说，两处 MILESTONE.md 都更新

### M2 冻结 —— 触发:「冻结 vX.Y.Z」
前置检查（不满足则列出差距，不冻结）：
- [ ] 表格内所有 spec 状态 = 已合并（Implement 完成且 merge 进 main）
- [ ] 各 spec 的 tasks.md 全勾、验证证据齐
冻结后：MILESTONE.md 状态改「已冻结」；**新需求默认进下一里程碑**，要挤进本版本需用户明确同意
（挤入 = 解冻重走 M2，changelog 记录）。

### M3 汇总 —— 触发:「汇总 vX.Y.Z」/「整理升级件」
1. **收集**：逐 spec 读 artifacts.md；无 artifacts.md 的 spec 用
   `git log --grep "Spec: specs/<目录>"` 扫 commit + 读 plan.md 数据模型/配置节，交叉核对防漏
2. **整理 SQL**：合并同表变更 → 按依赖重排 → 分配序号 → 写文件头注释块 → 配 rollback
3. **整理配置**：汇总进 config/changes.md
4. **生成 RELEASE-NOTES.md**：升级项从各 spec 的 R 条款聚合（对外口径，去掉内部细节）
5. **编写 UPGRADE.md**：部署顺序（服务依赖序）、SQL 执行顺序（=序号序）、配置变更步骤、
   每步验证方法、整体回滚步骤（逆序）
6. **更新 MILESTONE.md** 汇总进度勾选与件数

### M4 发布 —— 触发:「发版 vX.Y.Z」
1. `checklist.md` 人工逐项勾选（**演练项必须真做**：在演练/预发环境按 UPGRADE.md 走一遍，
   SQL 全执行、配置全应用、核心功能验证；演练发现问题回 M3 修）
2. git 操作按 standards/git-workflow.md：release 分支（B 档）或 main 直接打 tag
3. tag：`git tag -a vX.Y.Z -m "<RELEASE-NOTES 摘要 + spec 清单>"`
4. 项目根 CHANGELOG.md 追加本版本条目（**来源 = MILESTONE.md 的升级项表**，不再直接从 git log 拼）
5. releases/vX.Y.Z/ 全部产物随 tag 进 main（历史版本永远可查）

## 六、触发词速查

| 你说 | 动作 |
|---|---|
| 新建里程碑 v1.4.0 | M0 |
| 把 xxx 纳入 v1.4.0 | M1 |
| xxx 从 v1.4.0 移出 | M1 逆操作（两边表都更新） |
| 冻结 v1.4.0 | M2（前置检查不过会列差距） |
| 汇总 v1.4.0 / 整理升级件 | M3 |
| 发版 v1.4.0 | M4（checklist 未勾完会停） |
| v1.4.0 状态 | 读 MILESTONE.md 汇报 |

## 七、与现有机制的关系

- **不改变四阶段**：单需求流程原样；里程碑是外挂层，不做里程碑的项目零感知
- **spec 版本与里程碑版本互不干扰**：spec v1.1.0 指文档版本；里程碑 v1.3.0 指发版批次，
  MILESTONE.md 表格里记录挂接时的 spec 版本，spec 后续再改需重新确认并更新表格行
- **CHANGELOG.md（项目级）生成来源变更**：v3 起从 MILESTONE.md 汇总（此前从 git log 拼），
  git log --grep "Spec:" 仅作核对手段
- **.specrc.yml 不管里程碑**：里程碑流程与规矩全在本文件，无项目差异（有差异就改本文件）
