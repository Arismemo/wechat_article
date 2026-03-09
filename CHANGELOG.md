# Changelog

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
