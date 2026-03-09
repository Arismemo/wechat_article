# 阶段 4 生成、审稿与重生成

更新时间：2026-03-09
状态：已收口并纳入 v1.1.0

## 1. 目标

阶段 4 的目标，是在阶段 3 已产出的 `content_brief` 基础上，建立最小可运行的创作与卡口链路：

`brief_ready -> generation -> review -> review_passed / needs_regenerate / needs_manual_review`

当前正式范围覆盖：

- 基于 `content_brief`、`article_analysis`、原文与入选素材生成新稿
- 对新稿做结构化审稿与评分
- 对 `revise` 结果自动修订一次
- 对高 AI 痕迹稿件做定点 humanize pass 并自动复审
- 将写稿、审稿、AI 去痕、人工采用版本等信息聚合到 `GET /api/v1/tasks/{task_id}/workspace`
- 推微信草稿与反馈同步优先跟随“当前采用版本”，而不再只依赖 latest accepted generation
- 支持将最新 `review_passed` 稿件手动推送到微信草稿箱
- 支持通过 `PHASE4_AUTO_PUSH_WECHAT_DRAFT=true` 在 `review_passed` 后自动推送

## 2. 本轮边界

### 2.1 本轮要做

- `POST /internal/v1/tasks/{task_id}/run-phase4`
- `POST /internal/v1/tasks/{task_id}/enqueue-phase4`
- `POST /internal/v1/phase4/ingest-and-run`
- `POST /internal/v1/phase4/ingest-and-enqueue`
- `GET /api/v1/tasks/{task_id}/draft`
- `POST /internal/v1/tasks/{task_id}/push-wechat-draft`
- `phase4_worker`
- `generations`、`review_reports` 正式落库

## 3. 当前已实现范围

- `Phase4PipelineService`
  - 若缺少 Phase 3 结果，会先自动补跑 Phase 3
  - 基于 `content_brief`、原文分析、原文与入选素材生成新稿
  - 会额外读取 `style_assets` 中的 active 资产，并把已验证的开头、标题方向、结构资产注入写稿 Prompt
  - 审稿结论支持 `pass / revise / reject`
  - `revise` 会自动修订一次并重新审稿
  - 当审稿返回较高 `ai_trace_score` 且不命中 `reject` 时，会触发定点 humanize pass
  - humanize 会按 `rewrite_targets` 只改指定 block，随后再做一轮审稿
  - 审稿结果会额外产出：
    - `ai_trace_score`
    - `ai_trace_patterns`
    - `rewrite_targets`
    - `voice_summary`
    - `humanize_applied`
  - humanize 流程会写入这些审计动作：
    - `phase4.humanize.started`
    - `phase4.humanize.completed`
    - `phase4.humanize.skipped`
    - `phase4.humanize.failed`
- `Phase4QueueService`
- `scripts/run_phase4_worker.py`
- 内部接口：
  - `POST /internal/v1/tasks/{task_id}/run-phase4`
  - `POST /internal/v1/tasks/{task_id}/enqueue-phase4`
  - `POST /internal/v1/phase4/ingest-and-run`
  - `POST /internal/v1/phase4/ingest-and-enqueue`
- 查询接口：
  - `GET /api/v1/tasks/{task_id}/draft`
- 微信草稿箱推送接口：
  - `POST /internal/v1/tasks/{task_id}/push-wechat-draft`
- 自动推送开关：
  - `PHASE4_AUTO_PUSH_WECHAT_DRAFT=true`
  - 仍需同时满足 `WECHAT_ENABLE_DRAFT_PUSH=true`
- `docker-compose` 已纳入 `phase4_worker`
- 本地测试已覆盖：
  - 正常生成并审稿通过
  - `revise -> 自动修订一次 -> 审稿通过`
  - 高 AI 痕迹触发定点 humanize -> 复审通过
  - 当前采用版本优先于 latest accepted generation 的推稿与反馈链路
  - `workspace` 聚合时间线、AI 去痕诊断和采用版本解析

## 4. 服务器验收结果

`2026-03-07` 已完成首轮服务器 smoke test，验收结论如下：

- `POST /internal/v1/phase4/ingest-and-run`
  - 已成功产出 `generation` 和 `review_report`
  - 低分稿件会被打到 `needs_regenerate`
