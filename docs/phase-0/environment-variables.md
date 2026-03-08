# 阶段 0 环境变量清单

更新时间：2026-03-08

## 1. 配置原则

- 敏感信息只通过环境变量或密钥管理注入，不写死在仓库里。
- 所有环境变量在阶段 1 开始前先冻结第一版命名。
- 可选变量也要记录默认值策略。
- Phase 7B 之后，少量运行参数允许通过 `system_settings` 做数据库覆盖；密钥和基础设施配置仍然只允许保留在环境变量。

当前运行时读取顺序：

1. `system_settings`
2. `.env`

## 2. 基础配置

| 变量名 | 必填 | 说明 |
| --- | --- | --- |
| `APP_ENV` | 是 | 运行环境，建议 `dev/staging/prod` |
| `APP_HOST` | 是 | 服务监听地址 |
| `APP_PORT` | 是 | 服务监听端口 |
| `APP_BASE_URL` | 是 | 对外服务地址，快捷指令会调用 |
| `LOG_LEVEL` | 是 | 日志级别 |
| `TIMEZONE` | 是 | 系统时区，建议固定为 `Asia/Shanghai` |

## 3. 安全与鉴权

| 变量名 | 必填 | 说明 |
| --- | --- | --- |
| `API_BEARER_TOKEN` | 是 | 快捷指令调用接入 API 的 Bearer Token |
| `INGEST_SHORTCUT_SHARED_KEY` | 否 | iPhone 快捷指令专用共享密钥；配置后 `GET /api/v1/ingest/shortcut` 将优先使用它，而不是复用总 Bearer Token |
| `API_HMAC_SECRET` | 否 | 如果启用 HMAC 签名则必填 |
| `ADMIN_USERNAME` | 否 | 后台页 Basic Auth 用户名；配置后 `/admin/*` 将要求浏览器先登录 |
| `ADMIN_PASSWORD` | 否 | 后台页 Basic Auth 密码；建议仅在服务器环境注入 |
| `ALLOWED_IPS` | 否 | 对管理接口做 IP 限制时使用 |

## 4. 数据库与缓存

| 变量名 | 必填 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | 是 | PostgreSQL 连接串 |
| `REDIS_URL` | 是 | Redis 连接串 |
| `POSTGRES_DB` | 否 | docker compose 下的数据库名 |
| `POSTGRES_USER` | 否 | docker compose 下的数据库用户名 |
| `POSTGRES_PASSWORD` | 否 | docker compose 下的数据库密码 |
| `POSTGRES_PORT` | 否 | docker compose 对外暴露端口 |
| `REDIS_PORT` | 否 | docker compose 对外暴露端口 |
| `QUEUE_NAME_DEFAULT` | 否 | 默认任务队列名 |
| `QUEUE_NAME_PRIORITY` | 否 | 优先任务队列名 |

## 5. 对象存储

| 变量名 | 必填 | 说明 |
| --- | --- | --- |
| `STORAGE_ENDPOINT` | 否 | S3 兼容对象存储地址 |
| `STORAGE_BUCKET` | 否 | 默认桶名 |
| `STORAGE_ACCESS_KEY` | 否 | 存储访问密钥 |
| `STORAGE_SECRET_KEY` | 否 | 存储访问密钥 secret |
| `STORAGE_REGION` | 否 | 区域 |

当前确认值：

- MVP 阶段先使用服务器本机磁盘，可暂不启用外部对象存储
- 如启用本地存储，建议后续补充 `LOCAL_STORAGE_ROOT`

## 6. 模型服务

| 变量名 | 必填 | 说明 |
| --- | --- | --- |
| `LLM_PROVIDER` | 是 | 模型服务供应商标识 |
| `LLM_API_BASE` | 否 | 自定义 API Base URL |
| `LLM_API_KEY` | 是 | 模型服务密钥 |
| `LLM_MODEL_ANALYZE` | 是 | 分析模型名 |
| `LLM_MODEL_WRITE` | 是 | 写作模型名 |
| `LLM_MODEL_REVIEW` | 是 | 审稿模型名 |
| `LLM_MODEL_GROWTH` | 否 | 爆款增强器模型名 |
| `LLM_TIMEOUT_SECONDS` | 否 | 模型请求超时 |
| `LLM_WRITE_TIMEOUT_SECONDS` | 否 | 写作请求超时，默认长于通用超时 |
| `LLM_REVIEW_TIMEOUT_SECONDS` | 否 | 审稿请求超时 |

