# 全局规范中心（bryanchen-spec 内置）

本目录是 bryanchen-spec skill 的配套规范库，随 skill 全局安装、所有项目通用。

## 规范清单

| 文件 | 领域 | 核心内容 |
|---|---|---|
| code-style-backend.md | 后端代码 | Java 17 / Spring Boot 语境的通用底线 25 条 |
| code-style-frontend.md | 前端代码 | Vue 2 / Element UI 语境 + 通用前端底线 20 条 |
| logging.md | 日志 | 文件与滚动保留、格式 pattern、级别判据与四类强制日志点、脱敏、**异步线程 MDC 与线程池命名**、前端 console 分级、红线 |
| api-design.md | 接口设计 | RESTful、响应包装、错误码、校验、分页、幂等、版本 |
| database-design.md | 数据库设计 | 命名、公共字段、主键、索引、类型、SQL、变更迁移 |
| git-workflow.md | Git | 分支模型两档、命名、生命周期、commit 格式、tag、合并 |
| versioning.md | 版本 | spec 版本头、SemVer 定制、编号永久制、双层 changelog |

## 本目录的角色：默认源（可被项目级路由替换）

本目录是 bryanchen-spec 的**内置通用底线**。每个项目通过根目录 `.specrc.yml`
声明各领域实际采用哪套规范（global=本目录 / file:项目文件 / skill:规范类skill / none），
路由机制、探测顺序与完整示例见 `references/standards-routing.md`。

## 裁决顺序（冲突时自上而下）

```
① SKILL.md §0 铁律（三重确认/诚实性/生产代码保护…）——流程纪律，任何规范不得豁免
② .specrc.yml 的 project_files（AGENTS.md 等）中的具体条目——项目显式硬约束
③ .specrc.yml 中该领域声明的源——该领域唯一权威（整文件替换，本目录同领域文件不再读）
④ 默认——新代码跟随所在文件周边风格
```

- **存量代码不强制重构**：规范只约束新增代码；存量违规记录为技术债，不顺手改。
- **冲突显式化**：②与③冲突时②赢，并在 commit body 记一句采用了哪个及原因。

## 加载纪律

- **按 SKILL.md §8 的表按需加载，禁止一次性全读进上下文。**
- 每个文件控制在一次能消化的体量；条款冲突时以更具体的条款为准。

## 维护

- 规范是活文档：实战中发现某条反复被违反且违反得有道理 → 修改条款，而不是默默绕过。
- 修改本目录任何文件属于「全局规范变更」，建议在 commit 里单独成条：
  `docs(standards): <改了什么> 原因: <为什么>`
