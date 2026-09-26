# 数据库设计规范（MySQL 语境通用底线）

Plan 与 Implement 阶段涉及建表/改表/写 SQL 时加载。项目有专属规范（如 code-standards 的 03-database-design）时以项目为准。

## 一、命名

1. 表名/字段名 `snake_case`，全小写；表名用业务域单数或复数**全项目统一一种**（如 `sys_user` / `order_item`）。
2. 禁用保留字（`order`、`desc`、`status` 可用但 `order` 必须避免裸用——改 `order_no`/`t_order` 按项目约定）。
3. 索引命名：普通 `idx_<表缩写>_<字段>`；唯一 `uk_<表缩写>_<字段>`；主键 `pk_<表>`（或默认 PRIMARY）。
4. 布尔语义字段用 `is_`/`has_` 前缀或项目约定（如 `deleted`），类型 `tinyint`，注释写明 0/1 含义。

## 二、表结构

5. **公共字段**（每表必备，除非有充分理由并注释说明）：
   ```sql
   id          bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
   create_time datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
   update_time datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
   deleted     tinyint      NOT NULL DEFAULT 0 COMMENT '逻辑删除 0正常 1删除',
   ```
6. 主键：单库自增 `bigint`；分布式/分库用统一 ID 生成器（雪花等）。**主键不承载业务语义**
   （业务编号另设 `xxx_no` 字段 + uk）。
7. **表和字段必须有 COMMENT**；枚举含义写进字段注释（`状态 0待支付 1已支付 2已取消`），
   代码侧对应枚举类（禁魔法值联动条款）。
8. 字段类型：
   - 金额 → `decimal(M,2)`（禁 float/double）
   - 状态/类型 → `tinyint` + 枚举
   - 时间 → `datetime`（跨时区场景按项目约定，全项目一种）
   - 字符串 → `varchar` 按需定长（姓名 64、地址 255 级别），大文本才 `text` 且考虑拆表
   - 禁 `enum` 数据库类型（变更要 DDL），用 tinyint + 代码枚举
9. 字段约束：NOT NULL + DEFAULT 优先（null 语义模糊且索引/统计易踩坑）；确实可空的写明原因。

## 三、索引

10. 业务防重的最终防线是**唯一索引**（如 `uk_user_email`），不靠应用层查重（并发会穿）。
11. 高频查询条件建索引；联合索引按**最左前缀**排列（等值列在前、范围列在后）；单表索引 ≤5 个为宜。
12. 不在索引列上做函数/运算/隐式类型转换（`WHERE DATE(create_time)=...` ❌ → 范围条件 ✅；
    字符串列传数字 ❌）。
13. 深分页用游标/延迟关联（`WHERE id > ? LIMIT n`），不 `LIMIT 100000, 20`。

## 四、SQL 与访问

14. **禁 `SELECT *`**：写明列（防宽表拖流量、防加列破坏映射）。
15. 参数绑定一律 `#{}`（MyBatis），禁 `${}` 拼接；动态排序字段走白名单。
16. 大事务拆分：事务内只做必须原子的 DB 操作，远程调用/文件/MQ 移出事务。
17. 批量操作：insert 用 batch（单批 500~1000），in 条件限制条数（≤1000），大批量处理游标分批。
18. **禁止跨库直连查别的服务的表**（微服务语境）：走对方接口或数据同步。
19. 逻辑删除统一走框架机制（MyBatis-Plus `@TableLogic`），查询默认过滤 `deleted=0`；
    物理删除仅归档/合规场景并留审批记录。

## 五、变更与迁移

20. **所有 DDL/DML 变更必须有脚本文件**（进仓库，如 `db/migration/V1.3.0__add_member_discount.sql`
    或项目既有迁移目录），**并附回滚脚本/回滚说明**。
21. 大表变更（>百万行）走 online DDL 工具（gh-ost/pt-osc）或低峰窗口，评估锁表时间。
22. 变更顺序兼容性：**先加后删、先兼容后切换**——加列不删列 → 双写/回填 → 切读 → 下线旧列，
    跨多个发版完成，不一次性 breaking。
23. 数据订正（UPDATE/DELETE 生产数据）：WHERE 先 SELECT 验证行数、留备份、脚本进仓库、走审批。
24. 索引变更同样是 DDL 变更，走 20-22 的流程。

## 六、评审清单（Plan 阶段自查）

- [ ] 表/字段命名合规、COMMENT 齐全
- [ ] 公共字段四件套在
- [ ] 金额 decimal、状态 tinyint+枚举、时间类型统一
- [ ] 业务防重有 uk
- [ ] 高频查询路径有索引支撑（把主要查询语句列出来对着看）
- [ ] 迁移脚本 + 回滚方案有
- [ ] 无跨库直查、无 SELECT *、无 ${}
