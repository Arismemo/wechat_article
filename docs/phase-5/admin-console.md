# 阶段 5 后台工作台与人工审核

更新时间：2026-03-07
状态：第三轮已落地，本轮补充推草稿人工许可控制

## 1. 目标

阶段 5 的第一目标不是继续扩模型能力，而是把现有流水线从“看日志排查”变成“靠后台操作”。

本轮先交付最小可用后台：

- 按状态分组的任务看板
- “只看待处理任务”筛选
- 任务聚合详情页
- 生成稿版本与审稿结果对比
- generation 间版本差异视图
- 人工确认通过 / 驳回重写
- 人工“允许推草稿 / 禁止推草稿”
- 审计轨迹展示
- 一键回补 Phase 3、一键重跑 Phase 4、一键推微信草稿

## 2. 页面入口

- `GET /admin/phase5`

页面本身不内置服务端密钥，所有写操作仍依赖手动输入 Bearer Token。
如果服务器配置了 `ADMIN_USERNAME` / `ADMIN_PASSWORD`，浏览器访问 `/admin/phase2`、`/admin/phase5` 时会先弹出 Basic Auth 登录框。

## 3. 聚合详情接口

为避免后台页自己拼接多次请求，本轮新增：

- `GET /api/v1/tasks/{task_id}/workspace`

返回内容包括：

- 任务基本信息
- 最近一次 `source_article`
- 最近一次 `article_analysis`
- 最近一次 `content_brief`
- 最近 8 个 generation 及各自最新 review
- 最近 25 条 audit log
- 当前微信草稿推送许可状态

其中 generation 详情会额外展示：

- `model_name`
- `prompt_version`
- 分数
- 最新审稿结论
- 正文 Markdown

当前 `prompt_version` 仍是固定映射：

- `glm-5` / `phase4-fallback-template` -> `phase4-v1`

后续如果 Prompt 做版本化实验，再改成真实落库字段。

## 4. 后台操作流

页面当前支持这些动作：

- `提交链接并入队 Phase4`
- `提交链接并同步执行 Phase4`
- `加载工作台`
- `入队 Phase3`
- `同步执行 Phase4`
- `入队 Phase4`
- `人工确认通过`
- `人工驳回重写`
- `允许推草稿`
- `禁止推草稿`
- `推送微信草稿`

这些动作底层复用现有接口：

- `POST /internal/v1/phase4/ingest-and-enqueue`
- `POST /internal/v1/phase4/ingest-and-run`
- `POST /internal/v1/tasks/{task_id}/enqueue-phase3`
- `POST /internal/v1/tasks/{task_id}/run-phase4`
- `POST /internal/v1/tasks/{task_id}/enqueue-phase4`
- `POST /internal/v1/tasks/{task_id}/approve-latest-generation`
- `POST /internal/v1/tasks/{task_id}/reject-latest-generation`
- `POST /internal/v1/tasks/{task_id}/allow-wechat-draft-push`
- `POST /internal/v1/tasks/{task_id}/block-wechat-draft-push`
- `POST /internal/v1/tasks/{task_id}/push-wechat-draft`

人工审核动作的约束：

- `approve-latest-generation` 会把 latest generation 标为 `accepted`
- 如果该 generation 已经有成功的微信草稿记录，任务状态会保持 / 回补为 `draft_saved`
- `reject-latest-generation` 会把 latest generation 标为 `rejected`，并把任务打回 `needs_regenerate`
- 如果该 generation 已成功推送到微信草稿箱，接口会返回 `409 conflict`，避免状态和外部草稿不一致
- `block-wechat-draft-push` 会把任务的微信推稿许可切为 `blocked`
- `allow-wechat-draft-push` 会把任务的微信推稿许可切为 `allowed`
- 被 `blocked` 的任务即使直接命中推稿接口，也会在服务端返回 `409 conflict`，同时写入 `phase5.wechat_push.blocked_attempt` 审计日志

后台访问保护：

- `/admin/*` 现在支持最小登录保护
- 只要服务端配置了 `ADMIN_USERNAME` 与 `ADMIN_PASSWORD`，后台页就会要求浏览器先通过 Basic Auth
- 这层保护只负责页面入口；页面内的写操作仍然需要手动输入 `API_BEARER_TOKEN`

任务看板当前支持这些筛选能力：

- `active_only=true`：只看待处理任务
- `status=<task_status>`：只看某一个具体状态
- 页面会按状态自动分组显示卡片

任务工作台当前支持这些版本比对能力：

- 默认比较最新版本和上一版本
- 可手动切换任意两版 generation
- 展示标题前后变化
- 展示摘要前后变化
- 展示正文 Markdown 的行级 unified diff

任务工作台当前也会展示推草稿许可：

- `default`：默认允许，尚未人工干预
- `allowed`：已人工放行
- `blocked`：已人工禁止推草稿

## 5. 人工审核 SOP

页面内已写入简化 SOP，核心规则是：

- 先看最新状态与风险，再决定是否重跑
- 研究输入不够时先回补 Phase 3
- 写稿质量不够时直接重跑 Phase 4
- 人工审核备注会随 approve / reject 一起写入 audit log
- 如果任务还不准备进入微信草稿箱，先点“禁止推草稿”
- 只有 `latest accepted generation` 且推稿许可为 `default/allowed` 时才允许推草稿
- 推送后要核对 audit log，避免重复操作

## 6. 当前边界

这一版仍不包含：

- 登录体系
- 角色权限
- 真正的 Prompt 版本管理
- 后台人工编辑正文
- 审稿意见逐条确认流
- 发布后的反馈回收

## 7. 验收结果

本地已完成：

- `/admin/phase5` 页面渲染测试
- `/admin/phase5` Basic Auth 保护测试
- `/api/v1/tasks/{task_id}/workspace` API 测试
- `ManualReviewService` 人工通过 / 驳回 / 冲突保护测试
- 全量测试通过

服务器已完成：

- `GET /admin/phase5`
- `/admin/phase5` 未登录返回 `401`，带 Basic Auth 返回 `200`
- `GET /api/v1/tasks/{task_id}/workspace`
- `GET /api/v1/tasks?active_only=true`
- `POST /internal/v1/tasks/{task_id}/approve-latest-generation`
- `POST /internal/v1/tasks/{task_id}/reject-latest-generation`

当前测试结果：

- `pytest -q` -> `37 passed`
- `python3 -m compileall app tests` -> 通过

## 8. 下一步建议

如果继续推进 Phase 5，优先级建议如下：

1. 增加“我的待处理任务 / 今日新增失败任务”这类面向运营的快捷视图
2. 把当前前端生成的 diff 结果沉淀成可复用组件或后端摘要
3. 给人工动作和推草稿动作补失败重试 / 冲突提示优化
4. 如果要继续走生产化，再补角色权限而不是只靠 Basic Auth
