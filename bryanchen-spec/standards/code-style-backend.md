# 后端代码规范（Java 17 / Spring Boot 语境通用底线）

适用于新增代码；存量代码保持兼容不强制重构。项目有专属规范（如 code-standards skill）时以项目规范为准，本文件补其未覆盖处。

## 一、命名与结构

1. 类 `UpperCamelCase`；方法/变量 `lowerCamelCase`；常量 `UPPER_SNAKE_CASE`；包名全小写。
2. 名字说意图：`isExpired()` 而非 `check()`；`List<SysUser> actives` 而非 `list1`。
3. 分层单向依赖：`controller → service → mapper/dao → domain`。
   Controller 不得直连 Mapper、Redis、其他服务的内部实现。
4. 一个类一个职责；方法建议 ≤50 行、参数 ≤4 个，超了先想拆分而不是加注释。
5. 公共能力下沉公共模块；远程契约放 API 模块；**禁止跨库直查别的服务的表**。

## 二、红线级（审查发现即驳回）

6. **禁魔法值**：有业务语义的字面量一律用常量或枚举承载。
   ❌ `if ("1".equals(user.getStatus()))` ✅ `if (UserStatus.DISABLE.getCode().equals(...))`
   有限取值 → 枚举（含 code + 描述）；阈值/上限/分隔符 → 常量类（按域归类，不建巨型 Constants）；
   随环境变化 → 配置中心。豁免：循环索引、纯数学的 0/1/2、测试期望值。
7. **接口出入参禁裸 Map/Object**：入参 `XxxDTO`（带校验注解）、出参 `XxxVO`（只暴露所需字段）、
   服务间传 DTO/VO，不传库表 Entity。「结构简单」不是理由，聚合/统计/树节点同样建模。
8. **equals 防 NPE**：`"常量".equals(变量)`，不写 `变量.equals("常量")`。
9. **SQL 参数绑定**：MyBatis XML 一律 `#{}`，禁 `${}`（注入风险）；拼接 SQL 同理。
10. **密钥不落代码**：密码/密钥/token 进配置中心或环境变量；密码存储用强哈希（BCrypt 级），禁 MD5/SHA1 裸哈希。

## 三、异常与日志

11. 业务失败抛业务异常（如 `ServiceException`）交全局处理器统一转响应；不用异常做流程控制。
12. 不吞异常：catch 后要么处理、要么带上下文重抛；`catch (Exception e) {}` 是事故。
13. 日志带上下文（谁/对什么/结果如何）：`log.info("订单支付回调完成, orderNo={}, result={}", ...)`。
    禁 `System.out.println`；禁打印密码、完整卡号、身份证等敏感值（脱敏后才可以）。
14. 日志级别：error=需要人管、warn=可自愈的异常、info=关键业务节点、debug=开发细节。
15. 对外错误响应不泄漏内部信息（堆栈、SQL、内部路径）。

## 四、数据与事务

16. 事务边界在 service 层；事务方法内**不做远程调用、不发 MQ、不睡眠**（长事务锁表）。
17. 判空语义明确：返回集合用空集合不用 null；Optional 只用于返回值不用于字段/参数。
18. 金额用 `BigDecimal`（或最小货币单位的 long），禁 float/double；比较用 `compareTo`。
19. 时间统一 `LocalDateTime`（或项目约定），对外格式全项目一种（ISO 8601 或时间戳）。
20. 批量操作用 batch（`saveBatch`/`IN` 限制条数），禁循环里单条插删改。

## 五、并发与调度

21. 线程池统一创建与管理（配置化核心参数、命名线程工厂），禁裸 `new Thread` / `Executors.newFixedThreadPool`（无界队列风险）。
22. 分布式环境下的定时任务：统一调度平台（如 Quartz/sys_job），任务必须**幂等可重跑**（状态位 + 唯一索引兜底），禁 `@Scheduled` 裸跑业务、禁 `new Thread` 跑批。
23. 共享可变状态必须有同步策略；能用不可变对象就别加锁。

## 六、缓存（Redis 语境）

24. 统一走封装入口（如 RedisService），key 前缀进常量类；**所有 key 必须带 TTL**；
    写库成功后删缓存（Cache-Aside）；禁 `keys *` 通配遍历/删除（用 scan）。
25. 分布式锁：原子加锁（SET NX PX）+ 唯一 requestId + Lua 脚本释放，不释放别人的锁。

## 七、测试与验证

26. 新增业务逻辑必须有对应单测；测试命名场景化：`should_返回152元_when_会员200元订单叠加满减与折扣`。
27. 单测独立可重复：不依赖执行顺序、不依赖外部环境（外部依赖 mock/内嵌替代）。
28. 修 bug 先写复现测试（红），再修（绿）——防止回归。

## 八、注释与风格

29. 注释解释**为什么**（业务意图、边界条件、坑），不复述代码在做什么；公共 API 写 Javadoc。
30. 新代码跟随所在文件/模块的周边风格；与旧风格冲突时，一致性优先于个人偏好。
31. 提交前自查：无调试残留（System.out、断点、注释掉的大段代码）、import 无冗余、格式化统一（项目配置的 formatter）。
