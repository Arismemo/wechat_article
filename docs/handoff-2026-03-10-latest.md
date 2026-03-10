# 交接文档（2026-03-10，最新状态）

更新时间：2026-03-10
适用对象：即将接手本仓库、继续推进后台前端改版与日常维护的开发者
说明：本文档是截至 `2026-03-10` 的最新交接材料，补充了 [docs/handoff-2026-03-10.md](/Users/liukun/j/code/wechat_artical/docs/handoff-2026-03-10.md) 之后的新实现、新部署和新的待办。旧文档保留作为 `v1.1.2` 发布基线记录。

## 1. TL;DR

接手后先记住 6 件事：

1. 当前本地与 `origin/main` 的最新提交是 `6d7fb10 docs: record cc22580 deployment`。
2. 当前服务器运行代码是 `cc22580 feat: surface phase5 decision summaries`。
3. 服务器仓库目录是 `/home/liukun/j/code/wechat_artical`，访问域名是 `https://auto.709970.xyz`。
4. 最新一轮已完成部署和公网 smoke test，`/healthz`、`/admin`、`/admin/phase5`、`/api/v1/admin/monitor/snapshot` 都通过。
5. 当前主线工作不再是“修线上事故”，而是继续推进后台前端改版，优先收 `/admin` 和 `/admin/phase5`。
6. 近期规划明确不考虑多用户、权限管理和登录体系重构，按单人高频工作流继续做。

## 2. 当前代码与部署状态

### 2.1 Git 状态

- 本地 `HEAD`：`6d7fb10 docs: record cc22580 deployment`
- 远端 `origin/main`：`6d7fb10 docs: record cc22580 deployment`
- 服务器运行代码：`cc22580 feat: surface phase5 decision summaries`

说明：

- 本地与远端已经同步。
- 服务器只比 Git `HEAD` 少最后一笔文档提交，功能代码已经是最新上线版本。
- 如果接手人要再次部署功能，不需要先处理脏工作树；服务器仓库是干净的。

### 2.2 最近关键提交

- `6d7fb10 docs: record cc22580 deployment`
  - 只更新部署文档，未重新部署到服务器。
- `cc22580 feat: surface phase5 decision summaries`
  - 已部署上线。
  - 核心内容：
    - `Phase 5` 首屏新增 4 张决策摘要卡
    - `AdminUiShared` 共享脚本 helper 正式接入
    - 后台模板 `replaceAll` 兼容性问题清理
- `332d74c feat: add shared admin shell foundation`
  - 已推送，作为共享后台壳层第一刀。
- `f210204 docs: finalize v1.1.2 release records`
  - `v1.1.2` 发布收口文档提交。
- `af101ec feat: add phase7f monitor alerts and trends`
  - 已上线，提供 Phase 7F 第一刀告警和趋势能力。
- `f86531c fix: restore admin portal context after session expiry`
  - 已上线，修复 `/admin` 会话失效后上下文恢复。
- `50dfdce fix: preserve llm test output in settings`
  - 已上线，修复设置页测试结果被刷新覆盖。
- `3013203 fix: repair admin settings page script escaping`
  - 已上线，修复设置页一直停在“等待加载”。

### 2.3 服务器与部署方式

- 服务器：`liukun@100.112.123.6`
- 项目目录：`/home/liukun/j/code/wechat_artical`
- 标准部署方式：
  - `cd /home/liukun/j/code/wechat_artical`
  - `git pull --ff-only origin main`
  - `docker compose up -d --build api phase2_worker phase3_worker phase4_worker feedback_worker`

补充说明：

- 这轮 `cc22580` 已按上面方式完成部署。
- `postgres` / `redis` 作为依赖容器保持 healthy。
- `api` 和 `phase2_worker / phase3_worker / phase4_worker / feedback_worker` 已重建并启动。

## 3. 当前线上可用能力

### 3.1 后台主入口

- `/admin`
  - 单人总览主工作台
  - 已具备结构化“下一步”动作区
  - 已具备会话失效后的上下文恢复
  - 已具备工作区摘要、采用版本、参考文章、AI 去痕诊断、流水线时间线
- `/admin/phase5`
  - 审核台
  - 已具备历史版本、版本 diff、采用版本、参考文章、AI 去痕诊断、流水线时间线
  - 已新增首屏 4 张决策摘要卡
- `/admin/phase6`
  - 反馈台
  - 已具备反馈同步、反馈导入、实验榜、风格资产基础能力
- `/admin/console`
  - 高级监控台
  - 已具备告警、趋势、worker 观测、SSE 快照
- `/admin/settings`
  - 运行参数与 LLM 配置页
  - 已具备供应商 / 模型配置与一键连通性测试

### 3.2 LLM 运行时配置

已落地：

- `/admin/settings` 支持配置供应商列表、供应商对应模型、当前 active provider 和 analyze/write/review 三个模型槽位。
- 支持测试连通性，测试前会先保存当前配置。
- 已兼容 `/v1/responses` 协议的供应商。

当前默认生效仍是：

