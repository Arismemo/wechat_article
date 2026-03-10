# v1.1.0 之后的后台前端优化总方案

更新时间：2026-03-10
状态：Planned
适用范围：`/admin`、`/admin/phase5`、`/admin/phase6`、`/admin/console`、`/admin/settings`

## 1. 文档定位

这份文档不是视觉灵感草稿，也不是零散建议汇总，而是当前项目后台前端的完整优化方案。

目标只有一个：

- 把已经能跑的后台页面，收束成一套真正适合单人高频使用的“编辑部作战台”。

这份方案解决的是：

- 页面已经有功能，但信息层级不稳定。
- 页面之间能跳转，但上下文经常断。
- 有监控、有审核、有设置，但视觉和交互像几套独立页面拼起来。
- 代码仍以 FastAPI 直出 HTML 为主，如果没有明确的共享 UI 基座，后续改动会继续复制样式和脚本。

## 2. 输入来源

这份方案明确基于以下输入整理，不是凭空抽象出来的：

### 2.1 遗留交接文档

- [docs/handoff-2026-03-10.md](/Users/liukun/j/code/wechat_artical/docs/handoff-2026-03-10.md)

交接文档里与前端直接相关的关键约束有三条：

- 当前后台页仍是 FastAPI 直出 HTML。
- 继续收口现有入口，不新建一套重复后台。
- 改版实施时优先扩展 [admin_ui.py](/Users/liukun/j/code/wechat_artical/app/api/admin_ui.py)，先抽壳层和通用 tokens，再逐页改。

### 2.2 路线图与既有设计文档

- [docs/post-v1.1.0-roadmap.md](/Users/liukun/j/code/wechat_artical/docs/post-v1.1.0-roadmap.md)
- [docs/post-v1.1.0-task-plan.md](/Users/liukun/j/code/wechat_artical/docs/post-v1.1.0-task-plan.md)

路线图已经明确了前端方向：

- `/admin` 要成为单人主工作台。
- “下一步”要从一句文案升级成结构化动作卡。
- 会话失效后要保留上下文。
- 审核页、工作区、监控页都要下沉原始 JSON，上浮摘要。

### 2.3 直接加载的 antigravity 前端 skills

本次已直接读取以下本地 skill：

- `/Users/liukun/.gemini/antigravity/skills/creative-frontend/SKILL.md`
- `/Users/liukun/.gemini/antigravity/skills/web-design-guidelines/SKILL.md`
- `/Users/liukun/.gemini/antigravity/skills/web-design-guidelines/vercel-guidelines.md`

这两类 skill 对本项目的实际影响分别是：

- `creative-frontend`
  - 要求视觉方向明确，避免模板化后台和泛化 AI 审美。
  - 鼓励选定一个清晰的概念方向，然后一致执行。
  - 明确反对默认白底、紫色 SaaS 渐变、通用卡片模板和无个性的系统字体组合。
- `web-design-guidelines`
  - 要求所有交互都有清晰焦点状态。
  - 强调表单标签、语义元素、`aria-live`、键盘可达、`prefers-reduced-motion`。
  - 要求 URL 与页面状态同步， destructive action 必须确认，异步反馈必须清楚。
  - 强调长内容、空态、错误态、移动端、性能和布局安全性。

### 2.4 当前代码基线

当前共享前端基础主要来自：

- [app/api/admin_ui.py](/Users/liukun/j/code/wechat_artical/app/api/admin_ui.py)
- [app/api/admin.py](/Users/liukun/j/code/wechat_artical/app/api/admin.py)
- [app/api/admin_console.py](/Users/liukun/j/code/wechat_artical/app/api/admin_console.py)

当前已具备但尚未完全统一的能力包括：

- 顶部后台导航
- Skip link
- 基本的 `focus-visible`
- 局部 `localStorage` 恢复
- 异步状态提示
- 部分页面已有 Hero、Overview、Workspace 的雏形

## 3. 当前前端问题诊断

## 3.1 已经做对的部分

- 页面角色已经分清：
  - `/admin` 负责日常主流程
  - `/admin/phase5` 负责审核
  - `/admin/phase6` 负责反馈
  - `/admin/console` 负责排障
  - `/admin/settings` 负责运行参数与模型
- 关键工作区数据已经逐步聚合：
  - `selected_generation`
  - `timeline`
  - `related_articles`
  - `ai_trace_diagnosis`
