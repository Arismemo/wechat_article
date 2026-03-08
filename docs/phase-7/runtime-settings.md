# Phase 7B 运行参数设置

更新时间：2026-03-08
状态：Active

## 1. 目标

Phase 7B 只做一件事：把少量可热修改的运行参数从纯 `.env` 提升为“网页可配置 + 数据库存储 + 审计留痕”。

本阶段不做：

- 在线编辑整份 `.env`
- 在线显示或修改第三方密钥
- 修改数据库、Redis、微信 Secret 等基础设施配置
- 角色权限和多用户审批流

## 2. 数据模型

新增：

- `system_settings`

字段：

- `key`
- `value`
- `created_at`
- `updated_at`

当前仅保存“数据库覆盖值”。实际运行时的读取顺序是：

1. `system_settings`
2. `.env`

也就是说：

- 没有数据库覆盖时，系统继续读环境变量
- 恢复默认时，会删除数据库覆盖值，而不是把 `.env` 重写一遍

## 3. 第一批可网页配置的参数

当前开放的 key：

- `phase4.write_model`
- `phase4.review_model`
- `phase4.auto_push_wechat_draft`
- `feedback.sync_provider`
- `feedback.sync_day_offsets`

这些 key 只覆盖运行时行为，不会覆盖：

- `LLM_API_KEY`
- `LLM_PROVIDER`
- `WECHAT_APP_SECRET`
- `API_BEARER_TOKEN`
- `FEEDBACK_SYNC_HTTP_URL`
- `FEEDBACK_SYNC_API_KEY`

## 4. API

新增：

- `GET /api/v1/admin/settings`
- `GET /api/v1/admin/settings/{key}`
- `PUT /api/v1/admin/settings/{key}`

认证：

- 仍然使用 `API_BEARER_TOKEN`

`PUT` 请求体：

```json
{
  "value": "glm-5",
  "reset_to_default": false,
  "operator": "admin-console",
  "note": "切到新模型做验证"
}
```

如果要恢复默认：

```json
{
  "reset_to_default": true,
  "operator": "admin-console"
}
```

## 5. 页面入口

新增：

- `GET /admin/settings`

统一入口 `/admin` 现在包含 4 个视图：

- 监控首页
- 审核台
- 反馈台
- 设置

页面特性：

- 仍需先通过 Basic Auth 进入 `/admin/*`
- 页面内写操作仍需手动输入 `API_BEARER_TOKEN`
- 支持查看默认值、数据库覆盖值和实际生效值
- 支持保存覆盖值
- 支持恢复默认

## 6. 运行时接线

当前已接入的服务：

- `Phase4PipelineService`
  - 写稿模型
  - 审稿模型
  - 自动推草稿开关
- `FeedbackSyncService`
  - 自动反馈 Provider
  - 默认 day offsets

这意味着 Phase 7B 不是“只做设置页”，而是这批设置已经真实影响运行时逻辑。

## 7. 审计日志

每次保存 / 恢复默认，都会写入 `audit_logs`：

- `phase7.system_setting.updated`
- `phase7.system_setting.reset`

当前 `task_id` 为空，`operator` 与 `note` 会写入 payload。

## 8. 当前边界

当前仍未做：

- 只读环境变量状态面板
- 密钥是否已配置的可视化
- 配置变更 diff 历史页
- 按环境区分不同设置集

这些属于后续的 Phase 7C / 生产化增强项。
