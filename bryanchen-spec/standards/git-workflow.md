# Git 工作流规范（分支 / 提交 / 合并 / Tag）

与 bryanchen-spec 四阶段流程绑定：**Tasks 三重确认后才开分支，一个任务一个 commit。**

---

## 一、分支模型（两档）

### A 档 · 日常默认（单人 / 小团队）

```
main ──────●─────────●─────────●──────   永远可发布；只进 merge；禁 force-push
            \       / \       /
feature/*    ●─────●   \     /           一个 spec 一个分支
                        \   /
fix/*                    ●─               非紧急小修（无 spec 的小改动）
```

### B 档 · 有发布周期 / 多版本并行时启用（在 A 档上加两种）

```
release/v1.3.0   准备发布时从 main 切出；只收 bugfix 不收新功能；
                 发布后 tag v1.3.0 → 合回 main → 删除分支
hotfix/*         生产紧急修复，从 main（或线上 tag）切出；
                 修完合回 main（若有进行中的 release 分支，同时合入它）；打 patch tag
```

> 不设 develop 分支（trunk-based + release 分支），避免完整 git-flow 的重仪式。

## 二、分支命名

| 分支 | 规则 | 示例 |
|---|---|---|
| feature | `feature/<spec目录名去掉日期>`，与 spec 目录一一对应 | `feature/add-member-discount` ↔ `specs/20260926_add-member-discount/` |
| fix | `fix/<简短描述>` | `fix/login-npe` |
| hotfix | `hotfix/<简短描述>` | `hotfix/order-dup-pay` |
| release | `release/v<X.Y.Z>` | `release/v1.3.0` |

规则：全小写、连字符分词、≤5 个词、见名知意。

## 三、分支生命周期（与四阶段绑定）

1. **开分支时机**：Tasks 确认（三重确认自检通过）之后，从最新 main 切出。
   方案没定不切分支——分支存在即意味着「要做什么已冻结」。
2. **Implement 期间**：一个任务一个 commit（见 §四）。
3. **合并条件**（全部满足才可发起合并）：
   - [ ] tasks.md 全部勾选
   - [ ] 每个任务有验证证据（测试输出/命令结果，记录在任务下或 commit body）
   - [ ] 测试全绿；项目有规范扫描（如 check_standards.py）则红线清零
   - [ ] spec 文档若中途改动过，已重新确认且版本头是「已确认」
4. **合并方式**：默认 `git merge --no-ff feature/xxx`
   - 理由：保留 feature 边界与任务级 commit，与「一个 spec 一个工作单元」对齐，
     footer 溯源不被压扁。
   - 可选 squash（想要 main 历史极简时），代价：丢任务级追溯，需在 squash message
     里手工带上任务清单。
5. **合并后**：删除 feature 分支（`git branch -d` + 远端 `--delete`）。

## 四、Commit 规范（Conventional Commits + spec 溯源）

### 格式

```
<type>(<scope>): <中文祈使短句，≤50 字>

[可选 body：为什么这么改（不写怎么改）；破坏性变更写 BREAKING CHANGE:]

Spec: specs/20260926_add-member-discount v1.0.0
Task: T-03
```

- **标题**：动词开头、现在时、不加句号；一句话说清做了什么。
- **body 与 footer 之间空一行**；footer 的 `Spec:`/`Task:` 各占一行（git trailer 可解析）。
- 无 spec 的改动（fix/hotfix/chore）：省略 Spec/Task footer，body 里写清动机。

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
| `vX.Y.Z` | 产品发版（main 上） | annotated：`git tag -a v1.3.0 -m "<发版说明+spec清单>"` |
| `spec/<功能名>-vN.N.N` | 可选，需审计锚点时 | lightweight 即可 |

产品版本语义见 standards/versioning.md §二。

## 六、红线（无豁免）

1. **main 禁 force-push、禁直推**（有远端保护就开保护；没有就靠自觉+review）
2. **不得提交密钥/凭据**（含测试环境的）；进 `.gitignore` 或配置中心
3. **不得改写已推送的历史**（rebase 只用于未推送的本地分支）
4. **一个 commit 不混两件事**（重构+新功能拆开；spec 文档确认独立成 commit）
5. **合并前不 squash 别人的任务级 commit**（除非全员同意改用 squash 策略）

## 七、完整旅程示例

```bash
# 三重确认后
git checkout main && git pull
git checkout -b feature/add-member-discount

# 每个任务完成
git add <相关文件>
git commit    # feat(discount): ... + Spec/Task footer

# 全部完成、证据齐全
git checkout main && git pull
git merge --no-ff feature/add-member-discount
git branch -d feature/add-member-discount

# 发版（B 档）
git checkout -b release/v1.3.0        # 只收 bugfix
git tag -a v1.3.0 -m "..."            # 发布后
git checkout main && git merge release/v1.3.0 && git branch -d release/v1.3.0
# 同时汇总项目根 CHANGELOG.md（命令见 versioning.md §三）
```