- 最近几轮修复说明页面不是不能改，而是缺少统一的共享层。

## 3.2 当前最突出的前端问题

### 3.2.1 壳层统一度不够

- 顶部导航已存在，但各页 Hero、概览条、状态条、卡片层级和动作反馈仍各写各的。
- 同样的“状态提示 / 输出面板 / 空态 / 说明文案”在多个页面重复出现，但视觉和交互不完全一致。

### 3.2.2 页面之间的工作上下文仍然会断

- `task_id`、筛选、搜索词、最近输入的保留策略还不统一。
- 某些页面有 `localStorage`，某些页面只有 query，某些页面两者都不完整。
- `401` 场景下的恢复方式也不统一。

### 3.2.3 信息层级不稳定

- 某些页面已经开始“摘要在上、原始 JSON 在下”，但还没有成为全后台统一原则。
- 有些高频判断仍然需要先展开原始内容或滚很多区域才能做决定。

### 3.2.4 视觉语言已经开始形成，但还没收口

- `/admin`、`/admin/console`、`/admin/settings` 已经有更清晰的气质方向。
- 但字体、间距、卡片密度、按钮层级、状态语义、异步反馈方式还没有收成系统。

### 3.2.5 代码层重复明显

- FastAPI 直出 HTML 下，样式和脚本片段很容易在不同页面重复复制。
- 如果不尽快抽共享 tokens、shared shell、shared script helpers，后续每做一页都会放大维护成本。

## 4. 总体设计策略

## 4.1 核心概念

统一采用一个明确的设计方向：

- 名称：编辑部作战台
- 气质：新闻编辑台 + 内容工厂控制台 + 档案式工作区
- 关键词：克制、可信、锐利、密集、可判断、非模板化

这不是一个“看起来很现代的后台”，而是一个“让人一进来就知道先做什么、在哪里判断、哪里排障、哪里收口”的工作台。

## 4.2 用户模型

近期只有 1 个实际使用者，方案必须围绕单人高频操作设计：

- 不为多角色分工预留复杂导航
- 不为权限体系预留大量视觉占位
- 不把首页做成“部门分发表”
- 不把信息拆到过多页面才看得全

## 4.3 设计原则

从 `creative-frontend` 和 `web-design-guidelines` 抽取后，本项目的前端原则固定为：

- 概念要统一：所有页面必须像同一套系统，而不是五套模板。
- 首屏有主轴：进入页面 3 秒内能知道“这里是做什么的”和“先做什么”。
- 摘要优先：高频判断永远先看摘要，技术细节和原始 JSON 永远下沉。
- 状态清晰：加载中、失败、成功、警告、阻断要在视觉和文案上都能立刻区分。
- 上下文不丢：刷新、401、切页后，尽量能回到之前的工作位置。
- 无障碍合格：语义标签、可见焦点、`aria-live`、键盘操作、移动端触达都必须达标。

## 5. 视觉系统方案

## 5.1 视觉语言

- 背景不是纯白后台，而是浅纸色底叠加轻微纹理、渐变和秩序化层次。
- 标题采用带出版感的衬线，正文与表单采用高可读无衬线。
- 重点不是“把每个卡片都做得很漂亮”，而是把视觉权重压到“当前最该做什么”和“哪里有风险”上。

## 5.2 字体建议

- 标题：`Noto Serif SC` / `Source Han Serif SC`
- 正文与表单：`Noto Sans SC` / `Source Han Sans SC`
- 数字与状态：`font-variant-numeric: tabular-nums`

## 5.3 色板建议

- `--bg-paper: #f3ede3`
- `--bg-panel: rgba(255, 250, 244, 0.9)`
- `--ink-strong: #171717`
- `--ink-soft: #5f5a54`
- `--accent-forest: #1e5a4f`
- `--accent-brass: #9c6a22`
- `--accent-alert: #a14032`
- `--accent-focus: #c4497a`
- `--line-soft: rgba(50, 38, 22, 0.14)`

状态使用规则：

- 绿色：当前主动作、通过、可继续
- 铜金：待判断、中间态、提醒
- 赤红：失败、风险、阻断、危险动作
- 焦点粉：仅用于 `focus-visible`、当前高亮和极少数强调

## 5.4 动效建议

- 只允许 `transform` 和 `opacity`
- 禁止 `transition: all`
- 默认时长控制在 `150ms` 到 `240ms`
- 必须支持 `prefers-reduced-motion`
- 页面加载优先使用整块卡片的渐进出现，而不是零碎的小动画

