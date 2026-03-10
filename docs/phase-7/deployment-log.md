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

## 20. v1.1.0 发布前收口

更新时间：2026-03-09

本次收口目标不是继续扩 Phase 7 范围，而是把已经上线运行的后台会话、审稿闭环和 worker 观测能力整理为可打 tag 的第二版。

本次同步整理：

- 版本号从 `v1.0.0` 提升到 `v1.1.0`
- 补齐 `README.md`、`CHANGELOG.md`、`docs/release-v1.1.0.md`、`docs/release-process.md`
- 更新 Phase 5 / 6 / 7 文档中关于后台会话与 Bearer Token 的旧描述
- 本地忽略并清理 `output/` 等运行产物
- 清理服务器 `.deploy-backup/`、`output/` 和 AppleDouble `._*` 残留

## 21. v1.1.0 本地验证

- `pytest -q`
  - 结果：`85 passed`
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall app tests`
  - 结果：通过

重点覆盖：

- 后台会话与页面路由
- Phase 3 降级继续产出 brief
- Phase 4 AI 痕迹识别、定点 humanize 与复审
- 工作台审稿元数据响应
- worker heartbeat
- 并发 session 下状态写回

## 22. v1.1.0 当前服务器状态

当前服务器已确认：

- `/admin` 页面包含：
  - `STATUS_PROGRESS`
  - `applyOptimisticTaskState`
  - `cache: "no-store"`
- `/admin/phase5` 页面包含：
  - `AI 痕迹`
  - `已定点润色`
  - `语气诊断`
- `/admin/console/stream?once=true&limit=3`
  - 已返回 `event: snapshot`
  - 4 个 worker 当前都为 `healthy`

## 23. v1.1.0 发布要求

正式打 tag 前仍应满足：

- 当前工作区完成提交
- tag 指向明确 release commit
- 服务器从脏工作树运行态回到 Git 可追踪状态
- 正式发布使用标准路径：
  - `scripts/deploy_prebuilt_from_local.sh`
  - 或 `scripts/deploy_from_git.sh`

## 24. 结论

截至 2026-03-09，`v1.1.0` 的代码、文档和验证结果已经具备打 tag 条件。

第二版的主要价值不是新增一个全新 phase，而是把现有 MVP 主链路后的后台交互、审稿闭环和 worker 运行态增强整理为正式版本。

## 25. v1.1.1 发布收口

更新时间：2026-03-10

本次发布不是继续扩 Phase 7F，而是把 `v1.1.0` 之后已经本地完成的 4 个收口任务正式发到服务器：

- 参考文章可点击查看
- 历史稿人工采用与当前采用版本展示
- 流水线时间线
- AI 去痕触发原因可见化

本次部署方式：

- 本地 `git push origin main`
- 本地 `BASE_IMAGE=wechat_artical:v1.1.1-amd64 bash scripts/deploy_prebuilt_from_local.sh`
- 服务器 `git pull --ff-only origin main`
- `docker compose up -d --no-build --force-recreate api`
- `docker compose run --rm api alembic upgrade head`
- 额外手动执行：
  - `docker compose up -d --no-build --force-recreate phase2_worker phase3_worker phase4_worker feedback_worker`

本次服务器结果：

- 服务器仓库从 `2a292ac` 更新到 `b39fab3`
- `api` 已更新并重新健康
- 4 个 worker 已全部重建，当前快照返回：
  - `worker_count=4`
  - `healthy_count=4`
  - `phase2=idle`
  - `phase3=idle`
  - `phase4=busy`
  - `feedback=idle`

本次 smoke test：

- `GET /healthz`
  - 返回 `200 {"status":"ok"}`
- `GET /admin`
  - 页面包含：
    - `STATUS_PROGRESS`
    - `applyOptimisticTaskState`
    - `cache: "no-store"`
    - `当前采用版本`
    - `参考文章`
    - `AI 去痕诊断`
    - `流水线时间线`
- `GET /admin/phase5`
  - 页面包含：
    - `参考文章`
    - `AI 去痕诊断`
    - `流水线时间线`
    - `采用此版本`
    - `当前采用版本`
- `GET /admin/console/stream?once=true&limit=3`
  - 返回 `event: snapshot`
- `GET /api/v1/admin/monitor/snapshot?selected_task_id=b28d14f3-71e5-461c-a910-bf59a82fc393`
  - `workspace.selected_generation.source=latest_accepted`
  - `workspace.related_articles=5`
  - `workspace.timeline=26`
  - 最新 generation 已返回 `ai_trace_diagnosis`
- `GET /api/v1/tasks/b28d14f3-71e5-461c-a910-bf59a82fc393/workspace`
  - 初始 `selected_generation.version_no=2`
- `POST /internal/v1/tasks/b28d14f3-71e5-461c-a910-bf59a82fc393/select-generation`
  - 切到 `v1` 成功，随后 `workspace.selected_generation.version_no=1`
  - 再切回 `v2` 成功，随后 `workspace.selected_generation.version_no=2`

结论：

- `v1.1.1` 的 TP-01 ~ TP-04 已完成服务器发布与 smoke test
- `/admin`、`/admin/phase5`、`/api/v1/tasks/{task_id}/workspace`、`/internal/v1/tasks/{task_id}/select-generation` 已在线闭环

## 26. v1.1.2 发布收口

更新时间：2026-03-10

本次发布聚焦两件事：

- Phase 7F 第一刀正式上线
  - 告警分级
  - `dedupe_key`
  - 前端本地静默
  - 最近 24 小时趋势
- `/admin` 主工作台的会话失效恢复收口

本次部署方式：

1. 本地提交并推送 `af101ec`
2. 由于预构建镜像发布路径在 `docker save/load` 阶段耗时过长，改走 bundle 导入服务器仓库
3. 服务器仓库快进后执行：
   - `docker compose up -d --build api phase2_worker phase3_worker phase4_worker feedback_worker`
4. 由 `docker compose` 自动拉起依赖并重建 5 个服务

本次服务器结果：

- 发布会话中服务器仓库已快进到 `af101ec`
- `api`
  - 已完成重建并恢复对外服务
- `phase2_worker / phase3_worker / phase4_worker / feedback_worker`
  - 已完成重建并重新启动
- `postgres / redis`
  - 作为依赖容器保持 healthy

本次 smoke test：

- `GET https://auto.709970.xyz/healthz`
  - 返回：`{"status":"ok"}`
- `GET https://auto.709970.xyz/admin`
  - 页面包含：
    - `结构化下一步`
    - `当前卡点`
    - `focus-action-card`
    - `cache: "no-store"`
- `GET https://auto.709970.xyz/admin/phase5`
  - 页面包含：
    - `当前采用版本`
    - `采用此版本`
    - `参考文章`
    - `AI 去痕诊断`
    - `流水线时间线`
- `GET https://auto.709970.xyz/admin/console/stream?once=true&limit=3`
  - 返回 `event: snapshot`
  - 返回体包含 `alerts`、`trends` 和 worker 状态
- `GET https://auto.709970.xyz/api/v1/admin/monitor/snapshot`
  - 返回：
    - `alerts_count=1`
    - `trends_count=8`
  - 当前告警样例：
    - `critical / 任务推进卡住`

结论：

- `v1.1.2` 已完成正式发布闭环
- Phase 7F 第一刀与 `/admin` 会话恢复已在线可用
- 可以在此基线上继续启动后台前端改版实施
