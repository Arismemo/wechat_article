# wechat_artical

微信公众号选题重构与草稿生产系统。

当前仓库状态：

- `docs/` 中维护产品方案、阶段计划和阶段交付物
- `app/` 中维护 FastAPI 后端、数据模型和服务逻辑
- `migrations/` 中维护数据库迁移
- `docker-compose.yml` 中维护 API、数据库、Redis 以及阶段 2 / 阶段 3 worker 的容器化运行方式
  - 当前也已纳入 `phase4_worker` 和 `feedback_worker`
- 阶段 2 最小闭环及补充项已完成并通过服务器验收：`原文抓取 -> 固定模板稿 -> 图片重写 -> 微信草稿箱`
- 阶段 3 初版研究层已完成并通过服务器验收：`原文分析 -> 同题搜索 -> 差异矩阵 -> content_brief`
- 阶段 4 已完成并通过服务器验收：`content_brief -> generation -> review -> 手动或按开关自动推送微信草稿箱`
- 阶段 5 后台工作台第二轮已完成并通过服务器 smoke test：`任务看板 -> 聚合详情 -> 人工审核 -> 手动操作`
  - 当前已支持按状态分组与“只看待处理任务”筛选、版本 diff、人工确认通过 / 驳回重写
  - 当前已支持“允许推草稿 / 禁止推草稿”人工开关，并已通过服务器烟测验证服务端强制拦截被禁止的推送
  - `/admin/*` 现已支持可选 Basic Auth 保护
- 阶段 6 第一版已完成并通过服务器 smoke test：`手工反馈导入 -> Prompt 实验榜 -> 风格资产库`
  - 当前不依赖微信分析接口，已支持从后台手工录入 T+1 / T+3 / T+7 数据
  - 当前已支持 Phase 6 后台页：`GET /admin/phase6`
  - 当前已支持自动反馈入口：`HTTP Provider -> feedback_worker -> publication_metrics`
- MVP 主链路已在服务器完成最终收口：
  - 公开入口 `POST /api/v1/ingest/link`
  - `source=ios-shortcuts`
  - 自动进入 Phase 4 异步队列
  - 审稿通过后自动进入微信草稿箱

## 当前已完成范围

- 建立 `FastAPI + PostgreSQL + Redis` 基础骨架
- 建立第一版数据模型和数据库迁移
- 实现最小 API：
  - `POST /api/v1/ingest/link`
  - `GET /api/v1/tasks`
  - `GET /api/v1/tasks/{task_id}`
  - 公开入口现支持 `dispatch_mode=auto|ingest_only|phase4_enqueue`
  - `source=ios-shortcuts` / `ios-share-sheet` 且 `dispatch_mode=auto` 时，会直接进入 Phase 4 异步队列
- 实现阶段 2 内部联调入口：
  - `POST /internal/v1/tasks/{task_id}/run-phase2`
  - `POST /internal/v1/tasks/{task_id}/enqueue-phase2`
  - `POST /internal/v1/phase2/ingest-and-enqueue`
- 实现阶段 2 补充能力：
  - Playwright 官方 `chromium` new headless 兜底
  - 最近任务列表后台页：`GET /admin/phase2`
  - 正文图片上传与 HTML 重写
  - 轻量异步 worker：`scripts/run_phase2_worker.py`
  - `wechat-article-exporter` 对接 PoC：`scripts/wechat_exporter_poc.py`
  - 服务器已验证同步 `run-phase2` 与异步 `ingest-and-enqueue` 两条链路
- 实现阶段 3 初版能力：
  - `POST /internal/v1/tasks/{task_id}/run-phase3`
  - `POST /internal/v1/tasks/{task_id}/enqueue-phase3`
  - `POST /internal/v1/phase3/ingest-and-run`
  - `POST /internal/v1/phase3/ingest-and-enqueue`
  - `GET /api/v1/tasks/{task_id}/brief`
  - 研究层 worker：`scripts/run_phase3_worker.py`
  - 智谱 `web_search` 搜索接入
  - `article_analysis`、`related_articles`、`content_brief` 落库
