# wechat_artical

微信公众号选题重构与草稿生产系统。

当前仓库状态：

- `docs/` 中维护产品方案、阶段计划和阶段交付物
- `app/` 中维护 FastAPI 后端、数据模型和服务逻辑
- `migrations/` 中维护数据库迁移
- `docker-compose.yml` 中维护 API、数据库、Redis 和阶段 2 worker 的容器化运行方式
- 阶段 2 最小闭环及补充项已完成：`原文抓取 -> 固定模板稿 -> 图片重写 -> 微信草稿箱`

## 当前已完成范围

- 建立 `FastAPI + PostgreSQL + Redis` 基础骨架
- 建立第一版数据模型和数据库迁移
- 实现最小 API：
  - `POST /api/v1/ingest/link`
  - `GET /api/v1/tasks`
  - `GET /api/v1/tasks/{task_id}`
- 实现阶段 2 内部联调入口：
  - `POST /internal/v1/tasks/{task_id}/run-phase2`
  - `POST /internal/v1/tasks/{task_id}/enqueue-phase2`
  - `POST /internal/v1/phase2/ingest-and-enqueue`
- 实现阶段 2 补充能力：
  - Playwright 官方 `chromium` new headless 兜底
  - 最近任务列表后台页：`GET /admin/phase2`
  - 正文图片上传与 HTML 重写
  - 轻量异步 worker：`scripts/run_phase2_worker.py`
  - `wechat-article-exporter` 对接 PoC：`scripts/wechat_exporter_poc.py`

## 开发约束

- 所有项目确认信息必须先更新 `docs/`
- 敏感凭据只通过环境变量注入
- 固定可靠的服务优先用 `docker compose` 容器化运行
- 如果服务器端口冲突，只改本项目端口映射

## 运行方式

阶段 1 默认采用 `docker compose` 运行以下固定服务：

- `postgres`
- `redis`
- `api`
- `phase2_worker`
