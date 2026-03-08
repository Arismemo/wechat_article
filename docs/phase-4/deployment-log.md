# 阶段 4 部署与验收记录

更新时间：2026-03-08
状态：已完成服务器验收并闭合入草稿箱链路，且已追加接入 style_assets 的 prompt v2 验证

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

## 7. 追加收口验证

- 为解决 Phase 4 写作总是回退到 `phase4-fallback-template` 的问题，本轮补充了分档超时配置：
  - `LLM_WRITE_TIMEOUT_SECONDS=180`
  - `LLM_REVIEW_TIMEOUT_SECONDS=90`
- 追加复跑同一 `task_id` 后，新增 `version 5`：
  - `generation_id`: `6d4b12f3-5748-49d2-b2f5-88b82fda69f0`
  - `model_name`: `glm-5`
  - `review_report_id`: `80fabc3e-f6e7-4721-990b-16dbcea971c7`
  - `review_decision`: `pass`
  - `status`: `review_passed`
- 追加验证手动推送微信草稿箱：
  - 接口：`POST /internal/v1/tasks/{task_id}/push-wechat-draft`
  - 结果：`status=draft_saved`
  - `wechat_media_id`: `PyYQ74YwFFGh2wyA3BOdvzfhTwfMorm03-7lHNCD8etRTJjckK5xQ0LA24AFETkJ`

## 8. 当前结论

Phase 4 当前已经具备服务器闭环：

`content_brief -> generation -> review -> review_passed -> push-wechat-draft -> draft_saved`

其中“入草稿箱”目前仍是手动触发内部接口，不是 `review_passed` 后自动推送。

## 9. Prompt v2 追加验证

为把 Phase 6 的 `style_assets` 真正接回 Phase 4，本轮追加上线：

- `Generation.prompt_type`
- `Generation.prompt_version`
- 写稿 Prompt 新版本：`phase4-v2`
- active `style_assets` 自动注入写稿 Prompt

部署方式仍采用：

1. 远端 `git pull`
2. 将 `app/`、`migrations/` 与 `alembic.ini` 注入现有 `api` 容器
3. 执行 `alembic upgrade head`

新增 migration：

- `20260308_0005_add_generation_prompt_version_columns`

追加验收任务：

- `task_id`: `f703c3ef-e358-48ab-936d-187418c584c5`

追加验收步骤：

1. 先写入两条风格资产：
   - `opening_hook`: `dd624352-b966-436a-bdb6-bcd716ebcd99`
   - `outline`: `8ac602b9-da9a-436c-b46d-0216e3cb947b`
2. 调用：
   - `POST /internal/v1/tasks/{task_id}/run-phase4`
3. 返回结果：
   - `status=review_passed`
   - `generation_id=71c6bc73-a527-4e4a-be42-31b02b542008`
   - `review_report_id=43414589-2d8b-48f2-bf04-20949f2a0763`
   - `decision=pass`
4. 读取：
   - `GET /api/v1/tasks/{task_id}/workspace`
5. 验证结果：
   - 最新 generation `prompt_type=phase4_write`
   - 最新 generation `prompt_version=phase4-v2`
   - 最新 generation `model_name=glm-5`
   - `phase4.generation.started` 与 `phase4.generation.completed` 审计日志都带出 `style_asset_ids`

结论：

- Phase 4 已不再只是“能存风格资产”，而是已经真实消费 `style_assets`
- 新 generation 已可以在 Phase 5 / Phase 6 中被识别为 `phase4-v2`
