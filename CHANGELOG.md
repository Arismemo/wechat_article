# Changelog

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
