# 项目文档索引

更新时间：2026-03-07

## 文档留存原则

- 所有已确认的项目范围、接口约束、风险、环境变量、设计决策和阶段结论，必须写入 `docs/`，不能只保留在聊天上下文中。
- 任何阶段开始开发前，先补齐该阶段的输入文档；任何阶段结束后，补齐该阶段的结论和变更。
- 如果聊天中出现新的确认信息，后续实现前必须先同步到对应文档。
- 原始密钥和令牌不明文写入 Markdown；文档中只记录“已收到”、存放位置和对应环境变量名。
- 服务器部署时如果遇到端口冲突，只调整本项目端口，不修改服务器上其它服务的端口。

## 当前文档

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
- `docs/research-wechat-fetch-and-browser-options-2026-03-07.md`
  - 微信公众号读取方案、Claude Code skill 和浏览器自动化方案调研
- `docs/adr/0001-git-based-deploy.md`
  - 从文件拷贝切换到 Git 部署的技术决策

## 后续建议文档

- `docs/phase-3/research-pipeline.md`
- `docs/phase-4/generation-and-review.md`
- `docs/phase-5/admin-console.md`
- `docs/phase-6/feedback-loop.md`
- `docs/adr/`
  - 用于记录关键技术决策
