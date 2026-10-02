---
name: docker-cleanup
description: "安全清理 Docker 镜像与构建缓存：先只读盘点（镜像/容器/卷/缓存 + 引用关系），自动识别保护对象（运行与停止容器引用、compose 与 Dockerfile 引用、跨项目共享、人工白名单），默认 dry-run 只出方案，用户确认后才执行删除，删完自动复验其他项目未受影响；附带 macOS Docker.raw「幽灵空间」诊断与物理回收指引。触发词：docker镜像清理、清理docker、删除无用镜像、镜像太多、docker占空间、磁盘满了、docker system df、docker prune、悬空镜像、dangling image、释放磁盘空间、Docker.raw、清镜像。NOT for: 删除数据卷/数据库数据（不可逆，只提示不执行）、Kubernetes/containerd 镜像清理、卸载或升级 Docker Desktop、CI 流水线内的镜像清理。"
---

# Docker 镜像清理（docker-cleanup）

一句话纪律：**先盘点 → 划保护区 → 给用户确认 → 才删除 → 删完复验**。
脚本默认 **dry-run**，不看到用户明确确认，绝不加 `--apply`。

## When to Use

✅ 用户说：清理一下 docker 镜像 / docker 占太多空间了 / 磁盘满了 / 帮我删掉没用的镜像 / 有个项目不做了，把它的镜像删了 / docker system df 显示可回收很多

❌ 不适用：
- 删**数据卷**、数据库数据（不可逆；本 skill 只提示可回收量，删除必须人工逐条确认）
- Kubernetes / containerd / podman 的镜像清理
- 卸载、升级、重置 Docker Desktop（见 `references/macos-reclaim.md` 的取舍）
- CI 流水线里跑（流水线该用固定 tag + 定期重建 runner，不靠交互式确认）

## 铁律（P0，全部来自真实事故）

1. **不用 `docker system prune -a`、`docker volume prune`、`docker image prune -a`**：它们按"没有被运行中容器引用"判定，会顺手删掉别的项目暂停中的 compose 栈、回滚版本、构建 base 镜像。
2. **不用 `docker image rm -f`**：让 Docker 自己当安全网——被容器引用的镜像会**删失败**，这个失败是功能不是障碍。本 skill 全程不加 `-f`。
3. **默认 dry-run**：先跑 `docker_cleanup.py` 出方案，把清单给用户看，用户明确同意后才 `--apply`。
4. **停止的容器也算"在用"**：`docker compose down` 后的项目镜像必须保留，否则下次离线启动要重新拉取。除非用户明说"这个项目不要了"。
5. **跨项目共享镜像**：同一台机器多个项目常共用 `redis:7`、`mysql:8.0`、`postgres:latest`。只按当前项目判断必然误删——用 `-s/--scan-dir` 把所有项目的 compose/Dockerfile 都扫进来。
6. **镜像站别名 / base 镜像 / 上一版发布**是最容易被误删的三类。镜像站别名（如 `docker.1ms.run/library/node:22-bookworm`）常被构建脚本 `FROM` 引用但没有任何容器引用它；上一版 tag（如 `phoenix-backend:v1.3.0`）是回滚点。脚本会把它们单独列到 **[需人工确认]**，默认不删。
7. **清理前先把容器优雅停掉**（`docker stop` / `compose down`）；清理过程中**不要重启 Docker Desktop**。非优雅关闭曾导致 MySQL 数据目录 InnoDB 损坏。
8. **不要改 Docker Desktop 的 `settings.json`/代理配置**来"顺手解决"什么（改完必须重启守护进程，老版本极易卡死）。清理镜像不需要动 Docker 配置。
9. **删镜像几乎不释放 macOS 磁盘**：Docker.raw 是稀疏文件，只涨不缩。要真正还空间给 macOS，见 `references/macos-reclaim.md`。
10. **删完必须复验**：保护区镜像仍在、别的项目容器仍在运行。脚本自动做，报告里要有结论。

## 标准流程（4 步）

### 第 1 步：只读盘点

```bash
python3 scripts/docker_inventory.py --disk -s <项目目录1> -s <项目目录2>
```

先看清楚：多少镜像、多少在保护区、多少是候选、Docker.raw 实际占了多少。**这一步不删任何东西。**

### 第 2 步：把保护区划全

按优先级自动识别（脚本负责），人工补充两类：

- `-s/--scan-dir DIR`：把所有项目的 compose / Dockerfile 目录都传进去（可重复）。**多项目机器必须传**，否则会误删别人的栈。
- `-p/--protect GLOB` 或白名单文件：脚本算不出来的，比如"这个 mirror 别名构建脚本要用""上一版留着回滚"。

### 第 3 步：出方案，等用户确认（★ 人工确认点）

```bash
python3 scripts/docker_cleanup.py -s <项目目录1> --protect '<glob>'
```

把输出里的三块给用户看：**待删清单**、**[先问用户] 清单**、**预计回收量**。
用户只要没有明确说"可以删"，就停在这里，不要 `--apply`。

### 第 4 步：执行 + 复验

```bash
python3 scripts/docker_cleanup.py -s <项目目录1> --protect '<glob>' --apply
```

脚本会：删除前二次核对容器引用（防 TOCTOU）→ 逐个删除并解释失败原因 → 可选清构建缓存 → 重新盘点复验 → 打印回收量与"保护区镜像全部健在 ✔"。

## 脚本

### scripts/docker_inventory.py —— 只读盘点