- 阶段 4 已完成服务器收口：
  - `POST /internal/v1/tasks/{task_id}/run-phase4`
  - `POST /internal/v1/tasks/{task_id}/enqueue-phase4`
  - `POST /internal/v1/phase4/ingest-and-run`
  - `POST /internal/v1/phase4/ingest-and-enqueue`
  - `GET /api/v1/tasks/{task_id}/draft`
  - `POST /internal/v1/tasks/{task_id}/push-wechat-draft`
  - 创作与审稿 worker：`scripts/run_phase4_worker.py`
  - `generations`、`review_reports` 正式落库与查询
  - 服务器已验证 `glm-5` 真稿生成、审稿通过、手动推送微信草稿箱
  - 可选开关：`PHASE4_AUTO_PUSH_WECHAT_DRAFT=true`

## iPhone 快捷指令最终接法

- 手机端主入口仍是：
  - `复制链接 + 双击背面 + 读取剪贴板`
- 快捷指令默认调用：
  - `POST /api/v1/ingest/link`
- 推荐请求体：

```json
{
  "url": "https://mp.weixin.qq.com/s/xxxxxxxxxxxx",
  "source": "ios-shortcuts",
  "device_id": "iphone-15-pro",
  "trigger": "back-tap",
  "dispatch_mode": "auto"
}
```

- 若要让这条链路在审稿通过后自动进入微信草稿箱，服务器需同时满足：
  - `INGEST_SHORTCUT_AUTO_ENQUEUE_PHASE4=true`
  - `WECHAT_ENABLE_DRAFT_PUSH=true`
  - `PHASE4_AUTO_PUSH_WECHAT_DRAFT=true`
- 详细手机端接法与排查要点见：
  - `docs/phase-0/ios-shortcuts.md`
- 阶段 5 第一版已实现：
  - `GET /admin/phase5`
  - `/admin/*` 可选 `ADMIN_USERNAME` / `ADMIN_PASSWORD` Basic Auth
  - `GET /api/v1/tasks/{task_id}/workspace`
  - `GET /api/v1/tasks?active_only=true&status=...`
  - `POST /internal/v1/tasks/{task_id}/approve-latest-generation`
  - `POST /internal/v1/tasks/{task_id}/reject-latest-generation`
  - `POST /internal/v1/tasks/{task_id}/allow-wechat-draft-push`
  - `POST /internal/v1/tasks/{task_id}/block-wechat-draft-push`
  - 最近任务看板、源文/Brief/生成稿聚合详情
  - 按状态分组的任务看板与待处理筛选
  - generation 版本差异视图、风险展示、审计轨迹
  - 人工确认通过 / 驳回重写，并写入审计日志
  - `workspace` 返回当前推草稿策略，后台支持人工允许 / 禁止推草稿
  - 一键回补 Phase 3、一键重跑 Phase 4、一键推草稿
- 阶段 6 第一版已实现：
  - `GET /admin/phase6`
  - `POST /internal/v1/tasks/{task_id}/import-feedback`
  - `POST /internal/v1/feedback/import-csv`
  - `POST /internal/v1/tasks/{task_id}/run-feedback-sync`
  - `POST /internal/v1/tasks/{task_id}/enqueue-feedback-sync`
  - `POST /internal/v1/feedback/enqueue-recent-sync`
  - `POST /internal/v1/style-assets`
  - `GET /api/v1/tasks/{task_id}/feedback`
  - `GET /api/v1/feedback/experiments`
  - `GET /api/v1/feedback/style-assets`
  - `publication_metrics`、`prompt_experiments`、`style_assets` 落库
  - 手工录入或批量 CSV 回填 T+1 / T+3 / T+7 数据会自动回刷 Prompt 实验聚合
  - 自动反馈同步支持两种 Provider：
    - `FEEDBACK_SYNC_PROVIDER=mock`：本地和测试环境联调
    - `FEEDBACK_SYNC_PROVIDER=http`：向外部 HTTP 数据源请求反馈快照
  - 自动反馈 worker：`scripts/run_feedback_worker.py`
  - `style_assets` 已接回 Phase 4 写稿 Prompt，新 generation 会落 `prompt_type/prompt_version`
  - 服务器已验证反馈导入、实验榜聚合和 `/admin/phase6`

