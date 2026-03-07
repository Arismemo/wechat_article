# 阶段 2 部署与验证记录

更新时间：2026-03-07
状态：Completed

## 1. 目标

记录阶段 2 从本地开发到服务器部署、联调、真实草稿箱验证的全过程。

## 2. 部署结果

- 新增依赖：
  - `httpx`
  - `beautifulsoup4`
  - `playwright`
- 新增 migration：
  - `20260307_0002_add_source_article_metadata.py`
- 服务器已完成 `api` / `phase2_worker` 镜像切换
- `postgres`、`redis`、`api` 当前均为 `healthy`
- `phase2_worker` 已启动并通过异步 smoke test

## 3. 服务器侧配置变更

本次仅更新本项目 `.env`，未动服务器上其他项目。

新增或启用的关键变量：

- `WECHAT_ENABLE_DRAFT_PUSH=true`
- `WECHAT_API_BASE=https://api.weixin.qq.com/cgi-bin`
- `WECHAT_REQUEST_TIMEOUT_SECONDS=30`
- `FETCH_HTTP_TIMEOUT_SECONDS=25`
- `FETCH_BROWSER_TIMEOUT_SECONDS=45`
- `FETCH_USER_AGENT=<iPhone + WeChat UA>`
- `MAX_SOURCE_EXCERPT_CHARS=1200`
- `PLAYWRIGHT_HEADLESS=true`

## 4. 数据库变更

- 已执行：`alembic upgrade head`
- 结果：成功
- 实际升级：`20260307_0001 -> 20260307_0002`

新增字段：

- `source_articles.published_at`
- `source_articles.cover_image_url`

## 5. 真实联调记录

### 5.1 测试文章

- 测试来源：`https://mp.weixin.qq.com/s/OE0GJvalYOl9OJvQIg3bew`
- 抓取结果标题：`【Linux】虚拟内存的基础知识`
- 抓取结果作者：`专注Linux`

### 5.2 任务执行结果

- `task_id`：`d7b573d9-915f-4dd2-9af5-c6bb24e39a9d`
- 阶段 2 执行接口：`POST /internal/v1/tasks/{task_id}/run-phase2`
- 返回状态：`draft_saved`
- `generation_id`：`0ada4277-25fe-481b-b8b5-94050435e050`
- `wechat_media_id`：`PyYQ74YwFFGh2wyA3BOdv2ymk-Ek4xpAoyqQHIIlwiT0qVJRyfxXXV9mO7Tm5MFC`

### 5.3 数据库留痕

`source_articles` 验证结果：

- `fetch_status=success`
- `word_count=5482`

`wechat_drafts` 验证结果：

- `push_status=success`
- 已回写 `media_id`

### 5.4 API 验证结果

- `GET /healthz`：成功
- `POST /api/v1/ingest/link`：成功
- `POST /internal/v1/tasks/{task_id}/run-phase2`：成功
- `POST /internal/v1/phase2/ingest-and-enqueue`：成功
- `GET /api/v1/tasks?limit=2`：成功
- `GET /api/v1/tasks/{task_id}`：成功返回：
  - `status=draft_saved`
  - `progress=100`
  - `title=【Linux】虚拟内存的基础知识`
  - `wechat_media_id` 已可见

### 5.5 本轮补充项服务器验收

同步链路验证结果：

- `task_id`：`5d9cc392-bb31-4f7c-a9ec-7258d1862621`
- 路径：`POST /api/v1/ingest/link` -> `POST /internal/v1/tasks/{task_id}/run-phase2` -> `GET /api/v1/tasks/{task_id}`
- 返回状态：`draft_saved`
- `wechat_media_id`：`PyYQ74YwFFGh2wyA3BOdvxkz0qCmlZPjXk21PfNiOJAjMGkAWrSDI80Tet44hp-U`

异步链路验证结果：

