# 阶段 2 采集与草稿箱集成文档

更新时间：2026-03-07
状态：Completed（含补充项）

## 1. 目标

阶段 2 的目标是把阶段 1 的“任务创建”扩展成一个可验证的最小业务闭环：

`链接 -> 原文抓取 -> 正文清洗 -> 固定模板稿 -> 微信草稿箱`

本阶段先验证链路稳定性，不引入复杂的多源分析和重写逻辑。

## 2. 本轮实现切片

当前已落地的实现切片如下：

- `httpx` 抓取原文 HTML
- `Playwright` 浏览器兜底抓取，默认走官方 `chromium` new headless，并允许回退到 `chrome`
- 可选接入 `wechat-article-exporter` 公共下载接口作为微信文章抓取 PoC
- 针对微信文章优先解析 `og:title`、`#js_name`、`#js_content`
- 清洗正文并生成摘要
- 原始 HTML 快照写入本地存储
- 生成固定模板 HTML/Markdown 测试稿
- 将正文内图片上传到微信并重写 HTML 中的图片 URL
- 上传封面图到微信永久素材
- 调用 `draft/add` 写入草稿箱
- 回写 `source_articles`、`generations`、`wechat_drafts` 和 `audit_logs`
- 提供后台手动触发页和最近任务列表
- 提供 Redis 队列 + 独立 worker 的异步执行路径

## 3. 当前有意推迟的项

以下项仍属于阶段 2 后续优化范围，但不阻塞当前可用版本：

- Playwright 兜底命中率、失败原因和队列指标上报
- `wxdown-service` 深度接入，用于历史文章 / 评论 / 阅读量能力

推迟原因：

- 当前主要目标仍是单篇 URL 到草稿箱的稳定主链路
- `wxdown-service` 适合服务 `wechat-article-exporter` 的 credentials 自动刷新，不是当前单篇抓取主路径的必需条件

## 4. 新增接口

### 4.1 内部执行接口

```http
POST /internal/v1/tasks/{task_id}/run-phase2
Authorization: Bearer <token>
```

用途：

- 同步执行阶段 2 最小闭环
- 适合当前阶段联调和 smoke test

返回字段：

- `task_id`
- `status`
- `source_title`
- `generation_id`
- `wechat_media_id`
- `snapshot_path`

### 4.2 内部异步入队接口

```http
POST /internal/v1/tasks/{task_id}/enqueue-phase2
Authorization: Bearer <token>
```

用途：

- 将已有任务加入阶段 2 队列
- 返回是否成功入队和当前队列长度
- 供后台页、脚本和后续自动化重跑使用

### 4.3 合并入口

```http
POST /internal/v1/phase2/ingest-and-run
Authorization: Bearer <token>
Content-Type: application/json
```

用途：

- 在后台页或脚本里一次性完成“建任务 + 跑阶段 2”
- 适合人工联调和临时补触发

### 4.4 合并入队入口

```http
POST /internal/v1/phase2/ingest-and-enqueue
Authorization: Bearer <token>
Content-Type: application/json
```

用途：

- 一次性完成“建任务 + 入队”
- 适合后台页默认补触发路径

### 4.5 最近任务列表

```http
GET /api/v1/tasks?limit=10
Authorization: Bearer <token>
```

用途：

- 查询最近任务，供后台触发页快速复用
- 返回 `task_id/task_code/status/progress/title/wechat_media_id/source_url/created_at`

### 4.6 后台手动触发页

```http
GET /admin/phase2
```

用途：

- 输入 Bearer Token、微信文章链接或已有 `task_id`
- 在浏览器里同步执行或异步入队
- 查询单个任务当前状态
- 查看最近任务列表并快速重跑 / 查询 / 填充 `task_id`

## 5. 数据落库路径

### 5.1 `tasks`

- `queued -> fetching_source -> source_ready -> pushing_wechat_draft -> draft_saved`
- 异常时进入：
  - `fetch_failed`
  - `push_failed`

### 5.2 `source_articles`

本阶段会写入：

- `url`
- `title`
- `author`
- `published_at`
- `cover_image_url`
- `raw_html`
- `cleaned_text`
- `summary`
- `snapshot_path`
- `fetch_status`
- `word_count`
- `content_hash`

### 5.3 `generations`

本阶段写入的是固定模板测试稿：

- `model_name=phase2-fixed-template`
- `title`
- `digest`
- `markdown_content`
- `html_content`
- 固定评分占位值

