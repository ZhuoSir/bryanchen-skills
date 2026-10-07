# 规范源路由（.specrc.yml）

解决一个问题：**项目有自己的代码/接口/数据库等规范时，每个领域用谁的。**
机制：项目根一张声明表，每个领域独立选源；Phase 0 首次探测生成、确认后永久生效。

---

## 一、声明表 `.specrc.yml`（项目根）

```yaml
# .specrc.yml —— bryanchen-spec 规范源路由表
# 每个领域独立声明源，四种取值：
#   global             本 skill 的 standards/<领域>.md（通用底线）
#   file:<相对路径>     项目自己的规范文件（建议放 docs/conventions/，进 git）
#   skill:<skill名>     已安装的其他规范类 skill（用 skill 工具加载后遵守其对应领域文件）
#   none               该领域不设规范，默认行为（新代码跟随所在文件周边风格）

domains:
  code-backend:   global          # 领域键固定七个，见 SKILL.md §8
  code-frontend:  global
  api-design:     global
  database:       global
  git-workflow:   global
  versioning:     global
  # 可加自定义领域键（如 cache-redis、scheduled-task），
  # global 源没有对应文件时自定义键只能用 file:/skill:/none

project_files:                    # 永远生效的项目硬约束，优先级最高
  - AGENTS.md
  - CLAUDE.md
```

规则：
- **一个领域只有一个源**。声明了 `skill:` 或 `file:` 后，global 同领域文件**完全不读**
  （整文件替换，不做条款级合并——避免"全局第 6 条 vs 项目第 10 条"的裁决地狱）。
  想要"全局兜底 + 项目补充"，就 `file:` 指向一份自己合并好的文件。
- **`project_files` 不受路由影响**：AGENTS.md 等永远生效（DSH 本身也会注入），
  其中的具体条目（如「禁改某目录」）优先级高于任何领域源。
- **流程铁律不在路由范围内**：三重确认、诚实性、生产代码保护等（SKILL.md §0）
  是流程纪律，任何源都不能豁免。
- 表进 git = 团队共享约定；改表就是改约定，commit 用 `chore(specrc): <改了什么领域为什么>`。

## 二、Phase 0 首次探测（只在项目第一次触发 skill 时执行）

```
1. 项目根有 .specrc.yml？
   ├─ 有 → 直接读，跳过探测（不再问用户）
   └─ 无 → 继续
2. 探测项目级规范存在物：
   - AGENTS.md / CLAUDE.md / .cursorrules / docs/conventions/*.md / docs/standards/*.md
   - 命中 → 列入 project_files 或建议 file:<路径> 源
3. 探测 catalog 中的规范类 skill：
   - 名字或描述含 standards/规范/conventions/代码标准 的 skill
   - 命中 → 按其描述的覆盖领域，建议对应领域声明 skill:<名>
     （如 code-standards 覆盖代码/接口/数据库/缓存 → 建议这四项都指向它）
4. 识别技术栈，裁剪建议范围：
   - pom.xml/build.gradle → code-backend 相关；package.json+vue/react → code-frontend 相关
   - go.mod/requirements.txt 等 → global 的后端文件是 Java 语境，建议 none 或 file: 自建
5. 生成草稿展示给用户：
   「检测到 <探测结果>。建议路由：<每领域一行>。确认写入 .specrc.yml？可逐行改。」
6. 用户确认 → 写入项目根 .specrc.yml → 提醒提交 git
```

**只探测这一次。** 之后每次触发直接读表；表要变就手工改（或让 agent 改后重新确认）。

## 三、裁决顺序（冲突时自上而下）

```
① SKILL.md §0 铁律            （流程纪律，无条件）
② project_files 的具体条目     （如 AGENTS.md「禁改 src/legacy/」）
③ domains 声明的源             （该领域的唯一权威）
④ 默认                        （跟随所在文件周边风格）
```

- ②与③冲突：②赢（项目显式硬约束 > 领域规范），并在 commit body 记一句采用了哪个。
- ③的源内部自相矛盾：停下问用户，不自行选边。
- global 源文件之间冲突（如 api-design 与 database 对同一字段命名说法不一）：
  以更具体领域的条款为准，仍无法裁决则问用户。

## 四、三个完整示例

### 示例 A：BotCloud 项目（有专属规范 skill）

```yaml
domains:
  code-backend:   skill:code-standards   # 它的 01-code-style 比 global 的 Java 底线更具体
  code-frontend:  skill:code-standards   # 含 Vue2/Element 条款
  api-design:     skill:code-standards   # 它的 02-api-design（AjaxResult/R<T> 双信封等）
  database:       skill:code-standards   # 它的 03-database-design
  cache-redis:    skill:code-standards   # 自定义领域，global 没有 → 项目 skill 补位
  git-workflow:   global                 # code-standards 不管 git → 用全局
  versioning:     global
project_files:
  - AGENTS.md
```
加载行为：Implement 后端任务 → skill 工具加载 code-standards、按其索引读 01/02 等；
开分支/commit → 读本 skill 的 standards/git-workflow.md。

### 示例 B：个人项目 / 新项目（无任何规范沉淀）

```yaml
domains:
  code-backend:   global        # 按栈裁剪：纯前端项目则此行 none、frontend 为 global
  code-frontend:  global
  api-design:     global
  database:       global
  git-workflow:   global
  versioning:     global
project_files: []
```

### 示例 C：Python 项目自带规范文档

```yaml
domains:
  code-backend:   file:docs/conventions/python-style.md   # global 后端文件是 Java 语境，不适用
  code-frontend:  none                                     # 无前端
  api-design:     file:docs/conventions/api.md
  database:       global                                   # MySQL 通用底线仍适用
  git-workflow:   global
  versioning:     global
project_files:
  - AGENTS.md
```

## 五、维护时机

| 事件 | 动作 |
|---|---|
| 项目装了新的规范类 skill | 手工改 .specrc.yml 对应领域 → commit |
| 项目沉淀出自己的规范文档 | 放进 docs/conventions/ → 改声明为 file: → commit |
| 技术栈变化（如 Vue2→Vue3） | 检查 file:/skill: 源是否还适用，改声明 |
| 某领域规范实战中反复被违反且违反得有道理 | 改规范文件本身（源在哪改哪），不是改路由 |
