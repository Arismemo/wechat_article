# v1.1.0 发布说明

更新时间：2026-03-09
状态：Released

## 1. 发布结论

`v1.1.0` 已于 2026-03-09 正式发布，是继 `v1.0.0` MVP 收口之后的第二个正式版本。

这一版不重定义产品边界，重点是把现有流水线的后台交互、审稿闭环和 worker 运行态观测收口成更稳定、可运营、可发布的版本。

## 2. 相对 v1.0.0 的新增与变化

### 2.1 后台会话与交互

- `/admin`
- `/admin/console`
- `/admin/settings`
- `/admin/phase5`
- `/admin/phase6`

这些页面现在默认复用后台会话，不再要求在页面内手动输入 Bearer Token。

### 2.2 Phase 4 审稿闭环增强

- 新增 AI 痕迹评分与命中模式
- 新增 `rewrite_targets`
- 新增定点 humanize pass
- humanize 后自动复审
- 工作台与任务接口透出新的审稿元数据

### 2.3 Worker 与运行态观测

- Phase 2 / 3 / 4 / feedback 四个 worker 都补齐持续心跳
- 统一控制台展示：
  - `queue_depth`
  - `processing_depth`
  - `pending_count`
  - `last_seen_at`
  - `healthy`
  - `status`

### 2.4 工程与发布整理

- `output/`、临时计划文件和部署残留纳入发布前清理范围
- 发布流程文档化，正式版本要求回到 clean git worktree + tag + 标准部署路径

## 3. 本地验证

已完成：

- `pytest -q`
  - 结果：`85 passed`

重点覆盖：

- 后台会话与页面路由
- Phase 3 降级继续产出 brief
- Phase 4 AI 痕迹识别与定点 humanize
- 工作台审稿元数据响应
- worker heartbeat
- 并发 session 下状态写回

## 4. 线上验收

当前服务器已验证：

- `GET /healthz`
- `GET /admin`
- `GET /admin/phase5`
- `GET /admin/console/stream?once=true&limit=3`

已确认现象：

- `/admin` 页面包含 `STATUS_PROGRESS`、`applyOptimisticTaskState`、`cache: "no-store"`
- `/admin/phase5` 展示 AI 痕迹、定点润色和语气诊断
- `snapshot` 返回 4 个 worker，且均为 `healthy`

## 5. 已知边界

当前版本仍不包含：

- 更细粒度的后台权限模型
- Phase 7F 的趋势图、告警分级与静默
- 真实微信分析接口驱动的正式反馈 Provider
- 真实浏览器 E2E 回归套件

## 6. 发布结果

- release commit：`2a292ac`
- 正式 tag：`v1.1.0`
- 本地 `HEAD`：`2a292ac`
- `origin/main`：`2a292ac`
- `origin` 已存在 `v1.1.0` tag
- 当前服务器工作树已对齐到 `2a292ac`

本次正式发布后，`v1.1.0` 的代码、文档、tag 和线上运行态已经统一到同一版本基线。
