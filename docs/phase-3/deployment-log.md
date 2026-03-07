# 阶段 3 部署与验收记录

更新时间：2026-03-07
状态：已完成首轮服务器验收

## 1. 部署范围

- 服务端已上线：
  - `api`
  - `phase2_worker`
  - `phase3_worker`
  - `postgres`
  - `redis`
- 数据库 migration 已包含：
  - `20260307_0003_add_phase3_research_fields`
- 本轮部署采用“同步代码到服务器目录 + 将修复文件注入现有容器并重启”的方式完成。
  - 原因：远端重新构建 `Dockerfile` 会再次触发 Playwright 浏览器下载，耗时过长且不稳定。

## 2. 本轮修复

- 修正智谱 `web_search` 请求体，切换到官方 `search_query` 风格参数。
- 修正 `phase2_worker` / `phase3_worker` 的 `sys.path`，避免容器内执行脚本时优先命中旧 site-packages。
- 修正 Phase 3 在缺少 `source_articles` 时的自举逻辑：
  - 允许 `ingest-and-run`
  - 允许 `ingest-and-enqueue`
  - 不再要求必须先跑 Phase 2 才能进入 Phase 3

## 3. 验收样例

- 测试文章：
  - `https://mp.weixin.qq.com/s/OE0GJvalYOl9OJvQIg3bew`
- 验收任务：
  - `task_id`: `f703c3ef-e358-48ab-936d-187418c584c5`
- 同步链路：
  - 接口：`POST /internal/v1/phase3/ingest-and-run`
  - 结果：`brief_ready`
  - `analysis_id`: `1ab505e4-2301-4436-b706-d22439b97b8b`
  - `brief_id`: `15c1e239-e9af-4f75-872f-2ee8e8e3415b`
  - `related_count`: `5`
- 异步链路：
  - 接口：`POST /internal/v1/phase3/ingest-and-enqueue`
  - 结果：`brief_ready`
  - 由于 URL 去重，异步链路复用了同一个 `task_id`
  - 新生成 `analysis_id`: `649cdab8-1264-4070-acb6-7d2770ed3082`
  - 新生成 `brief_id`: `d71a4471-6011-4aac-8e31-068fc4018ace`
  - `related_count`: `5`

## 4. 关键验收结论

- 原文抓取成功，`source_articles` 已自动补齐，不再依赖 Phase 2 预抓取。
- 原文分析成功，`article_analysis` 已落库。
- 智谱 `web_search` 已在服务器环境正常返回结果。
- 相关素材抓取与筛选成功，入选 `related_articles = 5`。
- `content_brief` 已成功生成，并支持同一任务下多版本累积：
  - `brief_version = 1`
  - `brief_version = 2`
- `GET /api/v1/tasks/{task_id}/brief` 查询正常。

## 5. 验证方式

- 本地：
  - `pytest -q`
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall app scripts tests`
- 服务器：
  - `docker compose ps`
  - `docker logs --tail 50 wechat_artical_api`
  - `docker logs --tail 50 wechat_artical_phase3_worker`
  - `POST /internal/v1/phase3/ingest-and-run`
  - `POST /internal/v1/phase3/ingest-and-enqueue`
  - `GET /api/v1/tasks/{task_id}`
  - `GET /api/v1/tasks/{task_id}/brief`
  - 数据库查询 `tasks` / `article_analysis` / `related_articles` / `content_briefs` / `audit_logs`

## 6. 当前结论

Phase 3 初版研究层已经具备可用的服务器闭环：

`原文链接 -> 原文抓取 -> 原文分析 -> 同题搜索 -> 相关素材抓取 -> content_brief`

后续可以直接进入 Phase 4，基于 `content_brief` 生成正文与审稿。
