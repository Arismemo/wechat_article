# 阶段 5 后台工作台与人工审核

更新时间：2026-03-07
状态：第一版已落地，并完成服务器 smoke test

## 1. 目标

阶段 5 的第一目标不是继续扩模型能力，而是把现有流水线从“看日志排查”变成“靠后台操作”。

本轮先交付最小可用后台：

- 按状态分组的任务看板
- “只看待处理任务”筛选
- 任务聚合详情页
- 生成稿版本与审稿结果对比
- 审计轨迹展示
- 一键回补 Phase 3、一键重跑 Phase 4、一键推微信草稿

## 2. 页面入口

- `GET /admin/phase5`

页面本身不内置服务端密钥，所有写操作仍依赖手动输入 Bearer Token。

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
- `推送微信草稿`

这些动作底层复用现有接口：

- `POST /internal/v1/phase4/ingest-and-enqueue`
- `POST /internal/v1/phase4/ingest-and-run`
- `POST /internal/v1/tasks/{task_id}/enqueue-phase3`
- `POST /internal/v1/tasks/{task_id}/run-phase4`
- `POST /internal/v1/tasks/{task_id}/enqueue-phase4`
- `POST /internal/v1/tasks/{task_id}/push-wechat-draft`

任务看板当前支持这些筛选能力：

- `active_only=true`：只看待处理任务
- `status=<task_status>`：只看某一个具体状态
- 页面会按状态自动分组显示卡片

## 5. 人工审核 SOP

页面内已写入简化 SOP，核心规则是：

- 先看最新状态与风险，再决定是否重跑
- 研究输入不够时先回补 Phase 3
- 写稿质量不够时直接重跑 Phase 4
- 只有 latest accepted generation 才允许推草稿
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
- `/api/v1/tasks/{task_id}/workspace` API 测试
- 全量测试通过

服务器已完成：

- `GET /admin/phase5`
- `GET /api/v1/tasks/{task_id}/workspace`
- `GET /api/v1/tasks?active_only=true`

当前测试结果：

- `pytest -q` -> `29 passed`
- `python3 -m compileall app tests` -> 通过

## 8. 下一步建议

如果继续推进 Phase 5，优先级建议如下：

1. 增加 generation 间 diff 视图，而不只是版本卡片并排
2. 增加人工确认通过/驳回动作，而不只依赖模型审稿结论
3. 为后台接入最小登录保护，而不是只靠 Bearer Token
4. 增加“我的待处理任务 / 今日新增失败任务”这类面向运营的快捷视图
