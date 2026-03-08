# Phase 7 统一控制台

更新时间：2026-03-08
状态：Phase 7E Active

## 1. 目标

Phase 7A 先解决“统一入口”，Phase 7B 再接“运行参数设置”，Phase 7C 补上“实时流和统计卡片”，Phase 7D 再补“异常/成功率卡片、告警入口和环境状态面板”，Phase 7E 则继续接上“队列深度与 worker 心跳观测”。

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
  - 主入口
  - 面向日常使用：贴链接、看进度、做动作
- `/admin/console`
  - 监控详情页
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

- 单页主控台 `/admin`
- 开始一个任务
- 最近任务列表
- 自动刷新
- 任务状态筛选
- 关键词检索
- “现在该做什么”提示
- 快捷动作：
  - 重新跑一版
  - 通过
  - 驳回重写
  - 推草稿
- 高级深链：
  - 设置
  - 监控详情
  - 审核台
  - 反馈台

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

### 3.7 Phase 7E 补充

本阶段继续补：

- 四条队列的运行观测
  - `phase2`
  - `phase3`
  - `phase4`
  - `feedback`
- 每条队列展示：
  - `queue_depth`
  - `processing_depth`
  - `pending_count`
  - `last_seen_at`
  - `current_task_id`
  - `status`

worker 当前通过 Redis 心跳上报自身状态；超过 `WORKER_HEARTBEAT_STALE_SECONDS` 未更新时，会被标为 `stale` 或 `offline`。

## 4. 使用方式

1. 打开 `/admin`
2. 把微信文章链接贴进去
3. 点“开始处理”
4. 左边看最近任务自动刷新
5. 右边看“现在该做什么”
6. 需要你决定时，只点一个按钮：
   - “重新跑一版”
   - “通过”
   - “驳回重写”
   - “推草稿”
7. 需要更深的监控、设置或反馈时，再打开高级页面

## 5. 后续边界

## 5. 之后的边界

Phase 7E 完成后，下一步应进入：

- Phase 7F
  - 更细粒度的任务成功率趋势图
  - 告警分级与去重
  - 告警静默与值班策略
