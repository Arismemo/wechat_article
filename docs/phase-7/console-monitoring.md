# Phase 7 统一控制台

更新时间：2026-03-08
状态：Phase 7D Active

## 1. 目标

Phase 7A 先解决“统一入口”，Phase 7B 再接“运行参数设置”，Phase 7C 补上“实时流和统计卡片”，Phase 7D 再补“异常/成功率卡片、告警入口和环境状态面板”。

本阶段不做：

- 在线修改 `.env`
- 在线修改生产密钥
- 替代 Phase 5 的人工审核台
- 替代 Phase 6 的反馈运营台

## 2. 页面入口

- `GET /admin`
- `GET /admin/console`
- `GET /admin/console/stream`
- `GET /api/v1/admin/monitor/snapshot`
- `GET /api/v1/admin/runtime-status`
- `POST /api/v1/admin/alerts/test`

与已有后台页分工：

- `/admin`
  - 单一统一入口
  - 通过页内切换进入监控、审核、反馈、设置 4 个视图
- `/admin/console`
  - 总览、实时流、筛选、详情查看
- `/admin/settings`
  - Phase 7B 运行参数设置
- `/admin/phase5`
  - 审核、重跑、推草稿、人工动作
- `/admin/phase6`
  - 反馈导入、实验榜、风格资产

## 3. 当前能力

### 3.1 统一监控首页

页面现在已支持：

- Bearer Token 输入
- 自动轮询开关
- 轮询秒数设置
- 最近任务数量设置
- 任务状态分组看板
- SSE 实时推送
- SSE 失败后的轮询回退
- 当前筛选统计卡片
- 今日提交与今日入草稿统计卡片
- 今日失败、审稿通过率与自动推稿成功率卡片
- 异常堆积卡片
- 任务详情面板

### 3.2 历史筛选

`GET /api/v1/tasks` 现已支持：

- `limit`
- `active_only`
- `status`
- `source_type`
- `query`
  - 匹配 `task_code` / `source_url` / `normalized_url`
- `created_after`

### 3.3 任务详情

统一控制台选中任务后，会读取：

- `GET /api/v1/tasks/{task_id}/workspace`

页面展示：

- 任务状态与进度
- 源文摘要与 Brief
- 最新 generation
- 最近审计轨迹

### 3.4 监控快照接口

Phase 7C 新增：

- `GET /api/v1/admin/monitor/snapshot`
  - 需要 `API_BEARER_TOKEN`
  - 同时返回：
    - 当前筛选下的统计摘要
    - 最近任务列表
    - 当前选中任务的聚合详情

返回摘要当前包含：

- `filtered_total`
- `filtered_active`
- `filtered_manual`
- `filtered_review_passed`
- `filtered_draft_saved`
- `filtered_failed`
- `today_submitted`
- `today_draft_saved`
- `generated_at`

### 3.5 实时流

Phase 7C 新增：

- `GET /admin/console/stream`
  - 受后台 Basic Auth 保护
  - 返回 `text/event-stream`
  - 默认持续推送 `snapshot` 事件
  - 支持 `once=true` 做单次 smoke test

前端策略：

- 优先建立 SSE 连接
- 连接异常时回退为固定秒数轮询
- 重新修改筛选条件、轮询秒数或当前选中任务后重建流连接

### 3.6 Phase 7D 补充

本阶段继续补了两类运营信息：

- 异常/成功率卡片
  - `filtered_stuck`
  - `today_failed`
  - `today_review_success_rate`
  - `today_auto_push_success_rate`
- 环境状态与测试告警
  - `GET /api/v1/admin/runtime-status`
  - `POST /api/v1/admin/alerts/test`

## 4. 使用方式

1. 打开 `/admin`
2. 输入 `API_BEARER_TOKEN`
3. 默认先进入监控首页
4. 设置轮询秒数和筛选条件
5. 点击“立即刷新”
6. 在看板里选择任务，点“查看详情”
7. 如需人工动作，切到“审核台”
8. 如需反馈和实验查看，切到“反馈台”
9. 如需查看环境状态或发送测试告警，切到“设置”

## 5. 后续边界

## 5. 之后的边界

Phase 7D 完成后，下一步应进入：

- Phase 7E
  - 更细粒度的任务成功率趋势图
  - 告警分级与去重
  - 队列深度和 worker 观测面板