当前确认值：

- `LLM_PROVIDER=ZHIPU`
- `LLM_MODEL_ANALYZE=glm-5`
- `LLM_MODEL_WRITE=glm-5`
- `LLM_MODEL_REVIEW=glm-5`
- `LLM_API_BASE=https://open.bigmodel.cn/api/coding/paas/v4`
- `LLM_API_KEY`：已收到，文档中不明文记录
- `LLM_MODEL_WRITE`、`LLM_MODEL_REVIEW` 当前可被 `/admin/settings` 网页运行参数覆盖

## 7. 搜索服务

| 变量名 | 必填 | 说明 |
| --- | --- | --- |
| `SEARCH_PROVIDER` | 是 | 搜索服务标识 |
| `SEARCH_API_KEY` | 视方案而定 | 搜索服务密钥 |
| `SEARCH_API_BASE` | 否 | 搜索服务 API 地址 |
| `SEARCH_TIMEOUT_SECONDS` | 否 | 搜索请求超时 |
| `SEARCH_ENGINE` | 否 | 智谱搜索引擎类型，默认 `search_std` |

当前确认值：

- `SEARCH_PROVIDER=ZHIPU_MCP`
- 建议主搜索端点：`https://open.bigmodel.cn/api/mcp/web_search_prime/mcp`
- 建议网页读取端点：`https://open.bigmodel.cn/api/mcp/web_reader/mcp`
- Phase 3 后端默认调用官方 `web_search` 接口；如果 `SEARCH_API_BASE` 仍配置为 MCP 地址，服务端会自动回退到 `https://open.bigmodel.cn/api/paas/v4/web_search`
- `SEARCH_API_KEY`：已收到，文档中不明文记录

## 8. 微信公众号集成

