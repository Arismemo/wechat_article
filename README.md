# wechat_artical

微信公众号选题重构与草稿生产系统。

当前正式版本：`v1.1.0`
状态：`Phase 7E Completed · 准备进入 Phase 7F`

第二版收口重点：

- 后台页默认复用 `admin_session`，不再要求在 Phase 5 / 6 / settings / console 页面手动输入 Bearer Token
- Phase 4 审稿增加 AI 痕迹识别、定点 humanize 和复审闭环
- 四条 worker 队列补齐持续心跳、queue depth / processing / pending 观测
- 工作台与任务接口新增结构化审稿元数据，统一并发状态写回逻辑

## 系统能做什么

系统当前已经打通两条主链路，其中网页端现在是默认交互入口：

- `打开 /admin -> 贴微信文章链接 -> 服务端异步跑完整流程 -> 审稿通过 -> 自动进入公众号草稿箱 -> 人工发布`
- `复制微信文章链接 -> iPhone 快捷指令提交 -> 服务端异步跑完整流程 -> 审稿通过 -> 自动进入公众号草稿箱 -> 人工发布`

已完成范围：

- Phase 2：原文抓取、清洗、Playwright 兜底、正文图片重写、微信草稿箱推送
- Phase 3：原文分析、同题搜索、差异矩阵、`content_brief`
- Phase 4：写稿、审稿、自动修订、自动/手动推草稿
- Phase 5：后台工作台、任务看板、版本 diff、人工审核、人工推草稿开关
- Phase 6：手工/批量反馈导入、Prompt 实验榜、风格资产、自动反馈同步入口
- Phase 7A：统一监控首页、自动轮询、历史筛选、任务聚合详情
- Phase 7B：网页运行参数设置、`system_settings` 覆盖层、配置审计日志
- Phase 7C：统一控制台实时流、统计卡片、SSE 监控快照接口
- Phase 7D：只读环境状态面板、测试告警入口、成功率与异常卡片
- Phase 7E：队列深度、worker 心跳与处理态观测面板

## 仓库结构

- `app/`：FastAPI 后端、数据模型、服务逻辑、后台页
- `migrations/`：Alembic 迁移
- `scripts/`：worker 和部署脚本
- `docs/`：需求、阶段文档、部署记录、MVP 收口结论
- `docker-compose.yml`：本地与服务器运行编排

## 核心入口

公开入口：

