# Phase 6 反馈闭环

更新时间：2026-03-08

## 当前目标

Phase 6 第一刀先不接微信官方分析接口，先把“手工反馈导入 -> Prompt 实验聚合 -> 风格资产沉淀”打通。这样即使外部分析能力还没确认，系统也已经能开始积累效果数据。

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
  - `POST /internal/v1/style-assets`
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

用于沉淀已验证的标题方向、开头结构、段落骨架、转场句式等资产。当前先支持手工创建和列表查询，还没有接回 Phase 4 生成链路。

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
2. 如果未指定 `prompt_type/prompt_version`，会按当前 generation 模型推断：
   - `glm-5` / `phase4-fallback-template` -> `phase4_write / phase4-v1`
3. 如果未指定 `wechat_media_id`，会尝试回填该 generation 最近一次成功草稿的 `media_id`
4. 写入或覆盖 `publication_metrics`
5. 回算并更新 `prompt_experiments`
6. 写入任务级审计日志：`phase6.feedback.imported`

### 新建风格资产

调用 `POST /internal/v1/style-assets` 时：

- 支持手工指定 `asset_type/title/content/tags/weight`
- 可选关联 `source_task_id` 和 `source_generation_id`
- 如果带来源任务，会写入审计日志：`phase6.style_asset.created`

## 后台页

`/admin/phase6` 当前提供三块能力：

- 手工录入 T+1 / T+3 / T+7 指标
- 查看任务反馈快照
- 查看 Prompt 实验榜
- 创建与浏览风格资产

页面本身仍受可选 `ADMIN_USERNAME` / `ADMIN_PASSWORD` Basic Auth 保护；实际写操作仍要求 `API_BEARER_TOKEN`。

## 验证

本地已通过：

- `pytest -q tests/test_app_routes.py tests/test_feedback_api.py tests/test_task_workspace_api.py`
- `python3 -m compileall app tests`

当前自动化测试覆盖：

- Phase 6 路由注册
- `/admin/phase6` 页面渲染与 Basic Auth
- 手工导入反馈
- 同观察窗口重复导入覆盖更新
- Prompt 实验聚合
- 风格资产创建与查询

## 当前未做

- 微信官方分析接口对接
- 自动反馈 worker
- 将 `style_assets` 真正接回 Phase 4 生成 Prompt
- Prompt 版本从固定映射升级为真实版本表关联
- 增长优化器与自动策略推荐

## 下一步建议

1. 先在服务器部署这版 Phase 6，并用真实任务录一组 T+1 数据。
2. 再决定数据入口路线：
   - 微信分析接口
   - 后台 CSV / Excel 导入
   - 继续手工录入
3. 等样本量足够后，再把 `style_assets` 和 `prompt_experiments` 接回生成链路。
