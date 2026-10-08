# 日志规范（logging）

**定位与分工**：项目级规范（如 `code-standards` §1.5）管「**一行 log 怎么写**」（占位符、保栈、审计 info）；
本文件管「**日志文件怎么落、格式长什么样、什么级别、异步线程怎么追**」。两者互补、都加载，
冲突时按 `standards/README.md` 的裁决顺序（项目 `project_files` > 领域声明源 > 本文件 > 周边风格）。

**技术栈默认**：Java 17 + Spring Boot + SLF4J/Logback。其他栈按同等语义映射（级别判据、文件滚动、
线程上下文传递三条是语言无关的）。

---

## 一、日志文件规范

### 1.1 路径与命名

| 项 | 规定 |
|---|---|
| 根目录 | `${LOG_HOME:-logs/${spring.application.name}}`——**环境变量可覆盖**，容器里挂 volume |
| 主文件 | `app.log`（INFO 及以上） |
| 错误文件 | `error.log`（**仅 ERROR**，独立文件：排障第一眼看它，不必在 GB 级 app.log 里捞） |
| 归档 | `archive/app.%d{yyyy-MM-dd}.%i.log.gz`——**必须压缩** |
| 版本控制 | `.gitignore` 必须含 `logs/`；日志目录**不进镜像层**、不进制品包 |

### 1.2 滚动与保留（`SizeAndTimeBasedRollingPolicy`）

| 参数 | 默认值 | 理由 |
|---|---|---|
| `maxFileSize` | 100MB | 单文件过大，grep / 下载 / 上传都痛 |
| `maxHistory`（app.log） | 30 天 | 常规排障窗口 |
| `maxHistory`（error.log） | **180 天** | 事故追溯与合规需要更长；有强合规要求继续拉长 |
| `totalSizeCap` | app 10GB / error 5GB | **防磁盘打满**——不配就是定时炸弹（红线级） |
| `cleanHistoryOnStart` | true | 长期停机后重启不清会堆积 |
| 编码 / 换行 | UTF-8 / LF | 中文乱码与跨平台 diff 的头号原因 |
| 时区 | `Asia/Shanghai`（跨时区团队统一 UTC） | **全项目一种**，写进 README 与 pattern 说明 |

### 1.3 环境分离（`springProfile`）

| 环境 | 输出目标 | 级别 | 附加约束 |
|---|---|---|---|
| dev | CONSOLE | DEBUG（可按 logger 精准开） | 可开 SQL 打印 |
| test | CONSOLE + FILE | INFO | 关 SQL 打印 |
| **prod** | **ASYNC_FILE + ERROR_FILE** | **INFO** | **禁全量 DEBUG**（红线）；禁 SQL 打印；必须走异步 appender |

### 1.4 Logback 骨架（可直接抄进项目）

```xml
<configuration>
  <property name="LOG_HOME" value="${LOG_HOME:-logs/${APP_NAME}}"/>
  <property name="PATTERN"
    value="%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level [%X{traceId:-},%X{runId:-}] %logger{36} - %msg%n"/>

  <appender name="FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
    <file>${LOG_HOME}/app.log</file>
    <rollingPolicy class="ch.qos.logback.core.rolling.SizeAndTimeBasedRollingPolicy">
      <fileNamePattern>${LOG_HOME}/archive/app.%d{yyyy-MM-dd}.%i.log.gz</fileNamePattern>
      <maxFileSize>100MB</maxFileSize>
      <maxHistory>30</maxHistory>
      <totalSizeCap>10GB</totalSizeCap>
      <cleanHistoryOnStart>true</cleanHistoryOnStart>
    </rollingPolicy>
    <encoder><pattern>${PATTERN}</pattern><charset>UTF-8</charset></encoder>
  </appender>

  <appender name="ERROR_FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
    <file>${LOG_HOME}/error.log</file>
    <filter class="ch.qos.logback.classic.filter.ThresholdFilter"><level>ERROR</level></filter>
    <rollingPolicy class="ch.qos.logback.core.rolling.SizeAndTimeBasedRollingPolicy">
      <fileNamePattern>${LOG_HOME}/archive/error.%d{yyyy-MM-dd}.%i.log.gz</fileNamePattern>
      <maxFileSize>100MB</maxFileSize>
      <maxHistory>180</maxHistory>
      <totalSizeCap>5GB</totalSizeCap>
    </rollingPolicy>
    <encoder><pattern>${PATTERN}</pattern><charset>UTF-8</charset></encoder>
  </appender>

  <appender name="ASYNC_FILE" class="ch.qos.logback.classic.AsyncAppender">
    <queueSize>2048</queueSize>
    <discardingThreshold>0</discardingThreshold>
    <neverBlock>false</neverBlock>
    <includeCallerData>false</includeCallerData>
    <appender-ref ref="FILE"/>
  </appender>

  <shutdownHook class="ch.qos.logback.core.hook.DelayingShutdownHook"><delay>2000</delay></shutdownHook>

  <springProfile name="dev">
    <root level="DEBUG"><appender-ref ref="CONSOLE"/></root>
  </springProfile>
  <springProfile name="prod">
    <root level="INFO"><appender-ref ref="ASYNC_FILE"/><appender-ref ref="ERROR_FILE"/></root>
  </springProfile>
</configuration>
```

