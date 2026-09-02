# 图标库（Icons）

内联 16×16 **线性**图标，随模板 `assets/template.html` 的 `<defs>` 自带（共 35 枚）。
与图例、反模式同纪律：**图标是编辑手段，不是装饰**。

## 何时用 / 不用

✅ 帮助读者扫读的语义锚点：架构图中的"数据库/云/外部系统"、组织图中的部门类型、流程图里的"邮件/定时"步骤
❌ 每个节点都放（≤1/节点、能省则省）；纯装饰美化；代替文字标签

## 用法（节点内槽位）

带图标节点 = 图标 + 左对齐文字：

```svg
<!-- 盒：x=420 y=100 w=144 h=32，盒心 y=116 -->
<rect x="420" y="100" width="144" height="32" rx="4" fill="#ffffff" stroke="#1f2937"/>
<use href="#icon-code" x="432" y="108" width="16" height="16" style="color:#1f2937"/>
<text x="456" y="121" font-size="12" font-weight="600" fill="#1f2937">产品研发部</text>
```

- 图标 `x = 盒左 + 12`，`y = 盒心y − 8`（盒高 32/36/40 均适用）
- 文字 `x = 盒左 + 36`，`text-anchor="start"`；节点宽 ≥ `36 + 文本宽 + 12`（右 padding），取 4 的倍数
- 图标颜色 = `<use style="color:…">`：默认 ink `#1f2937`；焦点节点 `#2563eb`；次要素描边 `#5b6b80`
- 图标只在 `<use>` 中引用，**不要复制 path 到正文**——单文件语义（画完可删未用的 symbol，但模板默认全带）

## 目录

| slug | 图形 | 典型场景 |
|---|---|---|
| `icon-user` | 人像 | 人员/角色/人力资源 |
| `icon-home` | 房子 | 顶层/首页/门户 |
| `icon-star` | 星形 | 总经理/重点/收藏 |
| `icon-code` | `</>` | 研发/代码/前后端 |
| `icon-server` | 机柜 | 服务/部署单元 |
| `icon-database` | 圆柱 | 数据库/存储 |
| `icon-globe` | 地球 | 外部系统/全球/站点 |
| `icon-folder` | 文件夹 | 目录/分类/项目 |
| `icon-doc` | 文件（折角） | 文档/单据 |
| `icon-chart` | 柱条 | 报表/数据/市场分析 |
| `icon-gear` | 齿轮 | 配置/运维/设置 |
| `icon-clock` | 时钟 | 定时/任务调度 |
| `icon-shield` | 盾牌+对勾 | 安全/权限/合规 |
| `icon-mail` | 信封 | 邮件/消息中心 |
| `icon-wallet` | 卡 | 财务/支付/钱包 |
| `icon-check` | 对勾 | 成功/通过/校验 |
| `icon-alert` | 三角感叹号 | 告警/异常/风险 |
| `icon-send` | 纸飞机 | 发送/推送/触达 |
| `icon-users` | 双人 | 团队/多角色/部门群组 |
| `icon-mobile` | 手机 | 移动端/App/小程序 |
| `icon-monitor` | 显示器 | 终端/桌面端/客户端 |
| `icon-cpu` | 芯片 | 计算/算力/核心处理 |
| `icon-network` | 三节点拓扑 | 网络/集群/依赖关系 |
| `icon-cart` | 购物车 | 订单/商城/采购 |
| `icon-building` | 楼宇 | 办公园区/厂房/楼栋 |
| `icon-bank` | 银行立面 | 金融/账务/机构 |
| `icon-lock` | 挂锁 | 权限/加密/登录鉴权 |
| `icon-key` | 钥匙 | 密钥/令牌/凭据 |
| `icon-search` | 放大镜 | 搜索/查询/检索 |
| `icon-bell` | 铃铛 | 通知/告警/订阅提醒 |
| `icon-calendar` | 日历 | 排期/日程/计划 |
| `icon-flag` | 旗帜 | 里程碑/阶段/标记 |
| `icon-target` | 同心靶 | 目标/KPI/对准 |
| `icon-box` | 立体盒 | 组件/制品/交付包 |
| `icon-download` | 下载入仓 | 下载/导入/落库 |

## 维护规则

1. 画布 0–16（视觉范围 ≈ 2–14，防描边出界）；`stroke-width 1.2`、`fill="none" stroke="currentColor"`
2. **只允许 `<path>` / `<symbol>`**：rect/circle/line 会产生 self_check 网格告警，禁止
3. 新增图标三步：模板 `<defs>` 注册 `<symbol>` → 本表登记一行 → 画一张含新图标的示例图过 self_check
4. 同义重复不新增（如"用户组"用 `icon-users` 即可）；体量控制在 40 枚内，超出走拆图而非堆图标
