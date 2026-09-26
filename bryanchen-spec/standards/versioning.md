# 版本规范（versioning）

管三件事：spec 文档版本、产品版本、双层 changelog。

---

## 一、spec 文档版本

### 1.1 版本头（四个产物文件首行，格式固定）

```markdown
> 版本: v1.0.0 | 状态: 已确认 | 更新: 2026-09-26 | 确认人: bryan
```

状态枚举：`草稿` → `已确认` → `待重确认`（已确认文档被改动后自动进入）→ `已确认` …
`已归档`（Implement 完成合并后，可选）。

### 1.2 版本序列（目录级统一）

一个 spec 目录的三个文档（requirements/plan/tasks）**共用一个版本序列**，
以目录为单位称呼「这个 spec 现在是 v1.2.0」。changelog.md 是唯一版本流水账。

| 事件 | 版本动作 |
|---|---|
| 初始化创建 | v0.1.0（草稿期，v0.x 内随意改，PATCH 递增即可） |
| 三文档首次全部确认 | **v1.0.0** |
| 删需求 / 改范围 / 方案推翻 | **MAJOR**（v2.0.0）→ 触发全部重审重确认 |
| 新增 R/T 条款、新增场景 | **MINOR**（v1.1.0）→ 增量确认改动的文档 |
| 措辞澄清、错别字、不改语义 | **PATCH**（v1.0.1）→ 免重新确认 |
| **勾选任务进度** | **不升版本**（进度≠内容） |

### 1.3 编号永久制（追溯的灵魂）

- `R-xx`、`T-xx` 编号一经分配**永不复用**。
- 删除条款：保留编号，标注 `### R-03 [已删除 v1.2.0] 原因: xxx`。
- 修改条款：编号不变，changelog 记「修改: R-03（v1.1.0→v1.2.0）原因: xxx」。
- 半年后任何人查 changelog 里的「R-03」都能唯一定位。

### 1.4 changelog.md 格式（spec 级，只追加不覆盖）

```markdown
# Changelog: add-member-discount

## v1.1.0（2026-09-28）确认人: bryan
- 新增: R-05 会员生日双倍积分（原因: 运营新需求）
- 修改: T-03 验收标准（原因: 评审发现漏了与满减叠加的边界）

## v1.0.0（2026-09-26）确认人: bryan
- 三重确认完成（requirements/plan/tasks），进入实现

## v0.1.0（2026-09-26）
- 初始化创建
```

### 1.5 git 锚点（默认轻量）

- **默认**：不打 spec tag。changelog.md + git log 已可完整追溯。
- **需要审计锚点时**（合规、重大版本）：确认后打
  `git tag spec/<功能名>-v1.0.0 -m "requirements/plan/tasks 三重确认"`
- spec 文档的每次确认都应是一个独立 commit：
  `docs(spec): <功能名> v1.0.0 三重确认`

---

## 二、产品版本（SemVer）

`vX.Y.Z`：
- **X（MAJOR）**：不兼容变更（接口删改、数据结构不兼容）
- **Y（MINOR）**：向下兼容的新功能
- **Z（PATCH）**：向下兼容的修复

Tag 规范：
- 在 main（或 release 分支合回后）打 annotated tag：
  `git tag -a v1.3.0 -m "发版说明（含 spec 清单）"`
- tag message 里列本次包含的 spec 目录与版本（来源：git log footer 汇总）。

---

## 三、双层 changelog 体系

| 层 | 位置 | 回答的问题 | 维护时机 |
|---|---|---|---|
| spec 级 | `specs/{目录}/changelog.md` | 这条需求为什么/何时/被谁改过 | 每次 spec 版本变更（流程自动） |
| 项目级 | 项目根 `CHANGELOG.md` | v1.3.0 发出去包含了什么 | **打 release tag 时**汇总生成 |

### 项目级 CHANGELOG.md 格式（Keep a Changelog 惯例）

```markdown
# Changelog

## [v1.3.0] - 2026-10-01
### Added
- 会员额外95折（specs/20260926_add-member-discount v1.1.0，R-01~R-05）
### Fixed
- 支付回调重复入账（hotfix/order-dup-pay，紧急修复无 spec）

## [v1.2.0] - 2026-09-15
### Changed
- 满200档位由减30调整为减40（specs/20260901_update-discount-tier v1.0.0）
```

### 汇总命令（发版时执行）

```bash
git log v1.2.0..HEAD --grep "Spec:" --pretty="format:%s | %(trailers:key=Spec,valueonly)"
```

commit footer 的 `Spec:` 行就是数据源——平时一任务一 commit 带 footer，发版零成本聚合。

### 追溯链全景

```
R-05（需求条款）
  → T-07（任务，标注 关联: R-05）
    → commit（footer: Spec: specs/... v1.1.0 / Task: T-07）
      → 项目级 CHANGELOG 的 v1.3.0 条目
        → tag v1.3.0
```

任何一环都能向上向下查：从线上版本反查到需求条款，从需求条款正查到哪次发版带出去的。