### 1.5 容器 / K8s 与采集

- **stdout 优先**：容器内由采集器（Filebeat/Fluent Bit/Loki）收 stdout；**文件与 stdout 二选一，不双写**
  （双写=重复存储+双倍成本）。必须写文件时挂 volume 或 sidecar。
- 停机顺序：`preStop` sleep + `terminationGracePeriodSeconds` 要 **≥ shutdownHook delay**，
  否则每次发版都丢掉最后几行日志——而问题往往就出在最后几行。
- 日志平台侧按 `traceId` / `runId` 建索引字段，否则全链路串联等于没做。

---

## 二、格式规范

### 2.1 文本 pattern（默认形态）

```
%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level [%X{traceId:-},%X{runId:-}] %logger{36} - %msg%n
```

输出示例：

```
2026-10-08 14:03:22.417 [order-async-3] INFO  [a3f9c1,batch-20261008-01] c.b.o.s.OrderServiceImpl - 订单支付回调完成, orderNo=SO20261008001, result=SUCCESS, cost=42ms
2026-10-08 14:03:22.881 [http-nio-8080-exec-7] ERROR [a3f9c1,-] c.b.o.c.PayController - 支付回调处理失败, orderNo=SO20261008001
java.lang.IllegalStateException: 订单状态不允许支付
	at com.bot.order.service.OrderServiceImpl.confirm(OrderServiceImpl.java:88)
```

四个槽位各有用途：`[%thread]` 追线程（**线程池没命名这里就是 `pool-1-thread-3`，等于白打**）、
`[traceId]` 串一次请求、`[runId]` 串一次批处理执行、`%logger{36}` 定位类。

### 2.2 JSON 结构化（可选：接 ELK / Loki 才启用）

```json
{"@timestamp":"2026-10-08T14:03:22.417+08:00","level":"INFO","app":"bot-order","env":"prod",
 "thread":"order-async-3","logger":"c.b.o.s.OrderServiceImpl","traceId":"a3f9c1","runId":"batch-20261008-01",
 "userId":"10086","msg":"订单支付回调完成","orderNo":"SO20261008001","result":"SUCCESS","cost":42}
```

字段固定：`@timestamp / level / app / env / thread / logger / traceId / runId / msg`，
业务字段平铺（不塞进 msg 字符串），便于日志平台直接建索引。不接平台的项目**不要上 JSON**（纯负担）。

### 2.3 消息文本六规则

1. **占位符 `{}`，禁字符串拼接**（性能 + 异常安全）：`log.info("用户 {} 登录成功", userId)`。
2. **业务字段用 `k=v`**（`orderNo={}, amount={}`），便于 grep 与日志平台提取。
3. **异常对象作最后一个参数**：`log.error("处理失败, bizId={}", id, e)`；
   ❌ `e.getMessage()`（丢栈）、❌ `"" + e`、❌ `e.printStackTrace()`。