- `POST /internal/v1/phase4/ingest-and-enqueue`
  - 已成功由 `phase4_worker` 消费
  - 真实跑通了 `revise -> 自动修订一次 -> review_passed`
- `GET /api/v1/tasks/{task_id}/draft`
  - 已可返回最新 generation 与最新 review 结果
- 追加收口验证：
  - 将写稿超时拆为 `LLM_WRITE_TIMEOUT_SECONDS=180`
  - 将审稿超时拆为 `LLM_REVIEW_TIMEOUT_SECONDS=90`
  - 复跑后已真实产出 `model_name=glm-5` 的 accepted generation
  - `POST /internal/v1/tasks/{task_id}/push-wechat-draft` 已成功返回 `draft_saved`

详细部署记录见：

- `docs/phase-4/deployment-log.md`

### 2.2 本轮不做

- 不做后台审稿台
- 不做多轮自动重生成
- 不做相似度向量检索和外部事实校验服务

## 5. 设计约束

- Phase 4 必须允许直接从任务链接启动；若缺少 Phase 3 结果，服务端应自动补跑 Phase 3。
- 写作输出必须落 `generations`，不能只返回临时字符串。
- 审稿输出必须落 `review_reports`，并带出明确决策：
  - `pass`
  - `revise`
  - `reject`
- 自动修订最多执行一次；再次不通过则转人工。
- 新 generation 会真实落库：
  - `prompt_type`
  - `prompt_version`
  当前写稿版本为 `phase4-v3`
- 审稿元数据继续复用 `review_reports.issues / suggestions`，不额外引入新表结构。
- 工作台与任务接口要能稳定透出结构化审稿元数据，不能只保留前端文案。
- AI 去痕诊断文案必须和真实代码判定条件一致，不能由前端自行猜测。
- `workspace` 中的时间线、AI 去痕诊断、采用版本解析由后端统一聚合，避免多个页面各自拼装。

## 5.1 AI 去痕触发与诊断

当前 humanize pass 的真实触发条件为：

- `ai_trace_score >= 70`
- 审稿结果中必须存在 `rewrite_targets`
- `policy_risk_score <= PHASE4_POLICY_RISK_MAX`
- `factual_risk_score <= PHASE4_FACTUAL_RISK_MAX`

当前页面和接口会明确区分这些状态：

- `not_triggered`
- `running`
- `completed`
- `skipped`
- `failed`

当前已结构化输出的主要原因包括：

- `ai_trace_below_threshold`
- `no_rewrite_targets`
- `policy_risk_too_high`
- `factual_risk_too_high`
- `no_valid_rewrites`
- `markdown_unchanged`

其中：

- `phase4.humanize.completed` 会同时记录 `generation_id` 与 `source_generation_id`
- `GET /api/v1/tasks/{task_id}/workspace` 会把这些信息汇总为：
  - generation 级 `ai_trace_diagnosis`
  - 任务级 `timeline`
  - 当前采用版本 `selected_generation`

## 6. 状态流

- `generating`
- `reviewing`
- `review_passed`
- `needs_regenerate`
- `needs_manual_review`
- `generate_failed`
- `review_failed`

## 7. 当前限制

- 生产环境默认仍不会把 Phase 4 成稿在 `review_passed` 后自动推到微信草稿箱，需显式打开 `PHASE4_AUTO_PUSH_WECHAT_DRAFT`
- Phase 4 本身不提供正文编辑器，人工比较、采用和推稿判断仍在 Phase 5 完成
- 审稿 fallback 目前是启发式规则，不是外部事实校验服务
- 定点 humanize 目前仍属于单轮、按块改写，不做整稿多轮风格重写

## 8. 验收标准

- 每个 `brief_ready` 任务能产出一版 `generation`
- 每版 `generation` 都能得到一份 `review_report`
- `revise` 能触发一次自动修订
- 审稿低于阈值的稿件不会进入 `review_passed`
- `GET /api/v1/tasks/{task_id}/draft` 可返回最新生成稿和最新审稿结果
- `GET /api/v1/tasks/{task_id}/workspace` 可返回 `ai_trace_score`、`rewrite_targets`、`humanize_applied` 等结构化审稿元数据
