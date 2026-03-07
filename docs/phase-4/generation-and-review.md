# 阶段 4 生成、审稿与重生成

更新时间：2026-03-07
状态：已完成首轮服务器验收

## 1. 目标

阶段 4 的目标，是在阶段 3 已产出的 `content_brief` 基础上，建立最小可运行的创作与卡口链路：

`brief_ready -> generation -> review -> review_passed / needs_regenerate / needs_manual_review`

本轮实现范围只覆盖：

- 基于 `content_brief`、`article_analysis`、原文与入选素材生成新稿
- 对新稿做结构化审稿与评分
- 对 `revise` 结果自动修订一次
- 仍不把 Phase 4 生成稿自动推送到微信草稿箱

## 2. 本轮边界

### 2.1 本轮要做

- `POST /internal/v1/tasks/{task_id}/run-phase4`
- `POST /internal/v1/tasks/{task_id}/enqueue-phase4`
- `POST /internal/v1/phase4/ingest-and-run`
- `POST /internal/v1/phase4/ingest-and-enqueue`
- `GET /api/v1/tasks/{task_id}/draft`
- `phase4_worker`
- `generations`、`review_reports` 正式落库

## 3. 当前已实现范围

- `Phase4PipelineService`
  - 若缺少 Phase 3 结果，会先自动补跑 Phase 3
  - 基于 `content_brief`、原文分析、原文与入选素材生成新稿
  - 审稿结论支持 `pass / revise / reject`
  - `revise` 会自动修订一次并重新审稿
- `Phase4QueueService`
- `scripts/run_phase4_worker.py`
- 内部接口：
  - `POST /internal/v1/tasks/{task_id}/run-phase4`
  - `POST /internal/v1/tasks/{task_id}/enqueue-phase4`
  - `POST /internal/v1/phase4/ingest-and-run`
  - `POST /internal/v1/phase4/ingest-and-enqueue`
- 查询接口：
  - `GET /api/v1/tasks/{task_id}/draft`
- `docker-compose` 已纳入 `phase4_worker`
- 本地测试已覆盖：
  - 正常生成并审稿通过
  - `revise -> 自动修订一次 -> 审稿通过`

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

详细部署记录见：

- `docs/phase-4/deployment-log.md`

### 2.2 本轮不做

- 不做自动推微信草稿箱
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

## 6. 状态流

- `generating`
- `reviewing`
- `review_passed`
- `needs_regenerate`
- `needs_manual_review`
- `generate_failed`
- `review_failed`

## 7. 当前限制

- 仍未把 Phase 4 成稿自动推到微信草稿箱
- 仍未做后台审稿台与人工重生成页
- 审稿 fallback 目前是启发式规则，不是外部事实校验服务

## 8. 验收标准

- 每个 `brief_ready` 任务能产出一版 `generation`
- 每版 `generation` 都能得到一份 `review_report`
- `revise` 能触发一次自动修订
- 审稿低于阈值的稿件不会进入 `review_passed`
- `GET /api/v1/tasks/{task_id}/draft` 可返回最新生成稿和最新审稿结果
