# Phase 7 统一控制台部署记录

更新时间：2026-03-08
状态：Phase 7E Completed

## 1. Phase 7C 发布目标

将 Phase 7C 第一刀发布到服务器：

- 统一控制台接入 SSE 实时流
- 增加监控快照接口
- 增加统计卡片
- 保持 `/admin` 单入口不变

## 2. 本次提交

- Git commit：`c6f02a2`
- 标题：`Start phase 7C realtime monitoring`

## 3. 本地验证

- `pytest -q`
  - 结果：`64 passed`
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall app tests`
  - 结果：通过

新增验证重点：

- `GET /api/v1/admin/monitor/snapshot`
- `GET /admin/console/stream?once=true`
- `/admin/console` 页面渲染文案

## 4. 服务器发布方式

本次优先尝试“预构建镜像发布”：

1. 本地构建 `linux/amd64` 镜像
2. 通过 `docker save | ssh ... docker load` 上传到服务器
3. 服务器 `git pull --ff-only`
4. `docker compose up -d --no-build --force-recreate api`

实际结果：

- 预构建镜像已在本地成功构建
- 远端镜像加载较慢，但最终服务器已完成：
  - `git pull --ff-only origin main`
  - `api` 容器重建
  - `alembic upgrade head`
- 本次无 schema 变更，worker 无需跟随重启

## 5. 服务器验收

服务器环境：

- 远端工作树：`/home/liukun/j/code/wechat_artical`
- 远端 HEAD：`c6f02a2`
- 服务状态：`wechat_artical_api` healthy

实际 smoke test：

- `GET https://auto.709970.xyz/healthz`
  - 返回：`{"status":"ok"}`
- `GET https://auto.709970.xyz/admin/console`
  - 页面已包含：
    - `统一控制台`
    - `自动实时更新（优先 SSE，失败时回退轮询）`
    - `当前模式：等待连接`
- `GET https://auto.709970.xyz/api/v1/admin/monitor/snapshot?limit=5`
  - 使用当前服务器 `API_BEARER_TOKEN` 验证通过
  - 返回统计摘要和最近任务列表
- `GET https://auto.709970.xyz/admin/console/stream?once=true&limit=5`
  - 使用后台 Basic Auth 验证通过
  - 返回 `event: snapshot`

## 6. 当前结果

Phase 7 当前已具备：

- `/admin`
  - 单入口控制台
- `/admin/console`
  - 监控首页
  - 统计卡片
  - SSE 实时推送
  - 轮询回退
- `/admin/settings`
  - 运行参数网页配置
- `/admin/phase5`
  - 审核台
- `/admin/phase6`
  - 反馈台

## 7. Phase 7D 发布目标

在 Phase 7C 的基础上继续补：

- 只读环境变量状态面板
- 告警入口
- 更完整的成功率和异常卡片

## 8. Phase 7D 本次提交

- Git commit：`9e8e7d0`
- 标题：`Start phase 7D runtime observability`

## 9. Phase 7D 本地验证

- `pytest -q`
  - 结果：`66 passed`
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall app tests`
  - 结果：通过

新增验证重点：

- `GET /api/v1/admin/runtime-status`
- `POST /api/v1/admin/alerts/test`
- `/admin/settings` 页面环境状态与告警测试文案

## 10. Phase 7D 服务器发布方式

本次仍优先尝试“预构建镜像发布”，但远端镜像加载继续偏慢。

最终采用的兜底方式：

1. 本地推送代码到 GitHub
2. 将最新 `app/` 热同步到服务器工作区
3. 将远端 `app/` 直接 `docker cp` 到 `wechat_artical_api`
4. 重启 `api` 容器

说明：

- 本次无 schema 变更
- worker 无需跟随重启
- 服务器运行态已是 Phase 7D 新代码

## 11. Phase 7D 服务器验收

实际 smoke test：

- `GET https://auto.709970.xyz/healthz`
  - 返回：`{"status":"ok"}`
- `GET https://auto.709970.xyz/api/v1/admin/monitor/snapshot?limit=3`
  - 返回新增字段：
    - `filtered_stuck`
    - `today_failed`
    - `today_review_success_rate`
    - `today_auto_push_success_rate`
