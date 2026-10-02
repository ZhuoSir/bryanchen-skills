# 安全规则与失败模式

## 1. 判定矩阵：镜像被"谁"引用

按下列优先级从高到低判定，命中即停（脚本实现的就是这张表）。

| 优先级 | 引用来源 | 判定 | 能不能删 |
|---|---|---|---|
| 1 | 运行中/暂停/重启中的容器 | 绝对保护 | ❌ 不删；要删先让用户停容器 |
| 2 | 已停止/已退出的容器 | 保护（项目可能随时 `compose up`） | ⚠️ 仅用户明说"这个项目不要了"时，才 `--allow-stopped-refs` |
| 3 | 任一项目的 compose 文件 `image:` | 保护 | ⚠️ 该栈确认下线才行；注意 `docker-compose.local.yml` 等 override 文件里的**本地复用镜像** |
| 4 | 任一 Dockerfile 的 `FROM`（含 `${VAR:-default}` 默认值） | 保护 | ⚠️ base 镜像删了，下次构建会重新拉几个 GB |
| 5 | 人工白名单 glob | 保护 | ❌ 除非用户主动撤销白名单 |
| 6 | 镜像站/私有仓库别名（`docker.1ms.run/...`、`registry.internal/...`） | 风险提示 | ⚠️ 先问用户"构建脚本是否 FROM 它" |
| 7 | 同仓库存在"在用版本"（如 `svc:v1.3.0` vs 在用的 `svc:v1.4.0-dev`） | 风险提示 | ⚠️ 大概率是回滚点，先问用户 |
| 8 | `<none>:<none>` 且无任何引用 | 悬空镜像 | ✅ 默认候选（共享层被依赖时会删失败，安全） |
| 9 | 有 tag 但无任何引用 | 孤儿镜像 | ✅ `--include-orphans` 后候选 |

**推论**：
- "没人用的 tag" ≠ "可以删"——第 3/4/5/6/7 条都不体现为容器引用。
- "有容器引用" ≠ "不能删"——已停止容器是第 2 条，属于"暂时别删"。

## 2. 只允许的两条删除路径

```bash
docker image rm <tag1> <tag2> ...   # 有 tag 的镜像：按 tag 删（一个都不许漏，否则只是 untag）
docker image rm <image-id>          # 悬空镜像：按 ID 删
docker builder prune -f             # 可选：构建缓存（-a 则连可复用缓存一起清）
```

**永不使用**：

| 禁用命令 | 原因 |
|---|---|
| `docker system prune -a` | 连别的项目暂停中的栈、回滚版本一起删 |
| `docker image prune -a` | 同上，且不等价于"删悬空镜像" |
| `docker volume prune` | 卷里是数据库/对象存储数据，不可逆 |
| `docker image rm -f` | 强行剥离引用，破坏"删失败即安全网"的设计 |
| `docker rmi $(docker images -q)` | 同上，且 Shell 展开后无法逐条解释 |

## 3. 典型报错与含义

| 报错片段 | 含义 | 处理 |
|---|---|---|
| `conflict: unable to delete <id> (must be forced) - image is being used by stopped container xxx` | 被已停止容器引用 | 预期结果，跳过；要删先删容器 |
| `conflict: unable to delete <id> (cannot be forced) - image is being used by running container xxx` | 被运行中容器引用 | 预期结果，跳过；先问用户 |
| `conflict: unable to delete <id> (cannot be forced) - image has dependent child images` | 这些层被其他镜像依赖（多 tag 或构建链） | 预期结果；先删依赖它的镜像，或按 tag 删 |
| `image is referenced in multiple repositories` | 同一镜像有多个 tag，用 ID 删不被允许 | 改为按每个 tag 逐个删（脚本已这样做） |
| `No such image: xxx` | 镜像已被删/被 retag | 忽略，重新盘点 |
| `Error response from daemon: ... i/o timeout` / `docker ps` 卡住 | 守护进程无响应 | 见下节，不要盲目重启 |

## 4. 守护进程无响应怎么办

