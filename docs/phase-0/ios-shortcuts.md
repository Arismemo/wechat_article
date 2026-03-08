# iPhone 快捷指令接入说明

更新时间：2026-03-08
状态：Active

## 1. 目标链路

首版目标链路固定为：

`复制文章链接 -> 双击背面触发快捷指令 -> POST /api/v1/ingest/link -> Phase 4 异步队列 -> 审稿通过后自动入微信草稿箱`

要让这条链路真正一键到底，服务器环境需同时满足：

- `INGEST_SHORTCUT_AUTO_ENQUEUE_PHASE4=true`
- `WECHAT_ENABLE_DRAFT_PUSH=true`
- `PHASE4_AUTO_PUSH_WECHAT_DRAFT=true`

如果第三项未开启，快捷指令仍会把任务自动送进 Phase 4，但任务会停在 `review_passed`，需要后台或内部接口再手动执行一次推草稿。

## 2. 快捷指令请求约定

快捷指令默认调用：

- `POST /api/v1/ingest/link`

请求头：

- `Authorization: Bearer <API_BEARER_TOKEN>`
- `Content-Type: application/json`

请求体示例：

```json
{
  "url": "https://mp.weixin.qq.com/s/xxxxxxxxxxxx",
  "source": "ios-shortcuts",
  "device_id": "iphone-15-pro",
  "trigger": "back-tap",
  "dispatch_mode": "auto"
}
```

字段约定：

- `source`
  - 背面双击触发：`ios-shortcuts`
  - 分享菜单触发：`ios-share-sheet`
- `dispatch_mode`
  - `auto`：推荐值。对 `ios-shortcuts` / `ios-share-sheet` 会自动进入 Phase 4 队列
  - `ingest_only`：仅创建任务，不自动排队
  - `phase4_enqueue`：显式要求直接进入 Phase 4 队列

## 3. 响应约定

成功响应示例：

```json
{
  "task_id": "f703c3ef-e358-48ab-936d-187418c584c5",
  "status": "queued",
  "deduped": false,
  "dispatch_mode": "phase4_enqueue",
  "enqueued": true,
  "queue_depth": 1
}
```

字段说明：

- `deduped=true`
  - 说明命中了活动任务去重，服务端会直接复用现有任务，不会重复入队
- `dispatch_mode=phase4_enqueue`
  - 说明公开入口已经把任务送入完整生成链路
- `enqueued=true`
  - 说明这次请求实际完成了入队

## 4. 快捷指令推荐动作

建议快捷指令按这个顺序配置：

1. 从剪贴板读取文本
2. 如果不是 `http://` 或 `https://` 开头则直接提示失败
3. 构造上面的 JSON 请求体
4. 调用 `POST /api/v1/ingest/link`
5. 从返回值中读取 `task_id`
6. 弹出通知：
   - 成功：`任务已提交：<task_id>`
   - 如果 `deduped=true`：`任务已存在，复用已有任务：<task_id>`

首版不建议在手机端长轮询任务状态。查询和干预仍以后台页和任务 API 为主。

## 5. 排查要点

- 返回 `401`
  - 检查 `Authorization` 是否带了正确 Bearer Token
- 返回 `200` 但 `dispatch_mode=ingest_only`
  - 检查 `source` 是否为 `ios-shortcuts` 或 `ios-share-sheet`
  - 检查 `INGEST_SHORTCUT_AUTO_ENQUEUE_PHASE4` 是否仍为 `true`
- 任务停在 `review_passed`
  - 检查 `PHASE4_AUTO_PUSH_WECHAT_DRAFT` 是否已开启
- 任务停在 `needs_manual_review`
  - 说明审稿或策略门控要求人工介入，这属于正常卡口
