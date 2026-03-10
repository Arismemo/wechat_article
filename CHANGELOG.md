# Changelog

## v1.1.2 - 2026-03-10

围绕 Phase 7F 第一刀和前端收束准备做一次补丁发布，重点把“/admin 会话恢复”“monitor 分级告警与趋势图”“前端优化总方案”收进正式版本。

### Added

- `GET /api/v1/admin/monitor/snapshot` 新增：
  - `alerts`
  - `trends`
- `/admin/console` 新增：
  - 告警与静默面板
  - 最近 24 小时趋势面板
  - 告警本地静默与恢复全部静默
- 新增前端优化总方案文档：
  - `docs/post-v1.1.0-frontend-redesign-plan.md`

### Changed

- 项目版本提升为 `1.1.2`
- `/admin` 在会话失效后会明确提示“刷新后可恢复上下文”，并保留 `task_id`、主筛选、搜索词和未提交链接
- `AdminMonitorService` 现在会输出稳定 `dedupe_key`，供前端静默和去重使用
- `README.md`、`docs/README.md`、`docs/phase-7/console-monitoring.md`、路线图与交接文档同步到 Phase 7F 基线

### Verified

- `pytest -q`
- `python3 -m compileall app tests`
- 线上 smoke test 结果见 `docs/release-v1.1.2.md`

## v1.1.1 - 2026-03-10

围绕 `v1.1.0` 之后的 4 个收口任务做一次补丁发布，重点把“参考文章可查看 / 历史稿人工采用 / 流水线时间线 / AI 去痕触发原因可见化”真正发布到线上。

### Added

- `GET /api/v1/tasks/{task_id}/workspace` 新增：
  - `related_articles`
  - `selected_generation`
  - `timeline`
  - generation 级 `ai_trace_diagnosis`
  - `is_selected`
  - `draft_saved`
  - `wechat_media_id`
- `POST /internal/v1/tasks/{task_id}/select-generation`
- `TaskWorkspaceQueryService`
- `TaskGenerationSelectionService`
- `/admin/phase5` 新增：
  - 参考文章点击查看
  - 当前采用版本展示
  - 历史稿人工采用
  - AI 去痕诊断
  - 流水线时间线
- `/admin` 新增：
  - 当前采用版本摘要
  - 参考文章摘要
  - AI 去痕诊断摘要
  - 流水线时间线摘要

### Changed

- 项目版本提升为 `1.1.1`
- 微信草稿推送、反馈导入、反馈同步都优先跟随“当前采用版本”
- `/admin` 与 `/admin/phase5` 改为复用同一份 `workspace` 聚合逻辑，减少字段漂移
- “采用此版本”动作只允许直接采用已 `accepted` 的版本，避免页面语义和服务端冲突规则不一致

### Verified

- `pytest -q` -> `93 passed`
- `python3 -m compileall app tests` -> 通过
- 线上 smoke test 结果见 `docs/release-v1.1.1.md`

## v1.1.0 - 2026-03-09

第二个正式版本，完成 Phase 7E 收口，并将当前后台/审稿/worker 运行态增强整理为可发布版本。

### Added

- 审稿元数据结构化输出：`ai_trace_score`、`ai_trace_patterns`、`rewrite_targets`、`voice_summary`、`humanize_applied`
- Phase 4 定点 humanize pass 与复审闭环
- 四条 worker 的持续心跳刷新工具与对应测试
- 并发 session 下任务状态统一写回修正
- 第二版发布说明与标准发布流程文档

### Changed

- 项目版本提升为 `1.1.0`
- 后台主页面、监控页、设置页、Phase 5 / 6 页面默认复用后台会话，不再依赖手动输入 Bearer Token
- Phase 4 当前 Prompt 版本提升为 `phase4-v3`
- Phase 3 在无同题素材时改为降级继续产出 brief，而不是直接失败
- 正式发布要求回到“clean git worktree + tag + 标准部署”的流程，不再把热同步脏工作树视为正式版本

### Verified

- `pytest -q` -> `85 passed`
- `/admin` 页面已包含 `STATUS_PROGRESS`、`applyOptimisticTaskState`、`cache: "no-store"`
- `/admin/phase5` 已展示 AI 痕迹、定点润色和语气诊断
- `/admin/console/stream?once=true&limit=3` 已返回监控快照，4 个 worker 心跳正常

### Security

- 生产环境建议始终配置 `ADMIN_USERNAME` 与 `ADMIN_PASSWORD`。未配置时，后台会话会退化为基于 `API_BEARER_TOKEN` 的 `admin_session`

## v1.0.0 - 2026-03-08

首个正式 MVP 版本。

### Added

- Phase 2 原文抓取、清洗、Playwright 兜底、图片重写、微信草稿箱推送
- Phase 3 同题搜索、差异矩阵、`content_brief`
- Phase 4 写稿、审稿、自动/手动推草稿、风格资产回灌
- Phase 5 后台工作台、任务看板、版本 diff、人工审核、推草稿开关
- Phase 6 手工/批量反馈导入、Prompt 实验榜、自动反馈同步、风格资产
- `GET /api/v1/ingest/shortcut`，用于 iPhone 快捷指令一站式提交文章链接

### Changed

- 项目版本固定为 `1.0.0`
- 正式部署路径固定为：
  - GitHub 仓库作为源码基线
  - 本地预构建 `linux/amd64` 镜像
  - 服务器 `git pull + migration + docker compose --no-build --force-recreate`
- iPhone 快捷指令默认改走快捷链接入口，不再要求手机端配置 Bearer Header 和 JSON Body

### Verified

- 真实文章已从快捷指令入口跑到 `draft_saved`
- 服务器当前支持：
  - `https://auto.709970.xyz/api/v1/ingest/shortcut`
  - `/admin/phase5`
  - `/admin/phase6`