- `GET https://auto.709970.xyz/api/v1/admin/runtime-status`
  - 成功返回：
    - `APP_BASE_URL`
    - `ADMIN_USERNAME`
    - `API_BEARER_TOKEN`
    - `WECHAT_APP_SECRET`
    - `ALERT_WEBHOOK_URL`
  - 密钥类字段未明文暴露
- `GET https://auto.709970.xyz/admin/settings`
  - 页面已包含：
    - `RUNTIME SETTINGS & STATUS`
    - `告警测试`
    - `环境状态`
- `POST https://auto.709970.xyz/api/v1/admin/alerts/test`
  - 当前服务器未配置 `ALERT_WEBHOOK_URL`
  - 返回：`400 {"detail":"ALERT_WEBHOOK_URL is not configured."}`
  - 说明 Phase 7D 的测试告警入口行为符合预期

## 12. 当前结果

Phase 7 当前已具备：

- `/admin/console`
  - 实时监控
  - SSE 推送
  - 成功率与异常卡片
- `/admin/settings`
  - 运行参数网页配置
  - `.env` 只读环境状态面板
  - 测试告警入口
- `/admin/phase5`
  - 审核台
- `/admin/phase6`
  - 反馈台

## 13. Phase 7E 发布目标

在 Phase 7D 的基础上继续补：

- 队列深度观测
- processing / pending 观测
- worker 心跳
- worker stale / offline 判断

## 14. Phase 7E 本次提交

- Git commit：`20d838c`
- 标题：`Start phase 7E queue observability`

## 15. Phase 7E 本地验证

- `pytest -q`
  - 结果：`68 passed`
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall app tests`
  - 结果：通过

新增验证重点：

- `queue_observability_service`
- `/api/v1/admin/monitor/snapshot` 的 `operations`
- `/admin/console` 页面里的队列与 worker 面板

## 16. Phase 7E 服务器发布方式

本次直接采用热同步兜底：

1. `bash scripts/sync_to_server.sh`
2. 将远端 `app/` 和 `scripts/` 直接 `docker cp` 到：
   - `wechat_artical_api`
   - `wechat_artical_phase2_worker`
   - `wechat_artical_phase3_worker`
   - `wechat_artical_phase4_worker`
   - `wechat_artical_feedback_worker`
3. 重启 `api` 和四个 worker

说明：

- 本次无 schema 变更
- 不需要执行 migration
- Phase 7E 的 worker 心跳依赖脚本重启，所以这次不是只动 `api`

## 17. Phase 7E 服务器验收

实际 smoke test：

- `GET https://auto.709970.xyz/healthz`
  - 返回：`{"status":"ok"}`
- `GET https://auto.709970.xyz/api/v1/admin/monitor/snapshot?limit=3`
  - 返回 `operations.available=true`
  - 返回 4 条 worker：
    - `phase2`
    - `phase3`
    - `phase4`
    - `feedback`
  - 每条都带：
    - `queue_depth`
    - `processing_depth`
    - `pending_count`
    - `last_seen_at`
    - `healthy`
    - `status`
- `GET https://auto.709970.xyz/admin/console`
  - 页面已包含：
    - `队列与 Worker 观测`
    - `worker 超过阈值未上报时，会标为 stale 或 offline`
- `redis-cli keys "*:worker:heartbeat"`
  - 当前已看到：
    - `phase2:worker:heartbeat`
    - `phase3:worker:heartbeat`
    - `phase4:worker:heartbeat`
    - `feedback:worker:heartbeat`

## 18. 当前结果

Phase 7 当前已具备：

- `/admin/console`
  - 实时监控
  - SSE 推送
  - 成功率与异常卡片
  - 队列深度与 worker 心跳观测
- `/admin/settings`
  - 运行参数网页配置
  - `.env` 只读环境状态面板
  - 测试告警入口
- `/admin/phase5`
  - 审核台
- `/admin/phase6`
  - 反馈台

## 19. 后续建议

下一刀建议进入 Phase 7F：

- 告警分级、去重和静默
- 趋势图与时间序列统计
