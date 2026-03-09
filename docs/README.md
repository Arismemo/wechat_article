# 项目文档索引

更新时间：2026-03-10

## 文档留存原则

- 所有已确认的项目范围、接口约束、风险、环境变量、设计决策和阶段结论，必须写入 `docs/`，不能只保留在聊天上下文中。
- 任何阶段开始开发前，先补齐该阶段的输入文档；任何阶段结束后，补齐该阶段的结论和变更。
- 如果聊天中出现新的确认信息，后续实现前必须先同步到对应文档。
- 原始密钥和令牌不明文写入 Markdown；文档中只记录“已收到”、存放位置和对应环境变量名。
- 服务器部署时如果遇到端口冲突，只调整本项目端口，不修改服务器上其它服务的端口。

## 当前文档

- `docs/post-v1.1.0-roadmap.md`
  - `v1.1.0` 之后的单人运营路线图，包含 P0 / P1 / P2 优先级、前端交互优化和明确不纳入项
- `docs/post-v1.1.0-task-plan.md`
  - 将下一阶段 4 个重点问题拆成可执行任务包、里程碑、验收与依赖
- `docs/post-v1.1.0-recording-guide.md`
  - 规定下一阶段任务的设计、实现、验证、发布记录方式
- `docs/wechat-content-factory-plan.md`
  - 总体方案、系统架构、状态机、Prompt、阶段计划
- `docs/phase-0/requirements-freeze.md`
  - 阶段 0 需求冻结文档
- `docs/phase-0/dependency-inventory.md`
  - 外部依赖清单与确认状态
- `docs/phase-0/risk-register.md`
  - 风险清单与缓解策略
- `docs/phase-0/environment-variables.md`
  - 环境变量清单与配置约束
- `docs/phase-0/confirmation-log.md`
  - 阶段 0 已确认输入与未决问题
- `docs/phase-0/ios-shortcuts.md`
  - iPhone 快捷指令接入约定、一站式入口与排查要点
- `docs/phase-1/backend-scaffold.md`
  - 阶段 1 后端骨架说明
- `docs/phase-1/database-schema.md`
  - 阶段 1 初版数据表说明
- `docs/phase-1/deployment-log.md`
  - 阶段 1 服务器部署与 smoke test 记录
- `docs/phase-2/wechat-integration.md`
  - 阶段 2 抓取、清洗、固定模板稿和微信草稿箱集成说明
- `docs/phase-2/deployment-log.md`
  - 阶段 2 服务器部署与联调记录
- `docs/phase-3/research-pipeline.md`
  - 阶段 3 研究层、同题搜索、差异矩阵和 Brief 管道说明
- `docs/phase-3/deployment-log.md`
  - 阶段 3 服务器部署与 smoke test 记录
- `docs/phase-4/generation-and-review.md`
  - 阶段 4 生成、审稿、重生成与手动/自动推草稿说明
- `docs/phase-4/deployment-log.md`
  - 阶段 4 服务器部署与收口记录
- `docs/phase-5/admin-console.md`
  - 阶段 5 后台工作台、人工审核与手动操作说明
- `docs/phase-6/feedback-loop.md`
  - 阶段 6 手工反馈导入、Prompt 实验榜与风格资产沉淀说明
- `docs/phase-6/deployment-log.md`
  - 阶段 6 服务器部署与 smoke test 记录
- `docs/phase-7/console-monitoring.md`
  - Phase 7 统一控制台、实时流、统计卡片和历史筛选说明
- `docs/phase-7/deployment-log.md`
  - Phase 7D / 7E 服务器部署、运行观测与发布收口记录
- `docs/phase-7/runtime-settings.md`
  - Phase 7 运行参数设置、后台会话、`.env` 只读状态和测试告警说明
- `docs/research-wechat-fetch-and-browser-options-2026-03-07.md`
  - 微信公众号读取方案、Claude Code skill 和浏览器自动化方案调研
- `docs/mvp-closeout-2026-03-08.md`
  - MVP 主链路收口结论与真实验收记录
- `docs/release-v1.1.0.md`
  - 第二版发布范围、验证结果、已知边界与正式发布结果
- `docs/release-v1.1.1.md`
  - TP-01 ~ TP-04 收口包发布说明、线上 smoke test 与 tag 结果
- `docs/release-process.md`
  - 标准版本发布流程、tag 前检查项与部署约束
- `docs/web-console-plan.md`
  - 网页端控制台历史规划文档与下一阶段建议
- `docs/adr/0001-git-based-deploy.md`
  - 从文件拷贝切换到 Git 部署的技术决策

## 后续建议文档

- `docs/adr/`
  - 用于记录关键技术决策
