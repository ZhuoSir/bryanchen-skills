# 前端代码规范（Vue 2 / Element UI 语境通用底线）

适用于新增代码；存量保持兼容不强制重构。项目有专属规范时以项目规范为准，本文件补其未覆盖处。

## 一、命名与结构

1. 组件名 `PascalCase`（`UserList.vue`）；非组件文件 `kebab-case`；变量/方法 `camelCase`；常量 `UPPER_SNAKE_CASE`。
2. 单文件组件块顺序固定：`<template>` → `<script>` → `<style>`；`<style>` 必须 `scoped`（全局样式进专门的全局文件）。
3. script 内选项顺序统一：`name → components → props → data → computed → watch → 生命周期 → methods`。
4. 名字说意图：`handleSubmit` 而非 `doIt`；`isLoading` 而非 `flag`。
5. 目录职责：`api/` 请求定义、`views/` 页面、`components/` 复用组件、`store/` 状态、`utils/` 纯函数——不在组件里散写请求。

## 二、红线级

6. **禁魔法值进模板**：状态判断用常量/字典，❌ `v-if="row.status === '1'"` ✅ `v-if="row.status === USER_STATUS.DISABLED"`；
   字典类显示走统一字典组件/过滤器，不在模板里手写映射。
7. **请求不散写**：所有 HTTP 调用集中在 `api/` 模块（统一实例、拦截器），组件只 import 函数；
   禁在组件里直接 `axios.get('/xxx')` 拼 URL。
8. **不 mutate props**：子组件不改 props；要改 → `$emit` 事件让父组件改，或本地副本（明确命名 `xxxLocal`）。
9. **提交无调试残留**：`console.log` / `debugger` / 注释掉的大段代码不进仓库（有意保留的 console.error 级日志除外）。
   console 分级映射（error/warn 上报，log/debug **生产构建剥离**）、三处全局兜底
   （`app.config.errorHandler` / `window.onerror` / `onunhandledrejection`）、异步链路带 runId、
   禁 token 与手机号进上报体——细则见 `standards/logging.md` §五。
10. **敏感信息不进前端**：密钥、内网地址、账号不硬编码；环境相关走 `.env.*`；
   日志与上报体同样不得含 token / 手机号 / 身份证（脱敏格式见 `standards/logging.md` §2.4）。

## 三、状态与数据流

11. 局部状态放 `data`；跨组件共享才进 Vuex（state 只经 mutation 改）；能用 props/events 解决就不上全局。
12. `data` 必须是函数返回对象（组件复用不串数据）；深层嵌套对象初始化给全字段（Vue 2 响应式限制），后加字段用 `$set`。
13. computed 做派生数据，不在 computed 里发请求/改状态；watch 处理副作用，深度监听写明 `deep` 的代价意识。

## 四、用户可见质量（三态必备）

14. 每个异步视图必须处理 **loading / empty / error 三态**：列表加载有 loading、无数据有空态提示、失败有可读错误 + 重试入口。禁白屏和静默失败。
15. 表单：提交前 Element 的 `rules` 校验齐备（required/类型/长度/格式）；提交按钮防重复点击（loading/disabled）；成功/失败都有明确反馈（$message）。
16. 危险操作（删除/清空/批量）必须二次确认（$confirm），文案说清后果。
17. 文案面向用户说人话：「保存失败，请重试」而非「Error: 500」；错误细节可展开或进日志，不糊脸。

## 五、性能

18. 长列表分页或虚拟滚动（一次渲染 >200 行必须处理）；图片懒加载；路由级代码分割（`() => import(...)`）。
19. 频繁触发的处理器（input/scroll/resize）加防抖/节流；组件销毁时清理定时器、事件监听、全局订阅（beforeDestroy）。
20. 大对象/大数组避免不必要的深拷贝与深度 watch。

## 六、样式

21. 颜色/间距/字号优先用主题变量（Element 的 `$--xxx` 或项目 design token），不写散落魔法色值。
22. 不用 `!important` 覆盖组件库样式（确实要覆盖，集中在一个 override 文件并注释原因）。
23. 布局用 Flex；固定像素只用于设计明确要求处；适配范围（桌面/移动）以项目定位为准，不默默只做一种。

## 七、注释与一致性

24. 复杂业务逻辑、临时方案（HACK/待优化）必须注释**为什么**；TODO 带负责人或 issue 号：`// TODO(bryan): 等后端分页接口改造后移除前端截取 #123`。
25. 新代码跟随项目既有风格（ESLint/Prettier 配置为准）；lint 报错不提交，禁 `eslint-disable` 大面积豁免（单行豁免写明原因）。