### 5.4 `wechat_drafts`

写入字段：

- `generation_id`
- `media_id`
- `push_status`
- `push_response`

## 6. 本地存储结构

MVP 阶段先使用服务器本机磁盘：

```text
data/
└── tasks/
    └── <task_id>/
        └── source/
            └── source.html
```

## 7. 配置要求

阶段 2 新增或实际启用的环境变量：

- `FETCH_HTTP_TIMEOUT_SECONDS`
- `FETCH_BROWSER_TIMEOUT_SECONDS`
- `FETCH_USER_AGENT`
- `MAX_SOURCE_EXCERPT_CHARS`
- `PLAYWRIGHT_HEADLESS`
- `PLAYWRIGHT_BROWSER_CHANNELS`
- `PLAYWRIGHT_VIEWPORT_WIDTH`
- `PLAYWRIGHT_VIEWPORT_HEIGHT`
- `WECHAT_EXPORTER_BASE_URL`
- `WECHAT_EXPORTER_REQUEST_TIMEOUT_SECONDS`
- `WECHAT_API_BASE`
- `WECHAT_REQUEST_TIMEOUT_SECONDS`
- `WECHAT_ENABLE_DRAFT_PUSH`
- `WECHAT_INLINE_IMAGE_MAX_BYTES`
- `PHASE2_INCLUDE_SOURCE_IMAGES`
- `PHASE2_MAX_INLINE_IMAGES`
- `PHASE2_QUEUE_KEY`
- `PHASE2_PROCESSING_KEY`
- `PHASE2_PENDING_SET_KEY`
- `PHASE2_WORKER_POLL_TIMEOUT_SECONDS`
- `PHASE2_WORKER_IDLE_SLEEP_SECONDS`

重要说明：

- `WECHAT_ENABLE_DRAFT_PUSH=false` 时，阶段 2 推草稿会被主动阻止，避免在本地或错误环境误推。
- 服务器联调环境需要显式开启该开关。
- `WECHAT_EXPORTER_BASE_URL` 为空时，不启用 exporter PoC 路径。
- `PLAYWRIGHT_BROWSER_CHANNELS` 默认顺序是 `chromium,chrome`，优先走官方 new headless。

## 8. 技术约束

- 当前抓取器优先面向微信公众号文章结构，通用网页只做基础兜底解析。
- 默认顺序是 `httpx -> wechat-article-exporter(可选) -> Playwright`。
- Playwright 默认使用移动端上下文和官方 `chromium` new headless；如果配置了 `chrome` 且环境可用，可自动回退。
- 当前测试稿会带入原文封面和部分正文配图；推送前会自动把 `<img>` 改写成微信 `uploadimg` 返回的 URL。
- 封面图优先使用原文 `og:image` 或首图；失败时退回内置占位图。
- Redis 失效不会阻塞 token 获取，只会退化为不缓存。
- 浏览器依赖已直接打进阶段 2 镜像，`api` 与 `phase2_worker` 都不依赖宿主机浏览器环境。
- 异步 worker 当前采用 Redis list + pending set + processing list 的轻量实现，重启 worker 时会自动把 processing 队列回灌到主队列。

## 9. 验收标准

本轮阶段 2 完成标准：

- 使用真实微信文章链接能抓到标题、作者、正文摘要
- 可以生成固定模板测试稿
- 可以成功写入公众号草稿箱
- `GET /api/v1/tasks/{task_id}` 可看到标题和 `wechat_media_id`

当前结果：

- 已用真实微信文章完成联调
- 已返回 `draft_saved`
- 已在 `source_articles`、`generations`、`wechat_drafts` 三处留痕
- 已提供可直接使用的后台手动触发页
- 已补齐最近任务列表、异步队列入口、worker 脚本、图片上传与 HTML 重写
- 已在服务器完成同步和异步两条 smoke test，`phase2_worker` 已验证可用
- 已新增 `scripts/wechat_exporter_poc.py` 用于评估 exporter 接入价值

## 10. 后续补充

当前最自然的后续补充项：

1. 把 Playwright 兜底命中率、失败原因、队列深度打成监控指标
2. 针对 `wechat-article-exporter` 公共接口做一次真实 PoC 验证，确认延迟和稳定性
3. 如要做历史文章/评论/阅读量，单独规划 `wxdown-service` 和 credentials 流程