- `task_id`：`96694882-8c18-44a2-8c7b-8efc06a0f30d`
- 路径：`POST /internal/v1/phase2/ingest-and-enqueue` -> `phase2_worker` -> `GET /api/v1/tasks/{task_id}`
- 入队返回：`enqueued=true`
- 最终状态：`draft_saved`
- `wechat_media_id`：`PyYQ74YwFFGh2wyA3BOdv9qynbQA5cvPgqO5cZH6pvLyOHhp2ta_lzV2bHObWbQg`

图片重写与数据库留痕：

- 两条任务的 `source_articles.fetch_status=success`
- 两条任务的 `source_articles.word_count=5482`
- 两条任务的 `wechat_drafts.push_status=success`
- `wechat_drafts.push_response.inline_images` 已记录图片重写日志；本次命中的原文图片均为微信域名，状态为 `already_wechat`

## 6. 容器状态

当前容器状态：

- `api`：`healthy`
- `phase2_worker`：`running`
- `postgres`：`healthy`
- `redis`：`healthy`

当前端口映射未变：

- `api`：`8000 -> 8000`
- `postgres`：`5432 -> 5432`
- `redis`：`6379 -> 6379`

说明：

- 本次没有发生端口冲突
- 按项目约束，未调整服务器上其他服务

## 7. 遇到的问题

### 7.1 macOS `._*` 文件再次污染远端目录

问题：

- 第二次构建后，Alembic 再次报错 `source code string cannot contain null bytes`

原因：

- 通过 macOS `tar` 同步代码时，AppleDouble `._*` 文件再次落到服务器目录
- 镜像构建时把这些文件带进了 `migrations/versions`

处理：

- 清理服务器项目目录下的 `._*` 和 `.DS_Store`
- 重新构建 `api` 镜像
- 重新执行 migration
- 增加 `scripts/sync_to_server.sh`，后续同步默认禁用 macOS 扩展属性打包

结果：

- 迁移成功
- 阶段 2 联调成功

### 7.2 服务器直接构建 Playwright 浏览器过慢

问题：

- 服务器直接执行 `docker compose build api phase2_worker` 时，`python -m playwright install --with-deps chromium` 下载过慢，不适合本轮收口

处理：

- 本地改为构建 `linux/amd64` 镜像
- Dockerfile 改成 `python -m playwright install --with-deps --no-shell chromium`
- 通过 `docker save | ssh ... docker load` 将镜像直接灌入服务器
- 在服务器打标签后用 `docker compose up -d --no-build` 切换 `api` 与 `phase2_worker`

结果：

- 避开服务器端慢下载
- `api` 与 `phase2_worker` 均成功切换到新镜像

## 8. 本轮补充项验收结果

以下补充项已全部完成服务器验证：

- Playwright 已升级为官方 `chromium` new headless 优先、`chrome` 可选回退
- 后台手动触发页已补最近任务列表、同步执行和异步入队按钮
- 已新增 `phase2_worker` 轻量 worker 路径与 `scripts/run_phase2_worker.py`
- 已新增正文图片上传与 HTML 重写逻辑
- 已新增 `wechat-article-exporter` 对接 PoC：`app/services/wechat_exporter_service.py` 与 `scripts/wechat_exporter_poc.py`

## 9. 结论

- 阶段 2 已完成并完成服务器验收
- 当前系统已经具备：
  - 原文抓取
  - 正文清洗与本地快照
  - 固定模板测试稿渲染
  - 微信永久封面素材上传
  - 正文图片重写
  - 微信草稿箱写入
  - 最近任务列表与后台手动触发页
  - Redis 队列与异步 worker
  - 任务和数据库留痕

## 10. 下一步

建议下次部署时优先补这几项验证：

1. 为 Playwright 兜底补充命中率、失败原因和浏览器下载失败告警
2. 为 `phase2_worker` 增加队列深度、处理中任务数和失败重试指标
3. 在服务器环境验证 `wechat-article-exporter` PoC 是否稳定可用
4. 如要继续阶段 3，进入“同题搜索 + 差异矩阵 + content_brief”