现象：`docker ps` 卡住、`Bad response from Docker engine`、命令超时。

处理顺序：

1. **等 10~30 秒重试一次**（大镜像操作时短暂无响应是常态）。
2. 看 Docker Desktop 图标/窗口：如果只是 GUI 假死而 daemon 正常，**重启 GUI 进程即可，不要重启 daemon**。
3. 如果 daemon 真的挂了：
   - 先确认容器里的数据已落盘（能 `docker stop` 就先优雅停止）；
   - **不要**在容器还在写数据时强杀守护进程/虚拟机（曾导致 MySQL InnoDB 数据目录损坏）；
   - 重启后检查带 `restart: unless-stopped` 的容器是否"复活"并在崩溃循环（依赖没起来时会出现），必要时显式 `docker stop`。
4. **不要在清理任务中修改 Docker Desktop 的 `settings.json`**（代理/资源等）：改完必须重启守护进程，而老版本重启后可能起不来；而且这与清理无关。

## 5. 数据边界：镜像 vs 容器 vs 卷

| 对象 | 删掉的后果 | 本 skill 的行为 |
|---|---|---|
| 镜像 | 代码/依赖，可重新构建或拉取 | 允许删除（按上面的判定矩阵） |
| 悬空层 | 构建残留 | 允许删除 |
| 容器 | 容器可写层（临时数据） | 不删容器；容器只作为"参考源" |
| **卷** | **MySQL/MinIO/Milvus 等真实数据，不可逆** | **绝不删**，只提示可回收量 |
| 构建缓存 | 下次构建变慢 | 可选清理（`--build-cache`） |
| Docker.raw | 全部镜像/容器/卷（等于重置） | 见 `macos-reclaim.md`，必须先得到用户确认与备份 |

用户若要求"把没用的容器和卷也清掉"：容器可逐条列名让用户确认后 `docker rm`；**卷必须逐条确认 + 明确数据来源与备份情况**，并提醒"删了无法恢复"。

## 6. 用户确认话术模板（★ 确认点）

给用户看的必须包含四件事：删什么、留什么、回收多少、删错了会怎样。

```
盘点结果（docker system df 口径）：镜像 24 个 14.34GB，可回收 12.92GB

本次计划删除 4 个悬空镜像（构建残留，无任何容器/配置引用），标称合计 3.52GB：
  <none> f1ffc4c5d230   1.57GB
  <none> 9bc2dcf054b0   1.57GB
  <none> 72a766e5bc56   190MB
  <none> e1a86bc58017   190MB

保留不动：
  · 运行中容器引用的 4 个（phoenix 栈 + redis:7）
  · compose/Dockerfile 引用的 9 个（bisheng 全套，删了下次启动要重拉）
  · 白名单 phoenix-* 两个旧版本（回滚点）

下面这几个看着还需要，我没有自动删，请你确认是否保留：
  ⚠ docker.1ms.run/library/node:22-bookworm  构建脚本可能 FROM 它
  ⚠ dataelement/bisheng-backend:base.v10     后端构建 base 镜像

风险：删除只影响镜像层，不动容器与数据卷；但注意 macOS 磁盘不会立刻多出 3.52GB
（Docker.raw 稀疏文件不收缩），这是逻辑回收。

确认执行吗？
```

## 7. 清理前后检查清单

清理前：

- [ ] `docker ps -a` 里没有"正在构建/正在拉取"的中间状态
- [ ] 需要保留的栈已确认（本项目 + 其他项目）
- [ ] 所有项目目录都传了 `-s/--scan-dir`
- [ ] 白名单文件 `~/.config/docker-cleanup/protect.txt` 已按机器实际情况写好
- [ ] 用户已看到待删清单并明确同意

清理后：

- [ ] 脚本报告的"保护区镜像全部健在 ✔"
- [ ] "运行中容器 N 个未受影响 ✔"
- [ ] 失败项逐条解释过（是安全网还是真问题）
- [ ] 需要时再跑一次 `docker_inventory.py --disk` 说明物理空间现状