4. **一句一事**：不带句号、不拼 HTML；大对象 toString **截断上限 2KB**。
5. **禁**：`System.out/err.println`、空 `catch{}`、循环体内 INFO（降 DEBUG 或循环外汇总一条）。
6. **中文消息 + 英文 k=v**，全项目统一一种（与既有代码规范一致）。

### 2.4 敏感信息脱敏（红线级）

| 数据 | 落日志形态 |
|---|---|
| 手机号 | `138****1234` |
| 身份证 | `110***********1234` |
| 银行卡 | `**** **** **** 6789`（只留后 4） |
| 姓名 | `张*` / `张*三` |
| 密码 / token / 密钥 / 授权码 | **永不落**——含 DEBUG 级、含异常消息里被带出来的 |
| 请求体 / 响应体全文 | 默认不落；必须落时截断 ≤2KB 且过脱敏 |

**统一走脱敏工具**（如 `LogMaskUtil.maskMobile(...)`），**禁各处手写 substring**——漏一处就是合规事故。

### 2.5 日志量预算

| 场景 | 预算 |
|---|---|
| 正常请求 | INFO ≤ 5 行（入口 1 + 关键决策 ≤3 + 出口 1） |
| 异常请求 | ERROR **1 条**带栈（全局处理器打过了，业务层不得重复打） |
| 批处理 | 开始/结束各 1 条 INFO；每条失败 1 条 WARN/ERROR，**逐条上限 100 行，超出改汇总** |
| 循环内 | 一律 DEBUG，或循环外汇总一条 |

---

## 三、级别判据与强制日志点

### 3.1 级别判据（每条都可判定，不靠感觉）

| 级别 | 判据 | 必带 | 典型误用 |
|---|---|---|---|
| **ERROR** | **需要人介入**：影响用户、资损、数据不一致、依赖不可用且无降级 | 异常栈 + 业务主键 + traceId | ❌ 用户输错密码、参数校验失败（可预期业务失败 → WARN 或不打） |
| **WARN** | **系统自愈了但有隐患**：重试后成功、降级生效、熔断、参数越界被纠正、证书/额度将到期、队列积压 | 上下文 + **为什么可以接受** | ❌ 拿来打正常分支 |
| **INFO** | **关键业务节点 / 可审计事件**：启停、状态跃迁、支付回调、任务开始结束、配置加载、权限变更 | 一事件一条 + 业务主键 + 耗时（如适用） | ❌ 打进入每个方法（那是 DEBUG） |
| **DEBUG** | 开发排障细节：分支判断、入参出参、SQL 参数、外部调用明细 | 可含较大上下文 | ❌ 生产常开 |
| **TRACE** | 逐帧 / 循环级 | — | 基本不用 |

### 3.2 四类强制日志点（缺任一 = 实现不完整，Tasks 验证方式必须能断言到）

| 场景 | 要求 |
|---|---|
| **服务启停 / 配置加载** | INFO：应用名、版本、profile、关键开关值（**不含密钥**） |
| **外部调用**（HTTP/Feign/MQ/Redis/第三方） | 出：目标 + 关键参数（DEBUG）；回：耗时 + 结果码（DEBUG/INFO）；失败：WARN（可重试或已降级）/ ERROR（无降级） |
| **定时任务 / 批处理** | 开始 INFO（`runId` + 参数）；结束 INFO（**耗时 + 处理条数 + 失败条数**）；失败条数 >0 → WARN 汇总 |
| **安全事件** | 登录成功/失败、越权尝试、权限与角色变更、敏感数据导出 → **INFO 及以上**，带主体标识（谁、对谁、从哪来） |

---

## 四、单独线程日志（异步 / 定时任务）

> 这一块最容易出事：日志打了但**追不到是哪条链路**，或者异常**被线程池吞掉**。

### 4.1 线程池必须命名

```java
// ❌ Executors.newFixedThreadPool(4) → 线程名 pool-1-thread-3，日志里认不出是谁
// ✅ 命名线程工厂 + 有界队列 + 明确拒绝策略
new ThreadPoolExecutor(4, 8, 60, TimeUnit.SECONDS, new LinkedBlockingQueue<>(1000),
    new CustomizableThreadFactory("order-async-"),      // → order-async-1 / -2 / -3
    new ThreadPoolExecutor.CallerRunsPolicy());
```