- `POST /api/v1/ingest/link`
- `GET /api/v1/ingest/shortcut`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/tasks/{task_id}/brief`
- `GET /api/v1/tasks/{task_id}/draft`
- `GET /api/v1/tasks/{task_id}/feedback`
- `GET /api/v1/tasks/{task_id}/workspace`
- `GET /api/v1/admin/monitor/snapshot`
- `GET /api/v1/admin/runtime-status`
- `GET /api/v1/admin/settings`
- `POST /api/v1/admin/alerts/test`

后台页：

- `GET /admin`
- `GET /admin/phase2`
- `GET /admin/console`
- `GET /admin/console/stream`
- `GET /admin/settings`
- `GET /admin/phase5`
- `GET /admin/phase6`

## iPhone 快捷指令接法

手机端推荐固定为：

`复制链接 + 双击背面 + 读取剪贴板 + GET /api/v1/ingest/shortcut`

推荐链接模板：

```text
https://auto.709970.xyz/api/v1/ingest/shortcut?key=<INGEST_SHORTCUT_SHARED_KEY>&url=<文章链接>&source=ios-shortcuts&device_id=iphone-shortcuts&trigger=back-tap&dispatch_mode=auto
```

服务器要实现“一键到草稿箱”，至少要打开：

- `INGEST_SHORTCUT_AUTO_ENQUEUE_PHASE4=true`
- `WECHAT_ENABLE_DRAFT_PUSH=true`
- `PHASE4_AUTO_PUSH_WECHAT_DRAFT=true`

详细快捷指令接法见：

- `docs/phase-0/ios-shortcuts.md`

## 本地运行

1. 复制环境变量模板：

```bash
cp .env.example .env
```

2. 填好至少这些变量：

- `API_BEARER_TOKEN`
- `INGEST_SHORTCUT_SHARED_KEY`
- `DATABASE_URL` 或 `POSTGRES_*`
- `REDIS_URL`
- `ZHIPUAI_API_KEY`
- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `WECHAT_AUTHOR_NAME`

3. 启动服务：

```bash
docker compose up -d postgres redis api phase2_worker phase3_worker phase4_worker feedback_worker
docker compose run --rm api alembic upgrade head
```

4. 查看健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

## 服务器部署

### 标准 Git 部署

适用于服务器能正常拉依赖和 Playwright 的场景：

```bash
bash scripts/deploy_from_git.sh
```

可选参数：

- `SERVICES="api phase4_worker feedback_worker"`
- `SKIP_BUILD=1`

如果服务器 `.git` 工作树损坏，先执行：

```bash
bash scripts/repair_server_git_checkout.sh
```

### 正式镜像发布路径

当前推荐的正式发布路径是：

1. 本地构建 `linux/amd64` 镜像
2. 通过 `docker save | ssh ... docker load` 推到服务器
3. 服务器 `git pull --ff-only`
4. 执行 migration
5. `docker compose up -d --no-build --force-recreate`

执行方式：

```bash
BASE_IMAGE=wechat_artical:v1.1.0-amd64 \
SERVICES="api phase2_worker phase3_worker phase4_worker feedback_worker" \
bash scripts/deploy_prebuilt_from_local.sh
```

如果本地已经有同版本镜像，可复用：

```bash
SKIP_LOCAL_BUILD=1 \
BASE_IMAGE=wechat_artical:v1.1.0-amd64 \
SERVICES="api phase2_worker phase3_worker phase4_worker feedback_worker" \
bash scripts/deploy_prebuilt_from_local.sh
```

### 为什么默认用预构建镜像

服务器当前外网下载 Chromium 仍然慢，而 Dockerfile 又需要 Playwright 浏览器层。  
所以当前正式发布默认采用“本地预构建 amd64 镜像 + 远端只做 Git 拉取和容器重建”的方式。

## 使用方式

### 方式 1：网页主控台

- 打开 `/admin`
- 贴微信文章链接
- 看左侧任务自动刷新
- 按需要点击“重新跑一版 / 通过 / 驳回重写 / 推草稿”
- 最终在公众号后台草稿箱查看结果

### 方式 2：手机快捷指令

- 复制微信文章链接
- 双击背面触发快捷指令
- 服务端异步处理
- 最终在公众号后台草稿箱查看结果

### 方式 3：高级页面

- `/admin`
  - 主入口
  - 默认面向日常使用：贴链接、看进度、做动作
- `/admin/console`
  - 监控详情页
  - 优先通过 SSE 实时推送任务快照，失败时回退轮询
  - 展示当前筛选、运行中、待人工、待推草稿、已入草稿、失败任务、异常堆积、今日提交、今日入草稿、今日失败、今日审稿通过率、今日自动推稿成功率等统计卡片
  - 展示 Phase 2 / 3 / 4 / feedback 的队列深度、处理中任务、待确认数量和 worker 心跳
  - 支持按状态、来源、关键词、起始时间筛选历史任务
  - 适合排障和深入看运行态
- `/admin/settings`
  - 查看和修改网页可配置的运行参数
  - 当前支持 Phase 4 写稿模型、审稿模型、自动推草稿
  - 当前支持反馈 Provider 和默认 day offsets
  - 展示环境默认值、数据库覆盖值和实际生效值
  - 展示 `.env` 只读环境状态面板
  - 支持发送测试告警验证 `ALERT_WEBHOOK_URL`
- `/admin/phase5`
  - 审核深水区：最近任务、状态分组、待处理筛选、版本 diff、人工审核
- `/admin/phase6`
  - 反馈深水区：反馈导入、Prompt 实验榜、风格资产、自动反馈入口

## 网页配置边界

Phase 7B 只开放“可热修改的运行参数”，当前读取顺序为：

1. `system_settings`
2. `.env`

Phase 7C / 7D 的监控快照接口、环境状态接口和统一控制台不会直接暴露密钥明文；实时流仍然通过后台 Basic Auth 保护，数据接口仍支持 `API_BEARER_TOKEN`，而通过后台页进入后的动作默认复用 `admin_session`。

也就是说，网页设置不会直接重写 `.env`。当前仍然只允许通过环境变量管理的值包括：

- 数据库与 Redis 连接
- `API_BEARER_TOKEN`
- `ADMIN_PASSWORD`
- `LLM_API_KEY`
- `WECHAT_APP_SECRET`
- `FEEDBACK_SYNC_HTTP_URL`
- `FEEDBACK_SYNC_API_KEY`

## 发布文档

- 第二版发布说明：`docs/release-v1.1.0.md`
- 标准发布流程：`docs/release-process.md`

## 自动反馈 Provider 协议

如果要接真实反馈数据源，当前约定：

- `FEEDBACK_SYNC_PROVIDER=http`
- `FEEDBACK_SYNC_HTTP_URL=https://your-provider.example/sync`
- 可选 `FEEDBACK_SYNC_API_KEY`

任务级入口：

- `POST /internal/v1/tasks/{task_id}/run-feedback-sync`
- `POST /internal/v1/tasks/{task_id}/enqueue-feedback-sync`

批量扫描最近已推草稿任务并入队：

- `POST /internal/v1/feedback/enqueue-recent-sync`

请求体示例：

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

响应体示例：

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

## 文档

- `docs/README.md`
- `docs/mvp-closeout-2026-03-08.md`
- `docs/phase-0/ios-shortcuts.md`
- `docs/phase-7/runtime-settings.md`
- `docs/phase-7/console-monitoring.md`
- `docs/web-console-plan.md`
- `CHANGELOG.md`
