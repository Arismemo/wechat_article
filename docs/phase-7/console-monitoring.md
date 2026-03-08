# Phase 7A 统一控制台

更新时间：2026-03-08
状态：Active

## 1. 目标

Phase 7A 只解决一个问题：把现有任务监控能力收束成统一入口。

本阶段不做：

- 在线修改 `.env`
- 在线修改生产密钥
- 替代 Phase 5 的人工审核台
- 替代 Phase 6 的反馈运营台

## 2. 页面入口

- `GET /admin`
- `GET /admin/console`

与已有后台页分工：

- `/admin`
  - 单一统一入口
  - 通过页内切换进入监控、审核、反馈 3 个视图
- `/admin/console`
  - 总览、轮询、筛选、详情查看
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
- 当前列表统计卡片
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

## 4. 使用方式

1. 打开 `/admin`
2. 输入 `API_BEARER_TOKEN`
3. 默认先进入监控首页
4. 设置轮询秒数和筛选条件
5. 点击“立即刷新”
6. 在看板里选择任务，点“查看详情”
7. 如需人工动作，切到“审核台”
8. 如需反馈和实验查看，切到“反馈台”

## 5. 后续边界

Phase 7A 完成后，下一步应进入：

- Phase 7B
  - `system_settings` 表
  - 运行参数网页配置
  - 配置审计日志
- Phase 7C
  - 实时推送
  - 统计卡片与告警
  - 只读环境变量状态面板