- `active_provider_id = env-default`
- `analyze_model = glm-5`
- `write_model = glm-5`
- `review_model = glm-5`

说明：

- nowcoding / 其它供应商配置能力已做完，但当前线上默认仍回到 ZHIPU 环境默认配置。

### 3.3 最近一轮前端改版已完成内容

本轮已经实装并上线的前端改版内容：

- 共享后台壳层第一刀
  - 统一导航
  - 统一共享样式注入
  - 5 张主页面接到同一套壳层入口
- 共享脚本 helper 第一刀
  - `AdminUiShared.escapeHtml`
  - `AdminUiShared.apiUrl`
  - `AdminUiShared.parseJsonResponse`
  - `AdminUiShared.setButtonBusy`
  - `AdminUiShared.storageGet / storageSet / storageRemove`
  - `AdminUiShared.buildSessionExpiredError`
- `Phase 5` 首屏信息层级优化
  - `当前审稿建议`
  - `当前推稿判断`
  - `主要风险`
  - `版本变化摘要`
  - `diff` 视图上移到版本列表之前
- Safari / WebView 兼容性修补
  - 后台相关模板里的 `replaceAll` 已清理，改回正则 `replace(...)`

## 4. 已完成 / 进行中 / 待完成

## 4.1 已完成

- `v1.1.2` 发布收口已完成。
- `Phase 7F` 第一刀已上线：
  - 告警分级
  - `dedupe_key`
  - 前端临时静默
  - 最近 24 小时趋势
- `/admin` 会话失效后上下文恢复已上线。
- 设置页“等待加载”问题已修复。
- 设置页“测试连通性结果被刷新覆盖”问题已修复。
- LLM 供应商 / 模型配置页已上线。
- 共享后台壳层第一刀已完成。
- `Phase 5` 决策摘要第一刀已完成并上线。
- 最新一轮部署记录已写入 [docs/phase-7/deployment-log.md](/Users/liukun/j/code/wechat_artical/docs/phase-7/deployment-log.md)。

## 4.2 进行中

- 后台前端改版正在进行，但只完成了前两刀：
  - 第一刀：共享后台壳层
  - 第二刀：共享交互 helper + `Phase 5` 首屏决策摘要
- 整体前端改版仍处于“已启动，未收口”阶段。
- 目前最明显的进度特点是：
  - `/admin` 已有不错的工作台雏形
  - `/admin/phase5` 首屏判断密度明显提升
  - 其它页面还没有同步到同样的信息层级和共享交互深度

## 4.3 待完成

短期高优先级待做：

- 把 `/admin` 继续收成单人日常主工作台
  - 任务队列从“时间倒序”进一步收成“最值得先处理”的排序
  - “下一步”继续从文案升级成更完整的结构化动作卡
  - 工作区继续上浮摘要，下沉原始 JSON
- 继续优化 `/admin/phase5`
  - 历史稿比较再收一轮
  - 驳回重写后的历史版本对比和人工选版链路补齐
  - 通过 / 驳回 / 推稿相关动作继续压缩成更明确的粘性操作带
- `/admin/phase6`
  - 拆出“当前任务反馈处理”和“长期实验沉淀”两层结构
- `/admin/console`
  - 更明确地区分“运营默认视角”和“排障视角”
- `/admin/settings`
  - 增加更清晰的“当前生效配置”顶层视图
  - 保存 / 测试 / 恢复结果继续做成更持久的结果区域
- 浏览器级 smoke test
  - 当前主要是 HTML 路由断言
  - 还缺 `/admin`、`/admin/phase5`、`/admin/settings` 的真实浏览器主流程回归

## 5. 交接给接手人的核心待办

建议按这个顺序继续推进，不要打乱：

1. 继续扩展共享 UI 层，而不是回到逐页复制样式 / JS
2. 先收 `/admin`
3. 再收 `/admin/phase5`
4. 然后做 `/admin/phase6`、`/admin/settings`
5. 最后再收 `/admin/console` 的默认视角与排障视角切换
6. 每一轮都补：
   - 页面 HTML 断言
   - 必要的接口断言
   - 浏览器级 smoke test

### 5.1 `/admin` 下一步建议

优先级最高，因为这是实际使用频率最高的入口。

建议继续做：

- 任务列表按优先级重排，而不是只按更新时间
- 把“当前卡点 / 推荐动作 / 推荐理由 / 风险提示 / 去哪里处理”固定收成 `FocusActionCard`
- 进一步上浮：
  - 当前采用版本摘要
  - 参考文章摘要
  - 流水线摘要
  - 最近动作摘要
- 让 80% 的日常判断尽量不需要跳页

### 5.2 `/admin/phase5` 下一步建议

当前已做了一半，但还没真正收成“审核驾驶舱”。

建议继续做：

- 历史稿比较固定支持：
  - 当前重写稿
  - 上一版
  - 最近一次已通过稿
  - 当前采用稿
- 给“驳回重写后”补完整的历史版本对比与人工选版链路
- 把“通过 / 驳回 / 允许推稿 / 禁止推稿 / 采用此版本”进一步整合为更稳定的操作带
- diff 继续维持“先摘要、后全文”

