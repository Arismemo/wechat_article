# wechat_artical

微信公众号选题重构与草稿生产系统。

当前正式版本：`v1.1.2`
状态：`Phase 7F First Cut Released · /admin 会话恢复已收口`

当前版本收口重点：

- `/admin` 主工作台补齐会话失效后的上下文恢复，保留当前任务、主筛选、搜索词和未提交链接
- `/api/v1/admin/monitor/snapshot` 新增 `alerts` / `trends`
- `/admin/console` 新增分级告警、稳定 `dedupe_key`、前端临时静默和最近 24 小时趋势视图
- Phase 7 文档与前端改版方案升级为可执行版本

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
- Phase 7F：最近 24 小时趋势、分级告警、去重 key 与前端临时静默

## 仓库结构

- `app/`：FastAPI 后端、数据模型、服务逻辑、后台页
- `migrations/`：Alembic 迁移
- `scripts/`：worker、宿主机部署脚本和兼容脚本
- `docs/`：需求、阶段文档、部署记录、MVP 收口结论
- `deploy/systemd/`：宿主机常驻服务模板
- `docker-compose.yml`：只保留 `postgres/redis` 两个官方基础设施容器

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
- `GET /api/v1/admin/topics/snapshot`
- `GET /api/v1/admin/topics/sources`
- `GET /api/v1/admin/topics/candidates`
- `POST /api/v1/admin/alerts/test`

后台页：

- `GET /admin`
- `GET /admin/topics`
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

## 本地部署（推荐）

1. 复制环境变量模板：

```bash
cp .env.example .env
```

2. 准备运行依赖：

- Python `3.9+`
- 建议直接安装系统浏览器 `google-chrome` 或 `chromium`

应用代码和 worker 走宿主机进程；`PostgreSQL / Redis` 可以二选一：

- 方案 A：直接装在宿主机
- 方案 B：继续使用官方 Docker 镜像，仅运行基础设施容器

如果这台机器已经有宿主机 `PostgreSQL / Redis` 占用了 `5432/6379`，不要再执行 `bash scripts/docker_infra.sh up`。

如果你要继续用官方 Docker 容器承载 `PostgreSQL / Redis`，并且 `5432/6379` 当前没有被宿主机服务占用，才执行：

```bash
bash scripts/docker_infra.sh up
```

如果你要把数据库和 Redis 直接装在宿主机，Ubuntu 常用依赖示例：

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip postgresql redis-server
```

或者直接执行仓库内的一次性安装脚本：

```bash
bash scripts/install_host_runtime_ubuntu.sh
```

3. 初始化宿主机运行时：

```bash
bash scripts/setup_local_host.sh
```

这个脚本会：

- 创建 `.venv`
- 安装项目运行依赖
- 检查宿主机是否已有 `chrome/chromium`
- 如果没有宿主机浏览器，则只在本机安装一次 Playwright Chromium

4. 填好至少这些变量：

- `API_BEARER_TOKEN`
- `INGEST_SHORTCUT_SHARED_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `LLM_API_KEY`
- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`

如果宿主机已经安装了 Chrome，建议把 `.env` 里的这一项改成：

```bash
PLAYWRIGHT_BROWSER_CHANNELS=chrome,chromium
```

5. 执行迁移并启动 API + worker：

```bash
bash scripts/local_runtime.sh start-all
```

如果只想先迁移数据库：

```bash
bash scripts/local_runtime.sh migrate
```

常用管理命令：

```bash
bash scripts/local_runtime.sh status
bash scripts/local_runtime.sh restart api
bash scripts/local_runtime.sh stop-all
```

运行日志默认落在：

- `run/logs/api.log`
- `run/logs/phase2_worker.log`
- `run/logs/phase3_worker.log`
- `run/logs/phase4_worker.log`
- `run/logs/feedback_worker.log`
- `run/logs/topic_fetch_worker.log`

PID 文件默认落在：

- `run/pids/`

6. 如果这台机器是长期运行的服务器，建议继续安装 systemd 单元：

```bash
START_SERVICES=1 bash scripts/install_local_systemd.sh
```

安装完成后，服务会变成宿主机常驻进程，机器重启后也会自动拉起。

更完整的宿主机部署和迁移步骤见：

- `docs/operations/host-deployment.md`

7. 查看健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

## Docker 运行

只有成熟的官方基础设施服务建议继续用 Docker，项目自己的 `api / worker` 已从仓库默认发布路径中移除。

如果你只是想快速拉起 `PostgreSQL / Redis` 官方容器，并且宿主机没有已经运行的 `5432/6379` 服务：

```bash
bash scripts/docker_infra.sh up
```

## 服务器部署

当前建议优先采用“宿主机 Python venv + 宿主机 Chrome/Chromium + 外部或官方 Docker 基础设施服务”的方式，避免每次发布都重新构建镜像和下载浏览器。

### 首次部署

```bash
cp .env.example .env
bash scripts/setup_local_host.sh
bash scripts/local_runtime.sh migrate
START_SERVICES=1 bash scripts/install_local_systemd.sh
```

如果 `PostgreSQL / Redis` 仍然走官方 Docker，并且宿主机没有占用 `5432/6379`，再单独执行：

```bash
bash scripts/docker_infra.sh up
```

### 日常发布

```bash
bash scripts/deploy_local_from_git.sh
```

如果服务器 `.git` 工作树损坏，先执行：

```bash
bash scripts/repair_server_git_checkout.sh
```

如果宿主机没有系统浏览器，首次安装依赖时可以带上：

```bash
PLAYWRIGHT_INSTALL_DEPS=1 bash scripts/setup_local_host.sh
```

如果你要顺手清理已经停掉的旧应用层 Docker 容器和镜像：

```bash
bash scripts/cleanup_legacy_app_docker.sh
```

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
- `/admin/topics`
  - 长期选题情报台
  - 查看来源运行状态、候选池、计划工作区，并把计划直接推进到任务链路
- `/admin/console`
  - 监控详情页
  - 优先通过 SSE 实时推送任务快照，失败时回退轮询
  - 展示当前筛选、运行中、待人工、待推草稿、已入草稿、失败任务、异常堆积、今日提交、今日入草稿、今日失败、今日审稿通过率、今日自动推稿成功率等统计卡片
  - 展示 Phase 2 / 3 / 4 / feedback / topic_fetch 的队列深度、处理中任务、待确认数量和 worker 心跳
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

- 当前版本发布说明：`docs/release-v1.1.2.md`
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
