# v1.1.1 发布说明

更新时间：2026-03-10
状态：Released

## 1. 发布结论

`v1.1.1` 是基于 `v1.1.0` 的补丁发布，范围只覆盖 TP-01 ~ TP-04 的发布收口，不把整份 post-`v1.1.0` 路线图视为已完成。

这一版重点把此前已在本地实现的 4 个问题真正发布到线上：

- 参考文章系统给出具体链接，并支持点击查看
- 驳回重写时可查看历史稿并做人工选择
- 有地方查看文章处理流水线的详细日志或关键信息
- AI 去痕未触发时，能明确看到原因

## 2. 相对 v1.1.0 的新增与变化

### 2.1 工作区聚合与当前采用版本

- `GET /api/v1/tasks/{task_id}/workspace` 新增：
  - `related_articles`
  - `selected_generation`
  - `timeline`
  - generation 级 `ai_trace_diagnosis`
  - `is_selected`
  - `draft_saved`
  - `wechat_media_id`
- 新增 `TaskWorkspaceQueryService`，统一 `/api/v1/tasks/{task_id}/workspace` 与 admin monitor 的聚合逻辑
- 新增 `TaskGenerationSelectionService`，通过审计日志解析“当前采用版本”

### 2.2 Phase 5 审核台

- `/admin/phase5` 现在可以：
  - 点击查看参考文章原文
  - 查看当前采用版本
  - 对历史稿执行“采用此版本”
  - 查看 AI 去痕诊断
  - 查看任务流水线时间线
- 新增 `POST /internal/v1/tasks/{task_id}/select-generation`
- “采用此版本”当前只允许直接采用已 `accepted` 的版本

### 2.3 主控台与后续链路一致性

- `/admin` 现在会展示当前采用版本、参考文章、AI 去痕诊断和流水线时间线的摘要层
- 微信草稿推送、反馈导入、反馈同步都优先跟随“当前采用版本”
- `/admin`、`/admin/phase5`、`/admin/console` 现在基于同一套 `workspace` 语义，减少“页面上看到的版本”和“实际将推送的版本”不一致的问题

## 3. 本地验证

已完成：

- `pytest -q`
  - 结果：`93 passed`
- `python3 -m compileall app tests`
  - 结果：通过

重点覆盖：

- `workspace` 返回参考文章、时间线、当前采用版本与 AI 去痕诊断
- 历史稿人工采用与冲突保护
- 当前采用版本优先的推草稿与反馈同步
- `/admin`、`/admin/phase5` 路由与页面渲染

## 4. 线上验收

本轮使用标准预构建镜像路径发布：

- 本地 `git push origin main`
- 本地 `BASE_IMAGE=wechat_artical:v1.1.1-amd64 bash scripts/deploy_prebuilt_from_local.sh`
- 服务器完成：
  - `git pull --ff-only origin main`
  - `docker compose up -d --no-build --force-recreate api`
  - `docker compose run --rm api alembic upgrade head`
  - `docker compose up -d --no-build --force-recreate phase2_worker phase3_worker phase4_worker feedback_worker`

线上已确认：

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
  - 初始 `ai_trace_diagnosis.state=not_triggered`
- `POST /internal/v1/tasks/b28d14f3-71e5-461c-a910-bf59a82fc393/select-generation`
  - 切到 `v1` 成功，返回 `status=draft_saved`
  - 随后 `workspace.selected_generation.version_no=1`
  - 再切回 `v2` 成功，返回 `status=draft_saved`
  - 随后 `workspace.selected_generation.version_no=2`

worker 运行态：

- `worker_count=4`
- `healthy_count=4`
- 当前状态：
  - `phase2=idle`
  - `phase3=idle`
  - `phase4=busy`
  - `feedback=idle`

## 5. 已知边界

当前版本仍不包含：

- 多用户、角色权限与审批流
- Phase 7F 的趋势图、告警分级、去重与静默
- 真正的后台正文编辑器
- 更完整的浏览器级 E2E 回归

## 6. 发布结果

- 正式 tag：`v1.1.1`
- 发布方式：
  - 本地预构建 `linux/amd64` 镜像
  - 服务器 `git pull --ff-only + alembic upgrade + docker compose --force-recreate`
- release commit：
  - 以 `v1.1.1` tag 指向的 commit 为准
- 服务器工作树：
  - 已对齐到 release commit
