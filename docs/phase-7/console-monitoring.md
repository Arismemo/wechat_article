# Phase 7 统一控制台

更新时间：2026-03-10
状态：Phase 7F Completed

## 1. 目标

Phase 7A 先解决“统一入口”，Phase 7B 再接“运行参数设置”，Phase 7C 补上“实时流和统计卡片”，Phase 7D 再补“异常/成功率卡片、告警入口和环境状态面板”，Phase 7E 继续接上“队列深度与 worker 心跳观测”，Phase 7F 则把这些观测整理成“趋势 + 分级告警 + 临时静默”的最小可用排障面板。

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
- 后台动作默认复用 `admin_session`
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
- 当前采用版本
  - 默认优先展示当前采用版本，而不是盲目展示 latest generation
- 同题参考文章摘要
- AI 去痕诊断摘要
- 流水线时间线摘要
- 最近审计轨迹

`/admin/console` 与 `GET /api/v1/tasks/{task_id}/workspace` 现在复用同一份后端聚合逻辑，避免监控页和审核页出现字段漂移。

### 3.4 监控快照接口

Phase 7C 新增：

- `GET /api/v1/admin/monitor/snapshot`
  - 需要 `API_BEARER_TOKEN`
  - 同时返回：
    - 当前筛选下的统计摘要
    - 最近任务列表
    - 当前选中任务的聚合详情

当携带 `selected_task_id` 时，聚合详情会额外包含：

- `related_articles`
- `selected_generation`
- `timeline`
- generation 级 `ai_trace_diagnosis`

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

### 3.8 Phase 7F 补充

本阶段继续补：

- 最近 24 小时趋势
  - `snapshot.trends`
  - 固定返回最近 24 小时的 8 个 3 小时桶
  - 每个桶包含：
    - `submitted`
    - `review_outcomes`
    - `review_successes`
    - `review_success_rate`
    - `auto_push_candidates`
    - `auto_push_successes`
    - `auto_push_success_rate`
    - `failed`
- 分级告警
  - `snapshot.alerts`
  - 当前最小覆盖：
    - worker 观测不可用
    - worker `stale / offline`
    - 卡住任务
    - 失败任务
  - 每条告警都会返回稳定的：
    - `key`
    - `dedupe_key`
    - `level`
    - `title`
    - `summary`
    - `detail`
    - `count`
    - `action_label`
    - `action_href`
- 前端临时静默
  - `/admin/console` 现在支持把单条告警静默 6 小时
  - 静默只保存在浏览器 `localStorage`
  - 静默不会改动后端任务状态、队列状态或真实告警来源
  - 页面支持“一键恢复全部静默”

### 3.9 当前采用版本与监控一致性

Phase 5 新增“采用此版本”后，以下链路都会优先跟随当前采用版本，而不是固定取 latest accepted generation：

- 微信草稿推送
- 反馈同步
- 监控快照中的 `workspace.selected_generation`

这样 `/admin` 与 `/admin/console` 查看到的聚合任务详情，会与 Phase 5 审核台看到的当前采用版本保持一致。

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

## 5. 当前边界

Phase 7F 已经补齐“趋势 + 分级告警 + 临时静默”的第一刀，但当前仍然保留这些边界：

- 静默只在当前浏览器生效，不做后端共享值班策略
- 告警仍然是基于监控快照实时计算，不做单独告警表或历史归档
- 趋势仍按固定 `24h / 3h` 视角展示，还不支持自定义窗口和多维钻取
- 真实外发告警仍只保留测试入口，尚未把分级结果接回 webhook 推送策略