## 6. 共享 UI 基座

## 6.1 共享壳层

所有后台页统一为四层：

1. 顶部粘性导航
2. 页面角色 Hero
3. 首屏概览条
4. 主工作区

当前 [admin_ui.py](/Users/liukun/j/code/wechat_artical/app/api/admin_ui.py) 只负责导航，下一步要扩成完整共享壳层。

## 6.2 建议新增或抽取的共享模块

- `AdminShell`
- `HeroStatusCard`
- `OverviewStrip`
- `FocusActionCard`
- `StickyContextBar`
- `EmptyStateCard`
- `InlineResult`
- `DebugOutputPanel`
- `EntityMetaGrid`
- `SectionHeader`
- `TimelineSteps`
- `ReferenceArticleCard`
- `DiffSummaryCard`

## 6.3 共享状态模型

所有页面统一使用下面四层状态表达：

- 系统状态：空闲、加载中、成功、失败、需关注
- 任务状态：待人工审核、待重写、待推草稿、已完成、失败
- 推荐动作：先审核、先推稿、先补反馈、先排障、先刷新
- 风险等级：低、中、高、阻断

不要每一页自己发明状态文案。

## 6.4 共享交互约定

- 所有异步操作都有明确结果反馈，并指向下一步。
- 危险动作必须二次确认。
- 表单结果不能只藏在折叠面板深处。
- 当前上下文要尽可能写进 URL。
- 还没提交但用户已经输入的内容，优先保存在 `localStorage`。

## 6.5 URL 与本地状态分工

统一约定：

- URL 负责：
  - `task_id`
  - 主筛选
  - tab / mode
  - 需要分享或深链的状态
- `localStorage` 负责：
  - 最近输入
  - 暂存筛选
  - 展开折叠偏好
  - 告警静默
  - 上次停留上下文

## 6.6 会话失效恢复策略

所有后台页统一实现：

- 任何 `401` 错误文案都明确说明“刷新后可恢复上下文”
- 进入页面时优先恢复：
  - 最近 `task_id`
  - 主筛选
  - 搜索词
  - 最近输入内容
- 页面刷新后重新拉取数据时，尽量回到相同任务和相同工作区

## 6.7 必须遵守的 Web Guideline 清单

这部分直接来自 `web-design-guidelines`，本项目前端改版必须视为强约束：

- 所有 action 必须用 `<button>`，所有导航必须用 `<a>`
- Icon-only 按钮必须有 `aria-label`
- 所有表单控件必须有 `<label>` 或 `aria-label`
- 所有异步状态和结果都要有 `aria-live="polite"`
- 交互元素必须有清晰的 `:focus-visible`
- 长文本、长链接、空数组、空态必须有稳定降级
- 不能使用 `transition: all`
- 不能靠点击 `div` 做按钮
- 不能只给桌面态，不给移动端滚动和布局策略

## 7. 页面级优化方案

## 7.1 `/admin`：单人主工作台

### 当前问题

- 已经有主工作台雏形，但“下一步”仍偏一句话。
- 左侧任务列表仍然更像任务清单，而不是优先级队列。
- 工作区内容已经很多，但还不够形成“80% 日常判断不跳页”的主入口。

### 目标结构

- 首屏焦点条：`待人工处理`、`待推草稿`、`今日失败`、`异常堆积`
- 左栏：任务队列 Dock
- 右栏：当前任务 Context Desk

### 必须落地的交互

- “下一步”升级成结构化 `FocusActionCard`
  - 当前卡点
  - 推荐动作
  - 推荐理由
  - 风险提示
  - 去哪里处理
- 任务列表按“最值得先处理”排序，而不是纯时间倒序
- 工作区默认展示：
  - 当前采用版本摘要
  - 参考文章摘要
  - 流水线摘要
  - AI 去痕诊断摘要
  - 最近动作摘要

### 预期结果

- 80% 的日常判断不需要跳去其它页面
- 打开首页就能知道“今天先处理什么”

## 7.2 `/admin/phase5`：审核驾驶舱

### 当前问题

- 已经具备历史稿、参考文章、时间线和 AI 去痕诊断，但首屏判断密度还不够高。
- 审核动作、版本比较、风险判断仍然有继续收束空间。

### 目标结构

