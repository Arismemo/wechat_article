# v1.1.1 发布说明

更新时间：2026-03-10
状态：Preparing

## 1. 发布结论

`v1.1.1` 是基于 `v1.1.0` 的补丁发布，范围只覆盖 TP-01 ~ TP-04 的发布收口，不把整份 post-`v1.1.0` 路线图视为已完成。

这一版重点把此前已在本地实现的 4 个问题真正发布到线上：

- 参考文章系统给出具体链接，并支持点击查看
- 驳回重写时可查看历史稿并做人工选择
- 有地方查看文章处理流水线的详细日志或关键信息
- AI 去痕未触发时，能明确看到原因

## 2. 相对 v1.1.0 的新增与变化

### 2.1 工作区聚合与当前采用版本

- `GET /api/v1/tasks/{task_id}/workspace` 新增：
  - `related_articles`
  - `selected_generation`
  - `timeline`
  - generation 级 `ai_trace_diagnosis`
  - `is_selected`
  - `draft_saved`
  - `wechat_media_id`
- 新增 `TaskWorkspaceQueryService`，统一 `/api/v1/tasks/{task_id}/workspace` 与 admin monitor 的聚合逻辑
- 新增 `TaskGenerationSelectionService`，通过审计日志解析“当前采用版本”

### 2.2 Phase 5 审核台

- `/admin/phase5` 现在可以：
  - 点击查看参考文章原文
  - 查看当前采用版本
  - 对历史稿执行“采用此版本”
  - 查看 AI 去痕诊断
  - 查看任务流水线时间线
- 新增 `POST /internal/v1/tasks/{task_id}/select-generation`
- “采用此版本”当前只允许直接采用已 `accepted` 的版本

### 2.3 主控台与后续链路一致性

- `/admin` 现在会展示当前采用版本、参考文章、AI 去痕诊断和流水线时间线的摘要层
- 微信草稿推送、反馈导入、反馈同步都优先跟随“当前采用版本”
- `/admin`、`/admin/phase5`、`/admin/console` 现在基于同一套 `workspace` 语义，减少“页面上看到的版本”和“实际将推送的版本”不一致的问题

## 3. 本地验证

已完成：

- `pytest -q`
  - 结果：`93 passed`
- `python3 -m compileall app tests`
  - 结果：通过

重点覆盖：

- `workspace` 返回参考文章、时间线、当前采用版本与 AI 去痕诊断
- 历史稿人工采用与冲突保护
- 当前采用版本优先的推草稿与反馈同步
- `/admin`、`/admin/phase5` 路由与页面渲染

## 4. 线上验收

待本轮服务器部署与 smoke test 完成后回填。

## 5. 已知边界

当前版本仍不包含：

- 多用户、角色权限与审批流
- Phase 7F 的趋势图、告警分级、去重与静默
- 真正的后台正文编辑器
- 更完整的浏览器级 E2E 回归

## 6. 发布结果

待回填：

- release commit
- 正式 tag
- 部署方式
- 服务器当前 commit
