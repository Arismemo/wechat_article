# Phase 6 反馈闭环

更新时间：2026-03-08

## 当前目标

Phase 6 先不强依赖微信官方分析接口，优先把“手工反馈导入 / 自动反馈同步 -> Prompt 实验聚合 -> 风格资产沉淀”打通。这样即使外部分析能力还没完全确认，系统也已经能开始积累效果数据。

## 本轮已完成

- 新增反馈数据表：
  - `publication_metrics`
  - `prompt_experiments`
  - `style_assets`
- 新增 migration：
  - `20260308_0004_add_phase6_feedback_tables.py`
- 新增反馈服务：
  - `app/services/feedback_service.py`
- 新增读取接口：
  - `GET /api/v1/tasks/{task_id}/feedback`
  - `GET /api/v1/feedback/experiments`
  - `GET /api/v1/feedback/style-assets`
- 新增写入接口：
  - `POST /internal/v1/tasks/{task_id}/import-feedback`
  - `POST /internal/v1/feedback/import-csv`
  - `POST /internal/v1/tasks/{task_id}/run-feedback-sync`
  - `POST /internal/v1/tasks/{task_id}/enqueue-feedback-sync`
  - `POST /internal/v1/feedback/enqueue-recent-sync`
  - `POST /internal/v1/style-assets`
- 新增自动反馈 worker：
  - `scripts/run_feedback_worker.py`
- 新增后台页：
  - `GET /admin/phase6`

## 数据模型说明

### publication_metrics

一条记录对应某个 `generation` 在某个观察窗口的表现快照。当前按 `generation_id + day_offset` 唯一约束，重复导入会覆盖更新，不会重复累计样本。

关键字段：

- `task_id`
- `generation_id`
- `wechat_media_id`
- `prompt_type`
- `prompt_version`
- `day_offset`
- `snapshot_at`
- `read_count`
- `like_count`
- `share_count`
- `comment_count`
- `click_rate`
- `source_type`
- `imported_by`
- `raw_payload`

### prompt_experiments

当前按 `prompt_type + prompt_version + day_offset` 聚合。每次导入 `publication_metrics` 后，会同步刷新对应实验行。

关键字段：

- `sample_count`
- `avg_read_count`
- `avg_like_count`
- `avg_share_count`
- `avg_comment_count`
- `avg_click_rate`
- `best_read_count`
- `latest_metric_at`
- `last_task_id`
- `last_generation_id`

### style_assets

用于沉淀已验证的标题方向、开头结构、段落骨架、转场句式等资产。当前已经支持接回 Phase 4 写稿 Prompt。

关键字段：

- `asset_type`
- `title`
- `content`
- `tags`
- `status`
- `weight`
- `source_task_id`
- `source_generation_id`

## 当前行为

### 手工导入反馈

调用 `POST /internal/v1/tasks/{task_id}/import-feedback` 时：

1. 如果未指定 `generation_id`，优先取最新 `accepted` generation，否则退回最新 generation。
2. 如果未指定 `prompt_type/prompt_version`，会优先读取 generation 已落库的真实版本字段。
3. 如果 generation 还没有真实版本字段，再回退到兼容映射：
   - `glm-5` / `phase4-fallback-template` -> `phase4_write / phase4-v1`
3. 如果未指定 `wechat_media_id`，会尝试回填该 generation 最近一次成功草稿的 `media_id`
4. 写入或覆盖 `publication_metrics`
5. 回算并更新 `prompt_experiments`
6. 写入任务级审计日志：`phase6.feedback.imported`

### CSV 批量导入反馈

调用 `POST /internal/v1/feedback/import-csv` 时：

1. 以 `csv.DictReader` 解析文本
2. 支持列：
   - `task_id`
   - `generation_id`
   - `day_offset`
   - `snapshot_at`
   - `wechat_media_id`
   - `read_count`
   - `like_count`
   - `share_count`
   - `comment_count`
   - `click_rate`
   - `prompt_type`
   - `prompt_version`
   - `source_type`
   - `imported_by`
   - `notes`