- 顶部：粘性 Decision Bar
- 中央：当前采用稿 + diff 摘要 + 历史稿比较
- 右侧：风险、参考文章、时间线、AI 去痕诊断

### 必须落地的交互

- 首屏优先展示：
  - 是否建议通过
  - 是否允许推稿
  - 当前采用版本
  - 主要风险点
  - AI 痕迹等级
  - 是否触发 humanize
- diff 默认先看摘要，再展开全文
- 历史稿比较固定支持：
  - 当前重写稿
  - 上一版
  - 最近一次已通过稿
  - 当前采用稿
- “通过 / 驳回 / 允许推稿 / 禁止推稿 / 采用此版本”收成一个粘性操作带

### 预期结果

- 不展开原始 JSON，也能完成审核判断
- 历史稿比较与人工选择在同一工作上下文完成

## 7.3 `/admin/phase6`：反馈实验台

### 当前问题

- 页面职责较多，容易让“当前任务反馈处理”和“长期实验沉淀”混在一起。
- 没有 `task_id` 时，某些动作仍然显得过强。

### 目标结构

- 第一层：当前任务反馈回收
- 第二层：实验榜、风格资产、复用结论

### 必须落地的交互

- 没有 `task_id` 时，任务强绑定动作自动弱化
- 明确提示：
  - 当前任务还缺什么反馈
  - 先同步、先导入，还是先看实验
- 实验榜优先显示：
  - 样本量
  - 趋势方向
  - 是否建议继续
  - 最近观察窗口

### 预期结果

- Phase 6 从“功能集合页”变成“反馈回收与实验沉淀台”

## 7.4 `/admin/console`：排障战情室

### 当前问题

- 已经有趋势、告警、worker 观测和看板，但默认视图仍可继续压缩“技术味”。
- 需要把运营视角与排障视角更明确地区分开。

### 目标结构

- 默认：运营视角
- 切换后：排障视角

### 默认视角展示

- 当前异常概况
- 告警与静默
- 最近 24 小时趋势
- 积压队列
- 最近失败任务
- 建议去哪里处理

### 排障视角再展开

- SSE 状态
- 原始快照
- 队列深度细节
- worker 心跳细节
- 原始 payload

### 预期结果

- 先判断“要不要介入”
- 再决定“回 `/admin`、去 Phase 5，还是留在 console 排障”

## 7.5 `/admin/settings`：运行参数与模型控制台

### 当前问题

- 关键能力已具备，但配置、验证、历史结果三层还可以再拉开。
- 测试结果虽然已修复为可见，但还缺一个更明确的“当前生效配置”顶层视图。

### 目标结构

- 第一层：当前生效配置
- 第二层：可编辑配置
- 第三层：测试结果与验证记录

### 必须落地的交互

- 当前 provider / model 做成独立顶栏
- 测试结果不藏在折叠深处
- 保存、测试、恢复的结果默认持久显示，直到下一次主动清空
- 只读环境状态与可编辑设置彻底区分
- 缺失项显示为阻断风险，不只是普通提醒

### 预期结果

- 设置页从“配置表”变成“配置工作台”

## 8. 技术落地方案

## 8.1 不切前端框架，先做共享 UI 层

短期不建议为了改版切 React。正确顺序是：

1. 先扩展 [admin_ui.py](/Users/liukun/j/code/wechat_artical/app/api/admin_ui.py)
2. 再拆共享 tokens 和共享脚本 helper
3. 最后逐页迁移

## 8.2 建议的文件拆分

- `app/api/admin_ui.py`
  - 导航、壳层、共享基础样式
- `app/api/admin_ui_tokens.py`
  - 颜色、间距、阴影、字体、状态色、响应式断点
- `app/api/admin_ui_scripts.py`
  - 请求封装、状态提示、输出面板、会话恢复、URL 同步、空态渲染 helper
- `app/api/admin_page_sections.py`
  - Hero、Overview、EmptyState、ResultCard 等片段

目标不是组件化炫技，而是减少多页重复维护。

## 8.3 共享脚本必须统一的能力

- `request()` 统一处理：
  - `401`
  - JSON / text 错误
  - 网络失败
- `persistDraft()` / `restoreDraft()`
- `syncUrlState()`
- `renderResult()`
- `renderEmptyState()`
- `withButtonBusy()`
- `revealDebugOutput()`

## 8.4 后端视图模型建议

要让前端真正顺手，后端返回也要更像“工作台视图”，而不是原始数据库拼装：