## 开发约束

- 所有项目确认信息必须先更新 `docs/`
- 敏感凭据只通过环境变量注入
- 固定可靠的服务优先用 `docker compose` 容器化运行
- 如果服务器端口冲突，只改本项目端口映射

## 运行方式

阶段 1 默认采用 `docker compose` 运行以下固定服务：

- `postgres`
- `redis`
- `api`
- `phase2_worker`
- `phase3_worker`
- `phase4_worker`
- `feedback_worker`

## 部署方式

- 服务器推荐入口：`scripts/deploy_from_git.sh`
- 如果服务器工作区的 `.git` 已损坏，先执行：`scripts/repair_server_git_checkout.sh`
- Docker 镜像现在会先安装 `requirements.runtime.txt` 和 Playwright，再复制 `app/` 代码
  - 普通业务代码变更不会重新触发依赖层和浏览器下载层
- 如果服务器首次冷构建 Playwright 仍然过慢，可改走：`scripts/deploy_prebuilt_from_local.sh`
  - 本地构建 `linux/amd64` 镜像
  - 通过 `docker save | ssh ... docker load` 灌到服务器
  - 服务器仍然坚持 `git pull` 更新工作树和 migration
  - 加载后会 `--force-recreate` 目标服务，确保同名 tag 更新后容器实际切到新镜像
  - 如果本机已经有可复用镜像，可加：`SKIP_LOCAL_BUILD=1 BASE_IMAGE=...`
- `scripts/deploy_from_git.sh` 支持：
  - `SERVICES="api phase4_worker feedback_worker"` 只部署部分服务
  - `SKIP_BUILD=1` 跳过镜像构建，仅做 `git pull + migration + compose up`

## 自动反馈 Provider 协议

如果要接真实自动反馈数据源，当前后端约定：

- 配置 `FEEDBACK_SYNC_PROVIDER=http`
- 配置 `FEEDBACK_SYNC_HTTP_URL=https://your-provider.example/sync`
- 可选配置 `FEEDBACK_SYNC_API_KEY`
- 任务级同步入口：
  - `POST /internal/v1/tasks/{task_id}/run-feedback-sync`
  - `POST /internal/v1/tasks/{task_id}/enqueue-feedback-sync`
- 批量扫描最近已推草稿任务并入队：
  - `POST /internal/v1/feedback/enqueue-recent-sync`

HTTP Provider 请求体示例：

```json
{
  "task_id": "f703c3ef-e358-48ab-936d-187418c584c5",
  "task_status": "draft_saved",
  "task_source_url": "https://mp.weixin.qq.com/s/...",
  "generation_id": "71c6bc73-a527-4e4a-be42-31b02b542008",
  "generation_version": 5,
  "prompt_type": "phase4_write",
  "prompt_version": "phase4-v2",
  "wechat_media_id": "PyYQ74Y...",
  "draft_created_at": "2026-03-08T10:00:00+08:00",
  "day_offsets": [1, 3, 7]
}
```

HTTP Provider 响应体示例：

```json
{
  "provider": "wechat-analytics-proxy",
  "snapshots": [
    {
      "day_offset": 1,
      "snapshot_at": "2026-03-09T09:00:00+08:00",
      "read_count": 1666,
      "like_count": 101,
      "share_count": 18,
      "comment_count": 6,
      "click_rate": 0.2031
    }
  ]
}
```