### 4.2 MDC 跨线程必然丢失 → 每个线程池都要装传递器

MDC 基于 `ThreadLocal`，子线程拿不到 `traceId`。三种解法，**推荐 A**：

```java
// A. Spring TaskDecorator（@Async / ThreadPoolTaskExecutor 场景，一次配置全局生效）
public class MdcTaskDecorator implements TaskDecorator {
    @Override public Runnable decorate(Runnable runnable) {
        Map<String, String> ctx = MDC.getCopyOfContextMap();
        return () -> {
            if (ctx != null) { MDC.setContextMap(ctx); } else { MDC.clear(); }
            try { runnable.run(); }
            finally { MDC.clear(); }        // ★线程复用必须清：串号比没有更糟
        };
    }
}
executor.setTaskDecorator(new MdcTaskDecorator());
```

```java
// B. 手工包装（裸 ExecutorService / CompletableFuture 场景）
Map<String, String> ctx = MDC.getCopyOfContextMap();
executor.execute(() -> {
    if (ctx != null) { MDC.setContextMap(ctx); }
    try { doWork(); } finally { MDC.clear(); }
});
```

C. `TransmittableThreadLocal`（阿里 TTL）——**仅当项目已有该依赖**才用，不为日志单独引入。

**纪律**：任何线程池未配 MDC 传递 → 该池内日志无 traceId → **视为不合格**（红线 4）。

### 4.3 异步 appender 参数（防丢日志）

| 参数 | 值 | 说明 |
|---|---|---|
| `queueSize` | 2048+ | 太小会频繁阻塞业务线程 |
| `discardingThreshold` | **0** | 默认值在队列 80% 满时**丢掉 TRACE/DEBUG/INFO**——事故时最想要的 INFO 就没了 |
| `neverBlock` | false（默认阻塞） | 改 true = 宁可丢日志不阻塞，**仅在明确接受丢日志的高吞吐场景** |
| `includeCallerData` | false | 取调用方行号很贵，生产关 |

### 4.4 优雅停机必须 flush

`<shutdownHook class="ch.qos.logback.core.hook.DelayingShutdownHook"><delay>2000</delay></shutdownHook>`
——异步 appender 下进程被 kill 会丢掉队列里最后几行日志。

### 4.5 线程内异常绝不能静默

```java
// ❌ executor.execute(() -> doWork());   // 抛异常被线程池吞掉，Future 不 get 就永远看不见
// ✅ 全包 + 落 ERROR
executor.execute(() -> {
    try { doWork(); }
    catch (Throwable t) { log.error("异步任务失败, runId={}", MDC.get("runId"), t); }
});

// CompletableFuture 必须挂异常分支，否则同样静默
CompletableFuture.runAsync(task, executor)
    .exceptionally(t -> { log.error("异步链路失败, runId={}", MDC.get("runId"), t); return null; });
```

兜底：自定义 `ThreadPoolExecutor.afterExecute()` 统一记录未捕获异常。

### 4.6 批处理要能回答「哪一次执行」

```java
String runId = "batch-" + LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE) + "-" + seq;
MDC.put("runId", runId);
try {
    log.info("批处理开始, runId={}, param={}", runId, param);
    // ... 处理；每条失败 log.warn("批处理单条失败, runId={}, id={}", runId, id, e);
    log.info("批处理结束, runId={}, 处理={}, 失败={}, 耗时={}ms", runId, total, failed, cost);
} finally { MDC.remove("runId"); }
```

与调度库表（如 `sys_job_log`）**双向可查**：日志有 runId、库表有执行记录。

### 4.7 traceId 全链路注入（强制）

```java
// 入口：Filter 注入（网关已给则透传，未给则生成）
@Component
public class TraceIdFilter extends OncePerRequestFilter {
    @Override protected void doFilterInternal(HttpServletRequest req, HttpServletResponse resp,
                                              FilterChain chain) throws ServletException, IOException {
        String tid = req.getHeader("X-Trace-Id");
        if (!StringUtils.hasText(tid)) {
            tid = UUID.randomUUID().toString().replace("-", "").substring(0, 16);
        }
        MDC.put("traceId", tid);
        resp.setHeader("X-Trace-Id", tid);
        try { chain.doFilter(req, resp); } finally { MDC.remove("traceId"); }
    }
}

// 出口：Feign / RestTemplate 透传
@Bean
public RequestInterceptor traceIdInterceptor() {
    return template -> {
        String tid = MDC.get("traceId");
        if (tid != null) { template.header("X-Trace-Id", tid); }
    };
}
```

