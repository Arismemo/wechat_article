# Phase 7 运行参数与环境状态

更新时间：2026-03-10
状态：Phase 7F Completed

## 1. 目标

Phase 7B 先把少量可热修改的运行参数从纯 `.env` 提升为“网页可配置 + 数据库存储 + 审计留痕”；Phase 7D 再把 `.env` 的只读状态和测试告警入口接回同一个设置页；Phase 7F 补上 LLM 供应商、模型槽位选择和一键连通性测试。

本阶段不做：

- 在线编辑整份 `.env`
- 修改数据库、Redis、微信 Secret 等基础设施配置
- 角色权限和多用户审批流

补充说明：

- LLM 供应商的 `API Key` 现在允许通过后台页写入数据库配置，但读取时只返回掩码预览，不回显明文。
- 其他第三方密钥仍然不支持网页查看或修改。

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

Phase 7F 新增的 LLM 相关 key：

- `llm.providers`
- `llm.active_provider`
- `llm.analyze_model`
- `phase4.write_model`
- `phase4.review_model`

其中：

- `llm.providers` 保存后台页新增的 LLM 供应商配置列表，包含 `provider_id / vendor / label / api_base / api_key / models`
- `llm.active_provider` 保存当前选中的供应商
- `llm.analyze_model` 保存 Phase 3 分析模型
- `phase4.write_model` / `phase4.review_model` 继续沿用原 key，但现在同时作为统一 LLM 运行时的写稿 / 审稿模型槽位

## 3. 第一批可网页配置的参数

当前开放的 key：

- `phase4.write_model`
- `phase4.review_model`
- `phase4.auto_push_wechat_draft`
- `feedback.sync_provider`
- `feedback.sync_day_offsets`

Phase 7F 额外开放一组自定义 LLM 配置：

- 供应商列表
- 当前供应商选择
- 分析 / 写稿 / 审稿模型选择

其中前者存入 `llm.providers`，后者分别存入 `llm.active_provider` / `llm.analyze_model` / `phase4.write_model` / `phase4.review_model`。

除这组 LLM 配置外，其他 key 只覆盖运行时行为，不会覆盖：

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
- `GET /api/v1/admin/llm-config`
- `PUT /api/v1/admin/llm-config`
- `POST /api/v1/admin/llm-test`
- `GET /api/v1/admin/runtime-status`
- `POST /api/v1/admin/alerts/test`

认证：

- 数据接口仍支持 `API_BEARER_TOKEN`
- 通过后台页进入后，页面动作默认复用 `admin_session`

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

LLM 配置更新示例：

```json
{
  "providers": [
    {
      "provider_id": "openrouter-main",
      "vendor": "OPENROUTER",
      "label": "OpenRouter 主线路",
      "api_base": "https://openrouter.ai/api/v1",
      "api_key": "sk-or-...",
      "models": ["openai/gpt-4.1-mini", "openai/gpt-4.1"]
    }
  ],
  "active_provider_id": "openrouter-main",
  "analyze_model": "openai/gpt-4.1-mini",
  "write_model": "openai/gpt-4.1",
  "review_model": "openai/gpt-4.1-mini",
  "operator": "admin-console",
  "note": "切到 OpenRouter 验证"
}
```

LLM 连通性测试：

```json
{
  "provider_id": "openrouter-main",
  "model": "openai/gpt-4.1-mini",
  "operator": "admin-console",
  "note": "改完配置后做连通性测试"
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
- 页面动作默认复用当前后台会话
- 支持集中管理 LLM 供应商列表
- 支持切换当前供应商与分析 / 写稿 / 审稿模型
- 支持对指定供应商发送最小测试指令
- 支持查看默认值、数据库覆盖值和实际生效值
- 支持保存覆盖值
- 支持恢复默认
- 支持查看 `.env` 只读环境状态
- 支持发送测试告警验证 `ALERT_WEBHOOK_URL`

## 6. 运行时接线

当前已接入的服务：

- `Phase3PipelineService`
  - 分析模型
  - brief 生成使用的写稿模型
- `Phase4PipelineService`
  - 统一 LLM Provider / API Base / API Key
  - 写稿模型
  - 审稿模型
  - AI 去痕沿用写稿模型
  - 自动推草稿开关
- `FeedbackSyncService`
  - 自动反馈 Provider
  - 默认 day offsets

额外补充：

- `LLMService` 现在会在上游返回 `4xx/5xx` 时把响应体摘要带进异常消息，便于审计日志直接看到 provider 的错误正文。

这意味着这套能力不只是“多一个设置页”，而是已经真实影响运行时请求和排障可见性。

## 7. 审计日志

每次保存 / 恢复默认，都会写入 `audit_logs`：

- `phase7.system_setting.updated`
- `phase7.system_setting.reset`

Phase 7F 额外会写：

- `phase7.llm_runtime.updated`
- `phase7.llm.tested`

当前 `task_id` 为空，`operator` 与 `note` 会写入 payload。

## 8. Phase 7D 新增的只读状态面板

设置页现在额外展示：

- 应用基础配置
- 基础设施连接
- 访问控制与密钥
- 外部集成状态
- 告警 Webhook 是否已配置

注意：

- 密钥类值不展示明文
- 普通 URL 只显示到 `scheme://host`
- 该面板只读，不直接改写 `.env`

## 9. 当前边界

当前仍未做：

- 配置变更 diff 历史页
- 按环境区分不同设置集
- 更细粒度的权限模型
- 更完整的后台多用户登录体系
- 基于供应商能力自动约束可选模型列表之外的高级参数（如 tools / response_format / reasoning 选项）

## 10. 发布建议

- 生产环境建议始终配置：
  - `ADMIN_USERNAME`
  - `ADMIN_PASSWORD`
- 如果未配置后台 Basic Auth，后台页会退化为基于 `API_BEARER_TOKEN` 的 `admin_session` 会话，这适合本地开发或应急环境，但不建议作为正式生产默认形态。