| 变量名 | 必填 | 说明 |
| --- | --- | --- |
| `WECHAT_APP_ID` | 是 | 公众号 AppID |
| `WECHAT_APP_SECRET` | 是 | 公众号 AppSecret |
| `WECHAT_API_BASE` | 否 | 微信 API Base，默认 `https://api.weixin.qq.com/cgi-bin` |
| `WECHAT_TOKEN_CACHE_KEY` | 否 | Redis 中缓存 access_token 的 key |
| `WECHAT_ENABLE_DRAFT_PUSH` | 否 | 是否启用草稿箱推送，默认仅在 staging/prod 开启 |
| `WECHAT_DEFAULT_AUTHOR` | 否 | 草稿默认作者名 |
| `WECHAT_DEFAULT_DIGEST_PREFIX` | 否 | 摘要前缀 |
| `WECHAT_REQUEST_TIMEOUT_SECONDS` | 否 | 微信接口请求超时 |
| `WECHAT_INLINE_IMAGE_MAX_BYTES` | 否 | 正文内图片上传到微信前允许的最大字节数 |
| `INGEST_SHORTCUT_AUTO_ENQUEUE_PHASE4` | 否 | 公开入口收到 `ios-shortcuts` / `ios-share-sheet` 时，是否默认直接进入 Phase 4 异步队列，默认开启 |
| `PHASE2_INCLUDE_SOURCE_IMAGES` | 否 | 阶段 2 测试稿是否带入原文配图 |
| `PHASE2_MAX_INLINE_IMAGES` | 否 | 阶段 2 测试稿最多带入多少张原文图片 |
| `PHASE2_QUEUE_KEY` | 否 | 阶段 2 worker 主队列 Redis key |
| `PHASE2_PROCESSING_KEY` | 否 | 阶段 2 worker processing 队列 Redis key |
| `PHASE2_PENDING_SET_KEY` | 否 | 阶段 2 去重集合 Redis key |
| `PHASE2_WORKER_POLL_TIMEOUT_SECONDS` | 否 | worker 阻塞拉取队列的超时时间 |
| `PHASE2_WORKER_IDLE_SLEEP_SECONDS` | 否 | worker 空闲轮询补充 sleep 时间 |
| `PHASE3_SEARCH_PER_QUERY` | 否 | 阶段 3 每组 query 拉取多少条搜索结果 |
| `PHASE3_RELATED_TOP_K` | 否 | 阶段 3 最终保留多少篇同题素材 |
| `PHASE3_QUEUE_KEY` | 否 | 阶段 3 worker 主队列 Redis key |
| `PHASE3_PROCESSING_KEY` | 否 | 阶段 3 worker processing 队列 Redis key |
| `PHASE3_PENDING_SET_KEY` | 否 | 阶段 3 去重集合 Redis key |
| `PHASE3_WORKER_POLL_TIMEOUT_SECONDS` | 否 | 阶段 3 worker 阻塞拉取超时 |
| `PHASE3_WORKER_IDLE_SLEEP_SECONDS` | 否 | 阶段 3 worker 空闲 sleep 时间 |
| `PHASE4_QUEUE_KEY` | 否 | 阶段 4 worker 主队列 Redis key |
| `PHASE4_PROCESSING_KEY` | 否 | 阶段 4 worker processing 队列 Redis key |
| `PHASE4_PENDING_SET_KEY` | 否 | 阶段 4 去重集合 Redis key |
| `PHASE4_WORKER_POLL_TIMEOUT_SECONDS` | 否 | 阶段 4 worker 阻塞拉取超时 |
| `PHASE4_WORKER_IDLE_SLEEP_SECONDS` | 否 | 阶段 4 worker 空闲 sleep 时间 |
| `PHASE4_REVIEW_PASS_SCORE` | 否 | 阶段 4 审稿通过的最低综合分 |
| `PHASE4_SIMILARITY_MAX` | 否 | 阶段 4 相似度风险上限 |
| `PHASE4_POLICY_RISK_MAX` | 否 | 阶段 4 合规风险上限 |
| `PHASE4_FACTUAL_RISK_MAX` | 否 | 阶段 4 事实风险上限 |
| `PHASE4_MAX_AUTO_REVISIONS` | 否 | 阶段 4 自动修订最大次数，当前默认 1 |
| `PHASE4_AUTO_PUSH_WECHAT_DRAFT` | 否 | 阶段 4 审稿通过后是否自动推送微信草稿箱，默认关闭 |
| `FEEDBACK_SYNC_PROVIDER` | 否 | 自动反馈同步 Provider，支持 `disabled/mock/http` |
| `FEEDBACK_SYNC_HTTP_URL` | 否 | 自动反馈 HTTP Provider 地址，`FEEDBACK_SYNC_PROVIDER=http` 时必填 |
| `FEEDBACK_SYNC_API_KEY` | 否 | 自动反馈 HTTP Provider 的 Bearer Token |
| `FEEDBACK_SYNC_TIMEOUT_SECONDS` | 否 | 自动反馈 HTTP Provider 请求超时 |
| `FEEDBACK_SYNC_DAY_OFFSETS` | 否 | 自动反馈默认同步窗口，逗号分隔，默认 `1,3,7` |
| `FEEDBACK_SYNC_QUEUE_KEY` | 否 | feedback worker 主队列 Redis key |
| `FEEDBACK_SYNC_PROCESSING_KEY` | 否 | feedback worker processing 队列 Redis key |
| `FEEDBACK_SYNC_PENDING_SET_KEY` | 否 | feedback worker 去重集合 Redis key |
| `FEEDBACK_SYNC_WORKER_POLL_TIMEOUT_SECONDS` | 否 | feedback worker 阻塞拉取超时 |
| `FEEDBACK_SYNC_WORKER_IDLE_SLEEP_SECONDS` | 否 | feedback worker 空闲 sleep 时间 |
| `FEEDBACK_SYNC_RECENT_LIMIT` | 否 | 自动扫描最近已推草稿任务时的默认数量 |

当前确认值：