### 5.3 `/admin/phase6` 下一步建议

- 第一层只处理当前任务反馈
- 第二层再看实验榜、风格资产和长期沉淀
- 没有 `task_id` 时，任务强绑定动作应该自动弱化

### 5.4 `/admin/settings` 下一步建议

- 生效中的 provider / model 做成明显的顶栏摘要
- 测试结果不要藏在折叠区深处
- 阻断项要和普通提醒明显区分

### 5.5 `/admin/console` 下一步建议

- 默认先看运营视角：
  - 当前异常概况
  - 告警
  - 趋势
  - 积压
  - 最近失败任务
- 排障视角再展开：
  - SSE
  - 原始快照
  - 队列深度
  - worker 心跳
  - 原始 payload

## 6. 已知问题与风险

### 6.1 共享层仍未完全收口

虽然已经有 `AdminUiShared` 和共享壳层，但还没有彻底拆成独立模块文件。

当前文档里已经规划但尚未落地的拆分包括：

- `app/api/admin_ui_tokens.py`
- `app/api/admin_ui_scripts.py`
- `app/api/admin_page_sections.py`

所以现在的风险仍然是：

- FastAPI 直出 HTML 的模板字符串体积较大
- 多页脚本仍有重复逻辑
- 如果不继续沿共享层推进，后面又会回到复制粘贴式演进

### 6.2 浏览器级回归还不够

当前测试主要覆盖：

- `tests/test_app_routes.py`
- 部分 API / service 测试

还缺：

- 真实浏览器下的主路径验证
- 特别是：
  - `/admin` 任务切换与筛选
  - `/admin/phase5` 审核动作与 diff 交互
  - `/admin/settings` 保存与测试结果显示

### 6.3 线上与 Git HEAD 不完全一致

这是一个小风险，但需要明确告诉接手人：

- `origin/main` 当前是 `6d7fb10`
- 服务器运行代码是 `cc22580`
- 差异只有部署记录文档，不是功能代码

如果接手人要再次部署，只要正常 `git pull --ff-only origin main` 后再 `docker compose up -d --build ...` 即可。

### 6.4 近期规划边界

不要在接手后自行扩这些方向：

- 多用户
- 角色权限
- 新登录体系
- 再新起一套后台
- 为“现代感”而引入全新前端框架

当前既定策略非常明确：

- 继续沿用 FastAPI 直出 HTML
- 先做共享 UI 层
- 先收高频主路径
- 围绕单人高频工作流优化

## 7. 建议接手后的第一批动作

如果是一个新接手人，建议按下面顺序上手：

1. 先读这 4 份文档：
   - [docs/handoff-2026-03-10.md](/Users/liukun/j/code/wechat_artical/docs/handoff-2026-03-10.md)
   - [docs/handoff-2026-03-10-latest.md](/Users/liukun/j/code/wechat_artical/docs/handoff-2026-03-10-latest.md)
   - [docs/post-v1.1.0-roadmap.md](/Users/liukun/j/code/wechat_artical/docs/post-v1.1.0-roadmap.md)
   - [docs/post-v1.1.0-frontend-redesign-plan.md](/Users/liukun/j/code/wechat_artical/docs/post-v1.1.0-frontend-redesign-plan.md)
2. 本地先跑：
   - `python3 -m pytest tests/test_app_routes.py tests/test_admin_llm_api.py -q`
3. 去线上确认：
   - `/admin`
   - `/admin/phase5`
   - `/admin/settings`
   - `/admin/console`
4. 第一批只碰：
   - `app/api/admin_ui.py`
   - `app/api/admin.py`
   - `app/api/admin_console.py`
   - `tests/test_app_routes.py`
5. 继续推进时，优先完成 `/admin` 主工作台下一轮收口

## 8. 文档入口

这次交接最相关的文档入口：

- [docs/handoff-2026-03-10.md](/Users/liukun/j/code/wechat_artical/docs/handoff-2026-03-10.md)
- [docs/handoff-2026-03-10-latest.md](/Users/liukun/j/code/wechat_artical/docs/handoff-2026-03-10-latest.md)
- [docs/phase-7/deployment-log.md](/Users/liukun/j/code/wechat_artical/docs/phase-7/deployment-log.md)
- [docs/release-v1.1.2.md](/Users/liukun/j/code/wechat_artical/docs/release-v1.1.2.md)
- [docs/post-v1.1.0-roadmap.md](/Users/liukun/j/code/wechat_artical/docs/post-v1.1.0-roadmap.md)
- [docs/post-v1.1.0-frontend-redesign-plan.md](/Users/liukun/j/code/wechat_artical/docs/post-v1.1.0-frontend-redesign-plan.md)

## 9. 一句话结论

当前系统已经从“发布收口阶段”进入“前端改版实施阶段”。  
接手人不需要再去补发布闭环，应该直接从共享 UI 层继续推进 `/admin` 和 `/admin/phase5` 的下一轮收口。
