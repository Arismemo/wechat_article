# 宿主机本地部署

更新时间：2026-03-17

目标：把线上运行方式从“应用层 `docker compose`”切成“宿主机依赖一次安装 + Python venv + systemd 常驻服务”，避免每次代码发布都重新构建镜像和下载浏览器。

当前推荐形态：

- 项目代码：宿主机 Python 进程
- 常驻方式：`systemd`
- 基础设施：优先复用宿主机已有 `PostgreSQL / Redis`；如果宿主机没有，再考虑官方 Docker 容器

当前常驻 unit 清单：

- `wechat_artical-api.service`
- `wechat_artical-worker@phase2_worker.service`
- `wechat_artical-worker@phase3_worker.service`
- `wechat_artical-worker@phase4_worker.service`
- `wechat_artical-worker@feedback_worker.service`
- `wechat_artical-worker@topic_fetch_worker.service`

## 一次性准备

1. 安装宿主机依赖：

```bash
bash scripts/install_host_runtime_ubuntu.sh
```

如果 `PostgreSQL / Redis` 继续保留在官方 Docker 容器，并且宿主机当前没有服务占用 `5432/6379`，直接执行：

```bash
bash scripts/docker_infra.sh up
```

2. 调整 `.env` 关键项：

```dotenv
DATABASE_URL=postgresql+psycopg://<db_user>:<db_password>@localhost:5432/wechat_artical
REDIS_URL=redis://localhost:6379/0
PLAYWRIGHT_BROWSER_CHANNELS=chrome,chromium
LOCAL_STORAGE_ROOT=/home/<user>/j/code/wechat_artical/local_data
```

3. 初始化 venv 和 Python 依赖：

```bash
bash scripts/setup_local_host.sh
```

4. 安装 systemd 单元：

```bash
bash scripts/install_local_systemd.sh
```

## 非 systemd 本地运行

迁移数据库：

```bash
bash scripts/local_runtime.sh migrate
```

启动全部进程：

```bash
bash scripts/local_runtime.sh start-all
```

查看状态：

```bash
bash scripts/local_runtime.sh status
```

## systemd 模式发布

首次启用：

```bash
START_SERVICES=1 bash scripts/install_local_systemd.sh
```

后续发布：

```bash
bash scripts/deploy_local_from_git.sh
```

如果只是纯代码更新，跳过依赖重装：

```bash
SKIP_SETUP=1 bash scripts/deploy_local_from_git.sh
```

如果只想重启部分 unit，可以通过 `SERVICES` 指定，注意这里控制的是要重启的宿主机服务名，而不是 Docker 服务名：

```bash
SERVICES="api topic_fetch_worker" SKIP_SETUP=1 bash scripts/deploy_local_from_git.sh
```

## 从 Docker 迁移到宿主机

推荐顺序：

1. 先保留 `postgres/redis` 官方容器，只迁出 `api + worker`
2. 把 `.env` 里的 `DATABASE_URL` / `REDIS_URL` 改成宿主机可访问地址，例如 `127.0.0.1:5432` 与 `127.0.0.1:6379`
3. 把 `LOCAL_STORAGE_ROOT` 改成宿主机目录
4. 安装并启动本地 `systemd` 服务
5. 验证通过后停掉旧 `api/worker` 容器
6. 如有需要，再单独做 `postgres/redis` 的第二阶段迁移

如果要清理旧应用层容器和镜像：

```bash
bash scripts/cleanup_legacy_app_docker.sh
```

## 常用排障命令

```bash
sudo systemctl status wechat_artical-api.service
journalctl -u wechat_artical-api.service -f
journalctl -u wechat_artical-worker@phase4_worker.service -f
journalctl -u wechat_artical-worker@topic_fetch_worker.service -f
```
