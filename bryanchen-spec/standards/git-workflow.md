# Git 工作流规范（分支 / 提交 / 合并 / Tag）

与 bryanchen-spec 四阶段流程绑定：**Tasks 三重确认后才开分支，一个任务一个 commit。**

---

## 一、分支模型：一版一分支（version-branch model）

**每个版本一条分支，分支名 = 裸版本号（`1.4.0`，无 v 无前缀）；tag 带 v（`v1.4.0`），
两者差一个字母永不同名。** 不设 develop；原「A/B 档」二分已废除，统一此模型。

```
main ●──────────────────────●─────────────────●      只收用户确认合并的已发布版
      ╲                    ╱ (M4 问句确认后 merge --no-ff)
       1.4.0 ●──●───●─────●──                     版本分支：该版全生命的开发线
             ╲      ╲    ↑tag v1.4.0
   feature/add-x      fix/zz                      feature/fix 从这里切、合回这里
                       ╲
                        （该版发版未合 main 期间若起 v1.4.1：
                          新分支 1.4.1 从 1.4.0 的 tip 链式切，绝不从落后的 main 切）
```

| 对象 | 命名 | 粒度 | 生命周期 |
|---|---|---|---|
| 版本分支 | `1.4.0`（裸 x.y.z） | **一版一号一分支**（c 版也是新号新分支） | 立项创建 → 收 feature/fix 合并 → tag 发布 → 问合 main → **默认永久保留**（承载该版完整开发史），删除永远是用户动作 |
| 台账目录 | `releases/v1.4.0/` | 一版一目录（MILESTONE/SQL/UPGRADE） | 永久进 git，审计与重放 |
| 发布锚点 | tag `v1.4.0` | 一版一 tag，打在版本分支上 | 永久 |

**新分支基点规则（防丢代码，最高优先）**：

```
起 v1.5.0（b 升位，新功能）→ 若上一版已合 main → 从 main 最新切
起 v1.4.1（c 升位，修复批）→ 若 1.4.0 仍悬空（已 tag 未合 main）→ 从 1.4.0 分支 tip 链式切
若上一在途版未发版就要跳版 → 先按 SKILL.md §1.3 处置在途残留，不静默开新线
台账悬空表记「基于」关系；合并 main 按链序（先 1.4.0 再 1.4.1）
```
## 二、分支命名

| 分支 | 规则 | 示例 |
|---|---|---|
| **版本分支** | 裸 `x.y.z`（无 v 无前缀，与 tag `v1.4.0` 天然区分） | `1.4.0`、`1.4.1`、`1.5.0` |
| feature | `feature/<spec目录名去掉日期>`，与 spec 目录一一对应 | `feature/add-member-discount` ↔ `specs/20260926_add-member-discount/` |
| fix | `fix/<简短描述>` | `fix/login-npe` |
| hotfix | `hotfix/<简短描述>`，从最近线上 tag 切 | `hotfix/order-dup-pay` |

规则：全小写、连字符分词、≤5 个词（版本分支除外）、见名知意。
## 三、分支生命周期（与四阶段绑定）

1. **文档栖身铁律**：一切 `docs(spec)` 类提交（spec 四件套、changelog、全局账）只准落在
   **版本分支线**；HEAD 在 feature/fix/hotfix 时写文档 = 违规，先切回（SKILL §1 步骤 0）。
   误落已发生时的恢复：从错分支 `git checkout <错分支> -- <路径>` 到版本分支重新提交（或
   cherry-pick 纯文档 commit），changelog 记恢复事件；错分支合回时同内容冲突取任一侧解决。
2. **版本分支创建**：spec 启动版本问句中用户选「新开」→ 从台账基点规则所示基线切出，
   同时建 `releases/vX.Y.Z/` 台账目录（SKILL.md §1.3）。未获用户选择不建（铁律）。
3. **spec 施工分支**：Tasks 三重确认后，**从当前在途版本分支**切
   `git checkout -b feature/<功能名> <版本分支>`；完工 `merge --no-ff` **回版本分支**。
   无在途版本分支时（未接入期/hotfix 场景）临时以 main 为基点，并尽快归位。
4. **main 前进同步规则（防漂移）**：任何一次合入 main（release merge / hotfix）之后，
   下一个启动问句/简报固定带一行「main 已更新，是否同步进在途版本分支（git merge main）」——
   小合宜勤不宜攒。
5. **合并条件**（全部满足才可发起合并进版本分支）：
   - [ ] tasks.md 全部勾选；**或**未勾项全部在 completion.md 中有原因分类+处置去向且经用户批准
   - [ ] 每个任务有验证证据（测试输出/命令结果，记录在任务下或 commit body）
   - [ ] 测试全绿；项目有规范扫描（如 check_standards.py）则红线清零
   - [ ] spec 文档若中途改动过，已重新确认且版本头是「已确认」
   - [ ] completion.md 已生成、本过程发现的 bug 已登记进 bugs.md
   - [ ] **本 spec 无未收口 CR**：`changes/` 下每份 CR 状态 ∈ {已合入, 已放弃, 转新 spec, 转 BL}
     （合入八动作全勾才算「已合入」；判据见 references/change-request.md §六）
   - [ ] **共享面变更**：commit body 已同时贴「改好了」+「没改坏」双面断言实测输出
     （身份矩阵见 plan；只有一面 = 未回归，不得合并）
6. **spec 分支合并后**：删除 feature 分支（`git branch -d` + 远端 `--delete`）。
   **收尾三步硬动作（缺一视为合并未完成，事故原型：HEAD 滞留施工分支导致下一个 spec 文档被 hostage）**：
   a) `git checkout <版本分支>`——HEAD 归位账房  b) 删施工分支  c) 回执三行（合并✓/删除✓/HEAD=@版本分支）。
   **版本分支不删**——发版、合 main 之后都保留（该版开发史与潜在 patch 语境；且若悬空未合，它就是唯一内容载体）。
