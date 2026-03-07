# 阶段 4 部署与验收记录

更新时间：2026-03-07
状态：已完成首轮服务器验收

## 1. 部署范围

- 已上线服务：
  - `api`
  - `phase4_worker`
  - `postgres`
  - `redis`
- 本轮未做数据库 migration。
- 本轮仍采用“同步代码到服务器目录 + 将新代码注入现有容器 + 固化镜像”的方式部署，避免远端重建 Playwright。

## 2. 验收样例

- 测试文章：
  - `https://mp.weixin.qq.com/s/OE0GJvalYOl9OJvQIg3bew`
- 任务：
  - `task_id`: `f703c3ef-e358-48ab-936d-187418c584c5`
- 该 URL 已存在历史任务，Phase 4 验收命中去重，复用了同一个 `task_id`

## 3. 同步链路验收

- 接口：
  - `POST /internal/v1/phase4/ingest-and-run`
- 结果：
  - `status`: `needs_regenerate`
  - `generation_id`: `069f2afe-d21d-4eba-a4f2-58bddcf6f54f`
  - `review_report_id`: `f3cec839-82c6-4705-8f0d-11b5245196ae`
  - `decision`: `reject`
- 结论：
  - 同步链路已成功生成稿件并写入 `generations`
  - 审稿卡口已成功挡下低分稿件，没有误进 `review_passed`

## 4. 异步链路验收

- 接口：
  - `POST /internal/v1/phase4/ingest-and-enqueue`
- 结果：
  - `status`: `review_passed`
  - 最新 `generation_id`: `31c5ddab-6cdc-47b8-880e-c7bc25b58ad1`
  - 最新 `review_report_id`: `9b8e0b30-5140-43dd-bc1d-2188f62d8299`
  - 最新 `decision`: `pass`
  - 最新 `generation_version`: `3`
- 结论：
  - `phase4_worker` 已成功消费异步任务
  - “审稿返回 `revise` -> 自动修订一次 -> 再审稿”链路已真实跑通
  - 最终任务状态为 `review_passed`

## 5. Generation / Review 轨迹

- `version 1`
  - `generation_id`: `069f2afe-d21d-4eba-a4f2-58bddcf6f54f`
  - `model_name`: `phase4-fallback-template`
  - `review_decision`: `reject`
  - `score_overall`: `25.75`
- `version 2`
  - `generation_id`: `9732defe-74a6-4968-96b0-e984a4764b80`
  - `model_name`: `phase4-fallback-template`
  - `review_decision`: `revise`
  - `score_overall`: `44.5`
- `version 3`
  - `generation_id`: `31c5ddab-6cdc-47b8-880e-c7bc25b58ad1`
  - `model_name`: `phase4-fallback-template`
  - `review_decision`: `pass`
  - `score_overall`: `84.1725`

## 6. 关键验收结论

- `GET /api/v1/tasks/{task_id}/draft` 已能返回最新 `generation` 与 `review_report`
- 同步链路验证了“低质稿件被挡下”
- 异步链路验证了“自动修订一次并通过审稿”
- `phase4_worker` 已在服务器稳定运行

## 7. 当前结论

Phase 4 初版已经具备服务器闭环：

`content_brief -> generation -> review -> reject/revise/pass -> 状态回写`

下一步可以继续把 `review_passed` 的最新 generation 接回微信草稿箱推送，形成真正的“研究 -> 写稿 -> 审稿 -> 入草稿箱”一体链路。