- `/admin`
  - `next_actions`
  - `priority_reason`
  - `task_summary`
- `/admin/phase5`
  - `review_summary`
  - `risk_summary`
  - `diff_summary`
- `/admin/phase6`
  - `feedback_summary`
  - `experiment_summary`
- `/admin/settings`
  - `test_result_summary`
  - `effective_runtime_summary`
- `/admin/console`
  - `alerts`
  - `trends`
  - `operations_summary`

## 8.5 测试策略

每一轮前端改动都要至少覆盖三类验证：

- 路由 HTML 断言
  - 页面里关键结构、关键文案、关键脚本逻辑存在
- API/服务断言
  - 聚合字段和状态不回归
- 浏览器级 smoke test
  - 至少覆盖 `/admin`、`/admin/phase5`、`/admin/settings` 的主操作流

## 9. 实施顺序

## M0：共享基座审计

- 审查现有页面的重复 CSS、重复 JS、重复状态文案
- 把 `admin_ui.py` 升级成真正的共享壳层入口

## M1：设计系统与共享壳层

- 统一色板、字体、按钮层级、状态色、阴影和卡片规范
- 抽共享输出面板、状态条、概览卡、空态卡

## M2：先改高频主路径

- 先改 `/admin`
- 再改 `/admin/phase5`

原因：

- 这两页是单人使用主路径
- 改好后收益最大，能立刻减少切页和重复判断

## M3：再改辅助页

- `/admin/phase6`
- `/admin/settings`
- `/admin/console`

原因：

- 这些页面虽然重要，但不是每次进入系统都先打开的入口

## M4：统一恢复与深链

- 统一 URL 状态
- 统一 `localStorage`
- 统一 401 恢复
- 统一跨页深链上下文

## M5：浏览器级回归与细节打磨

- 键盘流
- 焦点流
- 空态
- 错误态
- 移动端布局
- `prefers-reduced-motion`

## 10. 验收标准

达到以下标准，才算前端优化真正完成：

- 不打开原始 JSON，也能完成大多数日常判断。
- `/admin` 首屏能直接告诉操作者今天先做什么。
- `/admin/phase5` 能在单页上下文完成风险判断、历史稿比较和动作执行。
- `/admin/phase6` 能在单页完成反馈回收与实验复盘闭环。
- `/admin/settings` 的动作结果清晰、可追溯、不会被刷新覆盖。
- `/admin/console` 能先判断异常，再决定是否进入深度排障。
- 页面之间跳转后，当前任务与主要筛选条件不会频繁丢失。
- 支持键盘操作、可见焦点、空态和移动端阅读。

## 11. 明确不做的方向

- 不做白底紫渐变 SaaS 风格
- 不做模板化后台换色
- 不做再新起一套后台
- 不做为了“现代感”而牺牲信息密度
- 不做把原始 JSON 包装成“高级工作区”
- 不做短期内的多用户、权限或审批流视觉设计

## 12. 风险与注意点

- FastAPI 直出 HTML 的最大风险不是实现不了，而是复制粘贴式演进会越来越难维护。
- 如果先动页面、后抽共享层，会把技术债再复制一轮。
- 如果只改视觉，不改状态模型和上下文恢复，页面还是会“不顺手”。
- 如果不补浏览器级回归，后续脚本小改动很容易带来交互倒退。

## 13. 与交接文档的关系

这份方案是对交接文档中前端部分的正式展开版。

交接文档给出的前端结论是：

- 继续沿用现有后台入口
- 不切新框架
- 先扩展 [admin_ui.py](/Users/liukun/j/code/wechat_artical/app/api/admin_ui.py)
- 先抽壳层和 tokens，再逐页改

本文把这些结论补成了：

- 完整的视觉方向
- 完整的交互原则
- 五个后台页的具体优化方案
- 共享 UI 基座的技术实现路径
- 明确的实施顺序与验收标准

## 14. 下一步建议

如果接下来开始真正实施，推荐按这个顺序启动：

1. 先在 [admin_ui.py](/Users/liukun/j/code/wechat_artical/app/api/admin_ui.py) 抽共享 tokens、壳层和共用脚本 helper。
2. 第一批只做 `/admin` 和 `/admin/phase5`，因为这是收益最高的主路径。
3. 第二批再收 `/admin/phase6`、`/admin/settings`、`/admin/console`。
4. 每批都补页面源码断言和浏览器级 smoke test。
