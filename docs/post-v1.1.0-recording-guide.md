# v1.1.0 之后的记录说明

更新时间：2026-03-09
状态：Active

## 1. 目的

这份文档用于约束下一阶段任务的记录方式，避免后续实现只留在聊天上下文里，或只有代码改动没有设计、验收和发布证据。

当前适用的任务包：

- TP-01：参考文章可查看
- TP-02：历史稿对比与人工选择
- TP-03：流水线详细日志与时间线
- TP-04：AI 去痕触发原因可见化

## 1.1 当前实现快照

`2026-03-09` 已完成 TP-01 到 TP-04 的本地实现，当前已落地的记录点如下：

- 页面：
  - `/admin`
  - `/admin/phase5`
- API：
  - `GET /api/v1/tasks/{task_id}/workspace`
  - `POST /internal/v1/tasks/{task_id}/select-generation`
- 服务：
  - `TaskWorkspaceQueryService`
  - `TaskGenerationSelectionService`
  - `ManualReviewService`
- 当前新增字段：
  - `workspace.related_articles`
  - `workspace.selected_generation`
  - `workspace.timeline`
  - `generation.ai_trace_diagnosis`
  - `generation.is_selected`
  - `generation.draft_saved`
  - `generation.wechat_media_id`
- 当前验证结果：
  - `pytest -q -> 93 passed`
  - `python3 -m compileall app tests -> 通过`

后续如果补服务器部署或正式发版，应继续补：

- 部署 commit
- 服务器 smoke test
- 是否需要重启 worker
- 线上已知边界

## 2. 记录原则

- 记录要能回答三件事：为什么改、具体改了什么、如何证明它按预期工作。
- 记录优先写事实和约束，不写空泛目标。
- 页面、接口、状态、字段、审计动作、环境变量的名称必须和代码一致。
- 如果范围变化，先改文档，再继续实现。
- 如果某项能力最终决定不做，也要在文档里明确写“不做”的原因，而不是静默丢失。

## 3. 开工前必须记录

每个任务包真正开始前，至少补齐以下信息：

- 任务编号与标题
- 目标与边界
- 关联页面
- 关联 API / service / 表结构
- 当前现状
- 计划怎么接线
- 明确不做什么
- 验收标准
- 风险与依赖

建议记录位置：

- 总体任务拆解放在 [docs/post-v1.1.0-task-plan.md](/Users/liukun/j/code/wechat_artical/docs/post-v1.1.0-task-plan.md)
- 若设计存在明显技术取舍，再补 `docs/adr/`

## 4. 设计完成后必须记录

当接口、页面结构或状态机方案确定后，需要把这些内容写入对应阶段文档：

- 改 Phase 4 流水线或审稿逻辑：
  - 更新 `docs/phase-4/generation-and-review.md`
- 改审核台或工作区：
  - 更新 `docs/phase-5/admin-console.md`
- 改统一控制台或监控视图：
  - 更新 `docs/phase-7/console-monitoring.md`

每次至少记录：

- 页面入口或 API 入口
- 新增或修改的字段
- 新增或修改的状态流 / 操作流
- 关键设计约束
- 当前限制

## 5. 实现过程中必须记录

### 5.1 通用记录项

- 涉及的文件与模块
- 是否新增内部接口
- 是否修改现有返回结构
- 是否新增审计动作
- 是否有 schema 变更
- 是否涉及环境变量或运行参数
- 是否需要 worker 配合改动

### 5.2 针对 TP-01 的额外记录

- 最终复用的是 `brief` 还是 `workspace`
- 参考文章展示哪些字段
- 链接如何打开
- 页面内是否支持快速预览
- 空态、无链接、失效链接的处理方式

### 5.3 针对 TP-02 的额外记录

- 历史稿比较的版本选择规则
- 比较维度：
  - 标题
  - 摘要
  - 正文
  - 审稿结论
  - AI 去痕状态
- 是否提供“保留某版”动作
- 若提供动作，对应的审计日志名和冲突保护规则

### 5.4 针对 TP-03 的额外记录

- 最终纳入时间线的事件清单
- 每个事件展示的摘要字段
- 原始 payload 是否保留展开入口
- 时间线是前端拼装还是后端聚合
- 与 `/admin/console` 的字段和命名是否统一

### 5.5 针对 TP-04 的额外记录

- AI 去痕触发阈值
- 风险门控条件
- `rewrite_targets` 的判定来源
- `skipped` 原因枚举
- 页面文案与代码判断的映射关系

## 6. 提交前验证必须记录

任何一个任务包完成后，至少记录：

- 本地验证命令
- 重点覆盖用例
- 关键接口响应
- 页面关键现象
- 已知边界

优先记录方式：

- 若只是本地验证，写入对应阶段文档或任务记录补充章节
- 若已经部署到服务器，写入对应 `deployment-log.md`

## 7. 发布后必须记录

如果某个任务包进入服务器或正式版本，必须补这些信息：

- Git commit
- 提交标题
- 部署方式
- 是否有 migration
- 是否需要重启 worker
- 服务器 smoke test
- 当前结论
- 未解决问题

这部分记录应优先写入：

- `docs/phase-4/deployment-log.md`
- `docs/phase-6/deployment-log.md`
- `docs/phase-7/deployment-log.md`
- 未来如进入正式版本，再写对应 release 文档

## 8. 最小记录模板

后续任何一个任务包都至少应保留下面这些最小记录项：

```md
## 任务
- 编号：
- 标题：
- 状态：

## 目标
- 

## 本轮要做
- 

## 本轮不做
- 

## 涉及范围
- 页面：
- API：
- 服务：
- 数据：

## 设计约束
- 

## 验收标准
- 

## 本地验证
- 命令：
- 结果：

## 部署记录（如有）
- commit：
- 方式：
- smoke test：

## 已知边界
- 
```

## 9. 与其它文档的关系

- 路线图负责说明方向与优先级：
  - [docs/post-v1.1.0-roadmap.md](/Users/liukun/j/code/wechat_artical/docs/post-v1.1.0-roadmap.md)
- 任务规划负责说明具体要做哪些任务：
  - [docs/post-v1.1.0-task-plan.md](/Users/liukun/j/code/wechat_artical/docs/post-v1.1.0-task-plan.md)
- 本文档负责说明这些任务后续如何被持续记录、验证和发布