## 四、Commit 规范（Conventional Commits + spec 溯源）

### 格式

```
<type>(<scope>): <中文祈使短句，≤50 字>

[可选 body：为什么这么改（不写怎么改）；破坏性变更写 BREAKING CHANGE:]

Spec: specs/20260926_add-member-discount v1.0.0
Task: T-03
Bug: BUG-02
CR: CR-01
```

- **标题**：动词开头、现在时、不加句号；一句话说清做了什么。
- **body 与 footer 之间空一行**；footer 的 `Spec:`/`Task:`/`Bug:`/`CR:` 各占一行（git trailer 可解析）。
- **修 bug 的 commit 必带 `Bug: BUG-xx`**（小 bug 直修无 Spec 时仅这一行，也合法且必要——它是
  bugs.md「已修复」状态的证据来源）。
- **CR 带出的任务 commit 必带 `CR: CR-xx`**——它是 M3/M4 反查「一条需求变更带出哪些代码」的
  唯一硬锚（与 `Bug:` 同级）；**CR 合入登记为独立 `docs(spec)` commit**（同样带 `Spec:` + `CR:`，
  绝不与代码混），格式：`docs(spec): CR-01 合入 v1.2.0（增 R-06 改 R-02 废 T-03）`。
- **CR 的回退处置用 `revert:` 型且单独提交**（不删历史、不与新功能混，见红线 4）；
  被作废任务的 commit 保留在历史里，作废标记只落在 tasks.md 文本上。
- 无 spec 无 bug 的改动（chore/docs 等）：省略这些 footer，body 里写清动机。

### type 枚举

| type | 用途 |
|---|---|
| feat | 新功能（对应任务完成） |
| fix | 缺陷修复 |
| refactor | 重构（不改外部行为） |
| perf | 性能优化 |
| test | 只动测试 |
| docs | 只动文档（含 spec 文档：`docs(spec): xxx v1.0.0 三重确认`） |
| chore | 构建/依赖/杂项 |
| revert | 回滚 |

### scope

模块名（如 `bot-kidcam`、`discount`）或功能名，与项目模块结构一致，全项目统一一套词表。

### 示例

```
feat(discount): 实现会员满减后95折计算

按 plan 决策2：折扣在满减之后施加，避免叠加顺序歧义。

Spec: specs/20260926_add-member-discount v1.0.0
Task: T-03
```

```
fix(order): 修复支付回调重复入账

回调重试时未做幂等检查，加唯一索引 uk_trade_no 兜底。
```

## 五、Tag 规范

| Tag | 时机 | 形式 |
|---|---|---|
| `vX.Y.Z` | 产品发版（打在**版本分支**上） | annotated：`git tag -a v1.3.0 -m "<发版说明+spec清单>"`；tag 后按 M4 问句决定是否合 main |
| `spec/<功能名>-vN.N.N` | 可选，需审计锚点时 | lightweight 即可 |

产品版本语义见 standards/versioning.md §二。

## 六、红线（无豁免）

1. **main 禁 force-push、禁直推**（有远端保护就开保护；没有就靠自觉+review）
2. **agent 永不自主合 main**：发版后合 main 只在 M4 问句获用户明确确认后执行（`merge --no-ff`，悬空链按序合）
3. **agent 永不自主 push**：所有推送远端的动作等用户口令；发版/合并完成后只**问**「要 push 吗」
4. **部署/发版物基线 = tag 或已合并的 main**：版本悬空（已 tag 未合 main）期间，禁止从 main 拉包
   冒充该版内容（main 是旧基线）；UPGRADE.md 必须写明本包对应 tag
5. **不得提交密钥/凭据**（含测试环境的）；进 `.gitignore` 或配置中心
6. **不得改写已推送的历史**（rebase 只用于未推送的本地分支）
7. **一个 commit 不混两件事**（重构+新功能拆开；spec 文档确认独立成 commit）
8. **合并前不 squash 别人的任务级 commit**（除非全员同意改用 squash 策略）
9. **版本分支默认永久保留**：清理/删除永远是用户明示动作
10. **永不自主回退已发布/已合并的内容**：revert、撤回、删 tag、reset 一律仅由用户口令发起；
    agent 在回退话题里只做两件事——列提交清单、问修复路径（见 versioning.md §2.5）
## 七、完整旅程示例

```bash
# ── 启动版本问句，用户答「新开 v1.5.0」后：──
git checkout main && git pull
git checkout -b 1.5.0                       # 版本分支（基点按台账规则：main 或链上未合版）
# releases/v1.5.0/ 台账目录与 MILESTONE.md 同步创建（spec 流程动作）

# ── 某 spec 三重确认后：──
git checkout -b feature/add-member-discount 1.5.0   # 施工分支从版本分支切
#   每任务一 commit，footer 带 Spec:/Task:
git checkout 1.5.0 && git merge --no-ff feature/add-member-discount
git branch -d feature/add-member-discount           # 施工分支合并即删；版本分支不删

# ── M4 发版：──
git checkout 1.5.0
git tag -a v1.5.0 -m "<RELEASE-NOTES 摘要 + spec 清单>"
# CHANGELOG.md / 台账翻「已发版·悬空」 → 问用户：
#   「v1.5.0 已发版，合并到 main 吗？」
git checkout main && git merge --no-ff 1.5.0        # ← 仅当用户确认
# 台账销悬空账；问「push？」等口令

# ── 悬空期间起修复版 v1.5.1：──
git checkout -b 1.5.1 1.5.0              # 链式从 1.5.0 tip 切，绝不从旧 main 切
```
