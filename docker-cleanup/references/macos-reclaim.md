# macOS 磁盘回收：Docker.raw 与"幽灵空间"

> 结论先行：**删镜像只是逻辑回收。macOS 上的磁盘空间不会跟着还回来**，除非对 Docker.raw 做物理回收（升级 Docker Desktop 一键回收 / 重置）。向用户汇报时必须说清这一点，不要承诺"删了就能腾出 N GB"。

## 1. 为什么删了镜像磁盘没变

Docker Desktop for Mac 把整个 Linux 虚拟机磁盘放在一个**稀疏文件**里：

```
~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw
```

- 里面的内容删除后，文件里留下空洞（hole），**文件本身不会自动缩小**；
- 稀疏文件的"逻辑大小"只涨不缩，"实际占用块数"也只在写入新数据时增长；
- 因此会出现：Docker 内部只剩 16GB 内容，而 Docker.raw 仍占着 59~64GB。

实测样例（引擎 20.10.20，一次真实清理后）：

| 指标 | 数值 |
|---|---|
| Docker.raw 逻辑大小（`ls -l`） | 64.00 GB |
| Docker.raw 实际占用（stat 块数 / `du`） | 63.48 GB |
| Docker 内部真实内容（`docker system df` 四项之和） | 16.32 GB |
| **差额（疑似未回收）** | **≈ 47 GB** |

同一次清理：`docker system df` 的 Images 从 34GB 降到 14.3GB（释放约 20GB 逻辑空间），但这 20GB 在 macOS 上**并没有**变成可用磁盘。

## 2. 诊断命令

```bash
# 逻辑大小 + 实际占用
ls -l  ~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw
du -h  ~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw

# Docker 内部真实内容（权威口径：Images + Containers + Local Volumes + Build Cache）
docker system df

# 本 skill 一条命令看全（含差值估算）
python3 scripts/docker_inventory.py --disk

# 宿主磁盘剩余
df -h /
```

差值 = Docker.raw 实际占用 − `docker system df` 四项之和，就是"看起来能回收但从没还给 macOS"的量。它包含已删镜像/容器的空洞、容器日志、以及 APFS 分配粒度带来的开销，**无法精确归因到某个具体镜像**（Docker 不记录"已删除历史"）。

## 3. 物理回收的三条路径

| 路径 | 做法 | 代价 | 适用 |
|---|---|---|---|
| **A. 升级 Docker Desktop 后一键回收**（推荐） | 升级到较新版本（4.28+ 有 "Clean / Purge data"），在设置里执行清理；新版本对稀疏文件回收做得更好 | 需要升级，升级期间要停服务 | 磁盘压力大、且能接受升级 |
| **B. 删除/重置 Docker.raw** | 退出 Docker → 删除（或重命名备份）Docker.raw → 重启 Docker | **所有镜像、容器、卷全部消失**，镜像要重新拉/重建；卷里的数据如果没备份就没了 | 彻底的"重装式"回收，最后手段 |
| **C. 先不动** | 只做逻辑清理，磁盘不紧张就不折腾 | 宿主机少几十 GB，但零风险 | 磁盘仍有充足余量（如剩 100GB+） |

**路径 B 的前置检查（缺一不可）**：

1. 卷里有没有不可重建的数据？`docker volume ls` → 找 MySQL / MinIO / Milvus / postgres 等命名卷，先备份或导出。
2. 有没有只能从本地镜像恢复的东西（自建镜像没推到 registry、没有 Dockerfile/源码）？
3. 有没有正在运行的其他项目容器（停掉并确认其数据安全）。
4. 记录恢复清单：本次清理要保留的镜像 tag 列表（`docker image ls --format '{{.Repository}}:{{.Tag}}'`），重置后照单重拉/重建。

## 4. 老版本 Docker Desktop 的坑（引擎 20.10 / Desktop 4.15 实测）

- 没有一键回收稀疏文件的入口；
- 大镜像构建（几 GB 的 base + 前端 pnpm 构建）与十来个容器并发时容易**引擎无响应**，甚至 GUI 假死；
- 调整代理/资源等设置后**必须重启守护进程**，而重启偶尔起不来（此时改坏配置的代价很高）；
- 结论：老版本上"清理镜像"这件事本身是安全的，但**不要顺手做升级/重置/改配置**——那些是另一类操作，风险等级完全不同，必须单独和用户确认。

## 5. 汇报口径模板

```
本次逻辑回收：镜像占用 34GB → 14.3GB（docker system df 口径）
macOS 磁盘现状：Docker.raw 实际占用 63.5GB，Docker 内部真实内容 16.3GB，
               约 47GB 是稀疏文件里"删了但不缩"的空间，需要物理回收才能还给系统。
物理回收选项：① 升级 Docker Desktop 后用 Clean/Purge（推荐，需停服务）
              ② 重置 Docker.raw（所有镜像/卷清空，需先备份数据，代价最大）
              ③ 暂时不动（磁盘还有余量时最稳妥）
```