- `WECHAT_APP_ID=wxa51f35e4cc384e6e`
- `WECHAT_APP_SECRET`：已收到，文档中不明文记录
- 当前后台白名单：`117.72.155.136,222.79.178.127`
- Tailscale 管理入口：`100.112.123.6`
- 真实公网出口 IP：`117.72.155.136`
- 本地或测试环境如需验证自动反馈链路，可设：`FEEDBACK_SYNC_PROVIDER=mock`
- `PHASE4_AUTO_PUSH_WECHAT_DRAFT`、`FEEDBACK_SYNC_PROVIDER`、`FEEDBACK_SYNC_DAY_OFFSETS` 当前可被 `/admin/settings` 网页运行参数覆盖
- 若要实现“快捷指令提交后直接跑完整链路到草稿箱”，需同时满足：
  - `INGEST_SHORTCUT_AUTO_ENQUEUE_PHASE4=true`
  - `WECHAT_ENABLE_DRAFT_PUSH=true`
  - `PHASE4_AUTO_PUSH_WECHAT_DRAFT=true`

## 9. 抓取与渲染

| 变量名 | 必填 | 说明 |
| --- | --- | --- |
| `FETCH_HTTP_TIMEOUT_SECONDS` | 否 | HTTP 抓取超时 |
| `FETCH_BROWSER_TIMEOUT_SECONDS` | 否 | 浏览器抓取超时 |
| `FETCH_USER_AGENT` | 否 | 抓取请求的 User-Agent |
| `PLAYWRIGHT_HEADLESS` | 否 | 是否以 headless 模式运行 |
| `PLAYWRIGHT_BROWSER_CHANNELS` | 否 | Playwright 浏览器通道顺序，默认 `chromium,chrome` |
| `PLAYWRIGHT_VIEWPORT_WIDTH` | 否 | 浏览器兜底移动端视口宽度 |
| `PLAYWRIGHT_VIEWPORT_HEIGHT` | 否 | 浏览器兜底移动端视口高度 |
| `WECHAT_EXPORTER_BASE_URL` | 否 | `wechat-article-exporter` 公共接口地址，启用单篇下载 PoC 时使用 |
| `WECHAT_EXPORTER_REQUEST_TIMEOUT_SECONDS` | 否 | exporter 接口请求超时 |
| `HTML_RENDER_THEME` | 否 | 渲染主题名 |
| `MAX_SOURCE_WORDS` | 否 | 单篇原文最大处理字数 |
| `MAX_SOURCE_EXCERPT_CHARS` | 否 | 阶段 2 测试稿正文节选长度 |
| `LOCAL_STORAGE_ROOT` | 否 | MVP 本地存储根目录 |

## 10. 观测与告警

| 变量名 | 必填 | 说明 |
| --- | --- | --- |
| `SENTRY_DSN` | 否 | 异常上报 |
| `METRICS_ENABLED` | 否 | 是否开启指标收集 |
| `ALERT_WEBHOOK_URL` | 否 | 异常告警 webhook |

## 11. 功能开关

| 变量名 | 必填 | 说明 |
| --- | --- | --- |
| `FEATURE_RESEARCH_ENABLED` | 否 | 是否开启同题研究流程 |
| `FEATURE_REVIEW_ENABLED` | 否 | 是否开启自动审稿 |
| `FEATURE_GROWTH_ENABLED` | 否 | 是否开启爆款增强器 |
| `FEATURE_FEEDBACK_LOOP_ENABLED` | 否 | 是否开启发布表现回收 |

## 12. 阶段 1 前必须确定的变量

- `APP_BASE_URL`
- `API_BEARER_TOKEN`
- `DATABASE_URL`
- `REDIS_URL`
- `LLM_PROVIDER`
- `LLM_API_KEY`
- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`

可延后到阶段 2 以后再确定：

- `STORAGE_ENDPOINT`
- `STORAGE_BUCKET`
- `STORAGE_ACCESS_KEY`
- `STORAGE_SECRET_KEY`

## 13. 管理要求

- 新增环境变量必须先更新本文件，再进入代码。
- 每个环境变量都要有默认值策略或缺失时的失败策略。
- 如果服务器已有端口占用，优先调整 `API_PORT`、`POSTGRES_PORT`、`REDIS_PORT`，不改其它项目服务端口。
