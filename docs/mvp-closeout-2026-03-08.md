# MVP 收口记录

更新时间：2026-03-08
状态：Closed

## 1. 收口结论

截至 2026-03-08，项目最初冻结的 MVP 主链路已完成：

`复制微信文章链接 -> iPhone 快捷指令提交 -> 服务端异步跑完整流程 -> 审稿通过 -> 自动进入公众号草稿箱 -> 人工发布`

这条链路已在服务器上完成真实 smoke test，不再只是内部接口联调。

## 2. 本次收口变更

- 公开入口 `POST /api/v1/ingest/link` 已支持 `dispatch_mode`
  - `source=ios-shortcuts` / `ios-share-sheet` 且 `dispatch_mode=auto` 时，默认直接进入 Phase 4 异步队列
  - 后台和调试入口可显式使用 `dispatch_mode=ingest_only` 保持“只建任务”
- 新增快捷指令接入文档：
  - `docs/phase-0/ios-shortcuts.md`
- 服务器已打开以下运行时开关：
  - `INGEST_SHORTCUT_AUTO_ENQUEUE_PHASE4=true`
  - `WECHAT_ENABLE_DRAFT_PUSH=true`
  - `PHASE4_AUTO_PUSH_WECHAT_DRAFT=true`

## 3. 真实验收

### 3.1 请求

- 入口：`POST /api/v1/ingest/link`
- 来源：`source=ios-shortcuts`
- 触发：`trigger=back-tap`
- 文章：
  - `https://mp.weixin.qq.com/s/OE0GJvalYOl9OJvQIg3bew?codex_smoke=20260308`

### 3.2 入口返回

- `task_id`：`95ac3cc1-ea9d-4fc4-8ef0-a8b730f196f7`
- `status`：`queued`
- `deduped`：`false`
- `dispatch_mode`：`phase4_enqueue`
- `enqueued`：`true`

### 3.3 终态

- 最终状态：`draft_saved`
- `generation_id`：`57882495-a2ce-4294-8ee0-b2fc60820538`
- `brief_id`：`b9c14dde-c957-40f5-b36d-ce4030c64b56`
- 微信草稿 `media_id`：`PyYQ74YwFFGh2wyA3BOdv0V4-W6lfrHpb2uoSEtp_e3mshV9eaX3Y6SrJ6F5fV_3`

## 4. 与最初需求对照

- `FR-001`：已完成
  - 公开入口已按 iPhone 快捷指令场景收口
- `FR-002`：已完成
  - URL 标准化、Bearer 鉴权、活动任务幂等去重、任务入队都已生效
- `FR-003` 到 `FR-014`：已完成
  - 抓取、研究、Brief、生成、审稿、草稿箱、后台、人工干预、审计轨迹均已落地
- `NFR-006`：已完成
  - 当前系统只自动入草稿箱，不自动正式发布

## 5. 仍属于后续优化的项

以下内容不再阻塞 MVP 收口，但仍值得后续继续硬化：

- 高风险垂类更严格的规则门控或白名单/黑名单
- 反馈同步从 `mock/http` Provider 升级到正式数据源
- 服务器部署链路进一步减少热同步步骤