| 选项 | 说明 |
|---|---|
| `-s, --scan-dir DIR` | 扫描该目录下 `docker-compose*.yml` / `compose*.yml` / `Dockerfile*`，引用到的镜像视为保留（可重复） |
| `-p, --protect GLOB` | 保护名单 glob，如 `'phoenix-*'`、`'*:v1.3.0'`（可重复） |
| `--protect-file FILE` | 保护名单文件，默认 `~/.config/docker-cleanup/protect.txt`，存在即自动加载 |
| `--only GLOB` | 只把匹配的镜像算作候选 |
| `--min-size MB` | 只把 ≥ 该体积的算候选 |
| `--disk` | 附 Docker.raw 磁盘账目（macOS） |
| `--json` | 输出结构化 JSON（Agent 二次加工用） |

### scripts/docker_cleanup.py —— 执行清理

| 选项 | 说明 |
|---|---|
| `--apply` | **真正执行删除**；缺省只打印将执行的命令 |
| `--include-orphans` | 除悬空镜像外，也删"有 tag 但无任何引用"的镜像 |
| `--no-dangling` | 不删悬空镜像（只清 orphan 时用） |
| `--build-cache` / `--build-cache-all` | 清理构建缓存（`docker builder prune -f` / `-a`） |
| `--allow-stopped-refs` | 危险：连"只被已停止容器引用"的镜像也删（项目将无法离线重启） |
| `--only GLOB`、`--min-size MB` | 只处理匹配子集（自检、精准清理） |
| `-s/--scan-dir`、`-p/--protect`、`--protect-file` | 同盘点脚本 |

退出码：`0` 成功或 dry-run；`1` 有镜像删除失败（看报告里的原因）；`2` Docker 不可用。

> 若 `docker` 不在 PATH（Agent 沙箱里常见：只有 `/usr/bin:/bin`），脚本会自动尝试 `/usr/local/bin/docker`、`/opt/homebrew/bin/docker`、`/Applications/Docker.app/Contents/Resources/bin/docker`；也可用环境变量 `DOCKER_BIN` 指定。

## 分类语义（六类）

| 类别 | 判定 | 脚本行为 |
|---|---|---|
| `running` | 运行/暂停/重启中的容器引用 | 保护，永不删 |
| `stopped` | 已停止容器引用（含 compose 栈已 down 的项目） | 保护；要删需 `--allow-stopped-refs` |
| `reserved` | compose/Dockerfile 引用，或命中保护名单 | 保护 |
| `dangling` | `<none>:<none>` 且无任何引用 | 默认候选（最安全的一类） |
| `orphan` | 有 tag 但无任何引用 | 需 `--include-orphans` 才成为候选 |
| `skipped-filter` / `skipped-small` | 被 `--only` / `--min-size` 排除 | 本次不处理 |

## 输出怎么读

- **回收量以 `docker system df` 的 RECLAIMABLE 为准**。候选清单里的"标称合计"是各镜像大小之和，共享层会被重复计数，通常明显偏大。
- **卷的可回收量只提示不执行**：卷里是数据库/对象存储真实数据。
- **删除失败不等于出错**：`被容器占用`（安全网生效）、`有子镜像依赖这些层`（共享层）都是预期结果，报告里会给出人话解释。
- **"疑似未回收"是 Docker.raw 的账**，和删镜像无关，见下。

## 常见场景配方

**1）日常清理（最保守，只删悬空镜像）**
```bash
python3 scripts/docker_cleanup.py            # dry-run：只列出悬空镜像
python3 scripts/docker_cleanup.py --apply    # 用户确认后执行
```

**2）某个项目下线，删它整套镜像（含中间件）**
```bash
# 先确认没有别的项目共用它的镜像！用全机器扫描 + 白名单把"别人的"排掉
python3 scripts/docker_cleanup.py --include-orphans \
  -s ~/work/other-project/docker -p 'shared-*' --protect-file ~/.config/docker-cleanup/protect.txt
```

**3）磁盘告警，想尽可能腾空间**
```bash
python3 scripts/docker_cleanup.py --include-orphans --build-cache --apply   # 逻辑回收
python3 scripts/docker_inventory.py --disk                                   # 再看物理占用与差距
```

**4）多项目共用一台 Docker**
把"别人的"和"要留的"写进 `~/.config/docker-cleanup/protect.txt`，之后每次盘点/清理都会自动加载：
```
# 一行一个 glob，# 注释
phoenix-*
docker.1ms.run/*
*:v1.3.0
```

**5）精准删某个镜像**
```bash
python3 scripts/docker_cleanup.py --include-orphans --only 'oldproj-*' --apply
```

## 参考文档

- `references/safety-rules.md` —— 完整安全规则、判定矩阵、典型报错与失败模式、用户确认话术
- `references/macos-reclaim.md` —— Docker.raw 稀疏文件原理、诊断命令、物理回收的三条路径与代价

## 实战教训（本 skill 的由来）

- 老版本 Docker Desktop（引擎 20.10）在大镜像构建 + 十来个容器并发下会反复卡死，且**重启守护进程导致过 MySQL 数据目录损坏**；清理前后都不要顺手重启 Docker。
- 带 `restart: unless-stopped` 的容器会在守护进程重启后"复活"，且依赖没起来时会崩溃循环——清理前显式 `docker stop` 才不会自己爬回来。
- 一次真实清理里，`redis:7` 被两个项目同时使用；`docker.1ms.run/node:22-bookworm` 没有容器引用但被构建脚本 `FROM` 引用；`phoenix-backend:v1.3.0` 是上一版回滚点。三者都靠"扫描 compose/Dockerfile + 人工白名单 + 风险提示"保住。
- 逻辑空间从 34GB 降到 14.3GB，但 macOS 磁盘没有立刻多出对应空间——这正是 Docker.raw 的机制，别向用户承诺"删了就能腾出 N GB"。