3. 如果请求里提供了 `default_task_id`，CSV 可省略 `task_id`
4. 全量导入采用单事务；任何一行非法会整批回滚并返回 `400`

### 自动反馈同步

调用 `POST /internal/v1/tasks/{task_id}/run-feedback-sync` 或由 `feedback_worker` 消费队列时：

1. 解析 `FEEDBACK_SYNC_PROVIDER`
2. 当前支持：
   - `disabled`：关闭自动同步
   - `mock`：本地联调和测试用 Provider
   - `http`：向外部 HTTP Provider 拉取反馈快照
3. 服务端会自动定位：
   - 最新 `accepted` generation
   - 该 generation 最近一次成功草稿的 `wechat_media_id`
4. 请求上游 Provider 时会发送：
   - `task_id`
   - `generation_id`
   - `prompt_type`
   - `prompt_version`
   - `wechat_media_id`
   - `draft_created_at`
   - `day_offsets`
5. Provider 返回的快照会复用现有 `import_publication_metric(...)` 幂等落库
6. 同一 `generation_id + day_offset` 仍然只保留一条快照；重复自动同步会覆盖更新，不会重复累计样本
7. 会写入审计日志：
   - `phase6.feedback.sync.enqueued`
   - `phase6.feedback.sync.completed`
   - `phase6.feedback.sync.failed`

### 自动同步队列

新增 Redis 队列：

- `FEEDBACK_SYNC_QUEUE_KEY`
- `FEEDBACK_SYNC_PROCESSING_KEY`
- `FEEDBACK_SYNC_PENDING_SET_KEY`

内部入口：

- `POST /internal/v1/tasks/{task_id}/enqueue-feedback-sync`
- `POST /internal/v1/feedback/enqueue-recent-sync`

当前批量扫描逻辑只会从最近成功推送草稿的任务里挑选候选，适合配合外部 cron / automation 每天触发一次。

### 新建风格资产

调用 `POST /internal/v1/style-assets` 时：

- 支持手工指定 `asset_type/title/content/tags/weight`
- 可选关联 `source_task_id` 和 `source_generation_id`
- 如果带来源任务，会写入审计日志：`phase6.style_asset.created`

## 后台页

`/admin/phase6` 当前提供四块能力：

- 手工录入 T+1 / T+3 / T+7 指标
- 自动同步当前任务反馈
- 扫描最近草稿并批量入队自动同步
- 批量粘贴 CSV 回填多条反馈
- 查看任务反馈快照
- 查看 Prompt 实验榜
- 创建与浏览风格资产

页面本身仍受可选 `ADMIN_USERNAME` / `ADMIN_PASSWORD` Basic Auth 保护；进入后台后默认复用当前 `admin_session`，不再要求在页面内手动输入 `API_BEARER_TOKEN`。

## 验证

本地已通过：

- `pytest -q tests/test_app_routes.py tests/test_feedback_api.py tests/test_task_workspace_api.py`
- `python3 -m compileall app tests`

当前自动化测试覆盖：

- Phase 6 路由注册
- `/admin/phase6` 页面渲染与 Basic Auth
- 手工导入反馈
- CSV 批量导入反馈
- 自动反馈同步
- 自动反馈批量入队
- CSV 非法行返回 `400`
- 同观察窗口重复导入覆盖更新
- Prompt 实验聚合
- 风格资产创建与查询

## 当前未做

- 微信官方分析接口对接
- Excel 文件上传与解析
- Prompt 版本进一步接入 `prompt_versions` 表，而不只是 generation 上的字符串字段
- 增长优化器与自动策略推荐

## 下一步建议

1. 先在服务器部署这版自动反馈入口，并为 `feedback_worker` 配好 Provider 环境变量。
2. 再决定真实生产 Provider：
   - 微信分析接口代理
   - 第三方统计服务
   - 内部手工维护的 HTTP 转换层
3. 如果运营更习惯文件流，再补 Excel 上传导入。
4. 等样本量足够后，再把 `prompt_experiments` 真正接回生成链路。