MQ 场景把 traceId 放进消息头；消费端取出后 `MDC.put` 再处理。

---

## 五、前端与 Node 侧（简版）

- `console` 分级映射：`error` → 上报；`warn` → 上报；`log/debug` → **生产构建剥离**（构建配置统一处理，
  不靠人工删）。
- 三处全局兜底必须接：`app.config.errorHandler`（Vue）、`window.onerror`、`window.onunhandledrejection`。
- 异步链路带自增 `runId`（一次用户操作触发的多个请求可串联）。
- **禁**把 token / 手机号 / 身份证写进 localStorage、上报体或 URL 参数。
- 用户可见错误说人话（「保存失败，请重试」），技术细节进上报不进 UI。

---

## 六、红线（等同「提交密钥」级，无豁免）

1. **敏感信息落日志**：密码 / token / 完整卡号 / 身份证 / 未脱敏手机号——含 DEBUG 级、含异常消息带出的。
2. **用日志替代错误处理**：只 log 不抛不返回，让调用方以为成功。
3. **生产全量 DEBUG，或未配 `totalSizeCap`**（磁盘打满 = 全站事故）。
4. **线程池无命名 + 无 MDC 传递**（异步日志不可追 = 出事查不了）。

---

## 七、验收接线（本规范如何被流程强制，不是"写了就算"）

| 阶段 | 强制动作 |
|---|---|
| **Phase 2 Plan** | 涉及后台服务 / 异步 / 定时任务 / 外部调用 → 必载本文件；plan.md 必须写「**关键日志点清单**」表（模板见 `references/templates.md`）：`场景 \| 级别 \| 触发点 \| 必带字段 \| traceId/runId` |
| **Phase 3 Tasks** | 有副作用 / 异步 / 批处理 / 外部调用的任务，「验证方式」**必须含日志断言**（例：跑一次批处理，日志须出现 `开始 runId=…` 与 `结束 处理=N 失败=M 耗时=Xms`）；缺则**确认③不放行** |
| **Phase 4 Implement** | 与 code-backend/frontend 一并**必然加载**；提交前自查三条：① 无 `printStackTrace` / `System.out`；② 线程池有命名且配 MDC 传递；③ 异步 appender 有 `shutdownHook` |
| **合并 / M4** | 合并条件：plan 的日志点清单**逐项有对应日志代码或明确豁免（写理由）**；M4 checklist：prod 为异步 appender + ERROR 独立文件 + 保留策略与 `totalSizeCap` 已配 |

---

## 八、评审自检清单（Plan/Tasks 评审与 code review 都用它）

- [ ] 四类强制日志点（启停 / 外部调用 / 定时批处理 / 安全事件）涉及的都有日志
- [ ] 级别用得对：可预期业务失败没打 ERROR；自愈类打 WARN 且写了为何可接受
- [ ] 每条 ERROR 有栈 + 业务主键 + traceId，且**不重复打**
- [ ] 消息用占位符与 `k=v`，无字符串拼接，无大对象整体 toString
- [ ] 敏感字段全部走脱敏工具，无手写 substring
- [ ] 线程池有业务命名；MDC 有传递器；子线程 `finally` 清理
- [ ] 异步链路异常有兜底记录（`catch Throwable` / `exceptionally` / `afterExecute`）
- [ ] 批处理有 runId，开始/结束两条 INFO 含耗时与条数
- [ ] 文件规范：ERROR 独立文件、压缩归档、`maxHistory` 与 `totalSizeCap` 都配了
- [ ] prod 走异步 appender + `shutdownHook`，K8s 停机宽限期 ≥ hook delay
- [ ] Tasks 里每条日志要求都有**可执行的验证方式**（不是「打日志」三个字）
