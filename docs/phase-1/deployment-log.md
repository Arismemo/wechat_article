# 阶段 1 部署与验证记录

更新时间：2026-03-07
状态：Completed

## 1. 部署位置

- 服务器：`117.72.155.136`
- 管理入口：`100.112.123.6`（Tailscale）
- 项目目录：`/home/liukun/j/code/wechat_artical`

## 2. 运行方式

阶段 1 采用 `docker compose` 运行以下服务：

- `postgres`
- `redis`
- `api`

当前端口映射：

- `api`：`8000 -> 8000`
- `postgres`：`5432 -> 5432`
- `redis`：`6379 -> 6379`

说明：

- 这次检查后确认上述端口空闲，因此未修改默认端口。
- 后续如遇冲突，只调整本项目端口映射，不修改服务器上其它服务端口。

## 3. 服务器侧配置

- `.env`：`/home/liukun/j/code/wechat_artical/.env`
- 临时密钥摘要：`/home/liukun/j/code/wechat_artical/.secrets.summary`
- 本地存储目录：`/home/liukun/j/code/wechat_artical/data`

说明：

- `.env` 和 `.secrets.summary` 仅保存在服务器上，不写入仓库。
- `.secrets.summary` 中记录了临时 Bearer Token 和数据库密码，供后续接快捷指令时使用。

## 4. 实际执行结果

### 4.1 容器启动

- `postgres`：启动成功，健康检查通过
- `redis`：启动成功，健康检查通过
- `api`：启动成功

### 4.2 数据库迁移

- 已执行：`alembic upgrade head`
- 结果：成功

### 4.3 Smoke Test

测试项：

- `GET /healthz`
- `POST /api/v1/ingest/link`
- `GET /api/v1/tasks/{task_id}`
- 数据库直接查询 `tasks`

结果：

- `GET /healthz`：成功，HTTP `200`
- `POST /api/v1/ingest/link`：成功，返回 `task_id`
- `GET /api/v1/tasks/{task_id}`：成功，返回 `queued`
- `tasks` 表查询：成功，能看到新写入记录

## 5. 过程中的问题与处理

### 5.1 Alembic `null bytes` 问题

问题：

- 第一次 migration 失败，报错 `source code string cannot contain null bytes`

原因：

- macOS 同步代码到 Linux 服务器时带入了 `._*` AppleDouble 文件
- Alembic 把这些文件当成版本脚本加载

处理：

- 删除服务器上的 `._*` 文件
- 更新 `.gitignore` 和 `.dockerignore`，忽略 `._*` 与 `.DS_Store`
- 重新同步代码并重建 `api` 镜像

结果：

- 第二次 migration 成功

## 6. 阶段 1 结论

- 阶段 1 的核心目标已完成
- 当前系统已经具备：
  - FastAPI 基础骨架
  - PostgreSQL / Redis / API 容器化运行
  - 初版数据模型和 migration
  - 任务创建和状态查询 API
  - 审计留痕基础能力

## 7. 下一步

- 进入阶段 2：采集链路与公众号草稿打通
- 优先实现：
  - 原文抓取
  - 正文清洗
  - 微信 token service
  - 微信素材与草稿箱写入
