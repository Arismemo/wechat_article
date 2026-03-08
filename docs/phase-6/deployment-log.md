# Phase 6 部署与验收记录

更新时间：2026-03-08

## 部署目标

将 Phase 6 第一版能力部署到服务器：

- 手工反馈导入
- Prompt 实验榜查询
- 风格资产查询与创建
- `/admin/phase6` 后台页

## 代码版本

- Git commit：`48b357b`
- 提交信息：`Start phase 6 feedback loop`

## 本地验证

- `pytest -q` -> `41 passed`
- `python3 -m compileall app tests` -> 通过

## 服务器部署过程

服务器当前工作树已经恢复为 Git 主线，因此先执行：

- `git push origin main`
- 远端 `git pull --ff-only origin main`

这次没有引入新的系统依赖，只新增应用代码和 migration。原计划尝试“本地预构建镜像 -> 远端 docker load”，但当前网络下镜像传输仍然偏慢；远端直接 `docker compose build api` 也没有命中依赖缓存，重新开始拉 Python 包与 Playwright。

因此本次最终采用的变通方案是：

1. 远端先 `git pull` 获取最新工作树
2. 将远端工作树中的 `app/`、`migrations/` 与 `alembic.ini` 直接 `docker cp` 到现有 `wechat_artical_api` 容器
3. 重启 `api`
4. 执行 `docker exec wechat_artical_api alembic upgrade head`
5. 再次重启 `api`

这个方案只用于“无新增依赖、纯应用层改动”的快速收口，不替代正式的镜像发布链路。

## migration

已成功执行：

- `20260308_0004_add_phase6_feedback_tables`

新增表：

- `publication_metrics`
- `prompt_experiments`
- `style_assets`
- 后续追加：
  - `20260308_0005_add_generation_prompt_version_columns`

## 服务器 smoke test

### 容器状态

- `api` healthy
- `phase2_worker` running
- `phase3_worker` running
- `phase4_worker` running

### 健康检查

- `GET /healthz` -> `{"status":"ok"}`

### Phase 6 接口验收

服务器实际验收任务：

- `task_id`: `baa5ba24-09e0-4d8d-bc60-7da9f31fbb4b`
- `generation_id`: `62b7c88f-5ffb-4178-ad89-ac51ddab1d47`

验收步骤：

1. `GET /api/v1/feedback/experiments?limit=3`
   - 初始结果：`[]`
2. `POST /internal/v1/tasks/{task_id}/import-feedback`
   - 请求窗口：`T+1`
   - 请求值：
     - `read_count=1234`
     - `like_count=77`
     - `share_count=12`
     - `comment_count=3`
     - `click_rate=0.1789`
   - 返回：
     - `status=draft_saved`
     - `prompt_type=phase4_write`
     - `prompt_version=phase4-v1`
     - `sample_count=1`
3. `GET /api/v1/tasks/{task_id}/feedback`
   - 成功返回该任务已导入反馈
   - 自动回填 `wechat_media_id=mid-08788bbf`
4. `GET /api/v1/feedback/experiments?limit=3`
   - 成功返回实验聚合：
     - `avg_read_count=1234.0`
     - `avg_like_count=77.0`
     - `avg_share_count=12.0`
     - `avg_comment_count=3.0`
     - `avg_click_rate=0.1789`
5. `GET /admin/phase6`
   - Basic Auth 校验通过
   - 页面内容命中 `Phase 6 反馈台`

## 结论

Phase 6 第一版已经完成服务器收口，当前可用闭环是：

`review_passed / draft_saved 任务 -> 手工导入 T+1/T+3/T+7 指标 -> Prompt 实验榜聚合 -> 风格资产沉淀`

## 追加联调：phase4-v2 反馈回写

在将 `style_assets` 接回 Phase 4 后，追加做了一轮 “新 prompt 版本 -> 反馈导入” 联调，用来确认 Phase 6 不会再把新 generation 记成旧版 `phase4-v1`。

追加验收任务：

- `task_id`: `f703c3ef-e358-48ab-936d-187418c584c5`
- `generation_id`: `71c6bc73-a527-4e4a-be42-31b02b542008`

追加验收结果：

1. `GET /api/v1/tasks/{task_id}/workspace`
   - 返回最新 generation：
     - `prompt_type=phase4_write`
     - `prompt_version=phase4-v2`
2. `POST /internal/v1/tasks/{task_id}/import-feedback`
   - 请求窗口：`T+1`
   - 请求值：
     - `read_count=1666`
     - `like_count=101`
     - `share_count=18`
     - `comment_count=6`
     - `click_rate=0.2031`
   - 返回：
     - `metric_id=917281bf-3b2e-4710-9c61-cedb0421f0cd`
     - `prompt_type=phase4_write`
     - `prompt_version=phase4-v2`
3. `GET /api/v1/tasks/{task_id}/feedback`
   - 返回该条 feedback 的 `prompt_version=phase4-v2`

结论：

- 新一轮 Phase 4 成稿已经能被 Phase 6 以真实 `phase4-v2` 版本回收
- Prompt 实验榜后续可以开始对比 `phase4-v1` 与 `phase4-v2`

## 后续建议

1. 把 `style_assets` 接回 Phase 4 生成 Prompt
2. 增加批量导入能力，例如 CSV / Excel
3. 再决定是否对接微信官方分析接口
