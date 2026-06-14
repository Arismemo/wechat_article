# 设计规格:多Agent出版社编委会评审 · 2026-06-14

> 状态:**待评审**。分支 `feat/editorial-board`(stacked on `chore/audit-remediation`)。
> 来源:brainstorming 对话(2026-06-14)。落地调研依据 `ref/04-report.md`。

## 1. 目标与背景

为流水线产出的**每一篇**稿件增加一道"出版社编委会"评审:由代表全编制岗位的多个 agent **独立评审 → 多轮辩论至收敛 → 总编终裁**,产出 `通过/改/毙` 裁决 + 结构化修改指令,喂给现有自动修订机制。

定位:把当前 Phase4 的**单次 LLM 审稿**升级为**多视角对抗式评审**,显著降低"看似过审实则平庸/有AI味/不合规/无传播力"的稿件流出。对接已有的相似度硬门禁(T6)、审稿评分(Q-AB)、内容质量调研(`ref/`)。

非目标:编委会**不写稿**(写稿仍是 Phase4 的职责);不替换现有单次审稿(双轨并存)。

## 2. 角色编制(16 岗,config 可开关,默认全开)

| # | 部门 | 岗位 key | 关注/rubric 主轴 |
|---|---|---|---|
| 1 | 决策层 | `chief_editor`(总编/主席) | 主持辩论、综合、终裁(通过/改/毙)+ 定稿评分 |
| 2 | 决策层 | `managing_editor`(执行主编) | 流程统筹、平票打破、收敛判定辅助 |
| 3 | 内容 | `content_editor`(责任编辑) | 选题契合/结构/论证完整 |
| 4 | 内容 | `copy_editor`(文字编辑) | 文风/去AI味/句子打磨(ref §3) |
| 5 | 内容 | `proofreader`(校对) | 错字/语法/一致性/规范 |
| 6 | 内容 | `fact_checker`(事实核查) | 数据/事实/引用核验 |
| 7 | 合规 | `compliance`(合规审核) | 政策/敏感/平台规则 |
| 8 | 合规 | `legal_copyright`(法务版权) | 洗稿/侵权/授权(对接 similarity 硬门禁) |
| 9 | 读者增长 | `reader_advocate`(读者代表) | 点进来/读完/共鸣(目标读者视角) |
| 10 | 读者增长 | `headline_editor`(标题编辑) | 打开率/钩子(ref §1) |
| 11 | 读者增长 | `growth_editor`(传播增长) | 收藏/转发/在看/关注(ref §4/§5) |
| 12 | 读者增长 | `layout_editor`(排版视觉) | 移动端可读性(ref §2) |
| 13 | 读者增长 | `platform_seo`(平台算法/SEO) | 看一看/推荐流分发适配 |
| 14 | 策略品牌 | `topic_strategist`(选题策划) | 是否值得发/定位/差异 |
| 15 | 策略品牌 | `domain_expert`(领域专家) | 专业深度/judgment(AI+产业·微信生态·单人运营) |
| 16 | 策略品牌 | `brand_voice`(品牌调性/人设) | voice 一致性/IP |

冗余说明:⑤校对/④文字、⑦合规/⑧法务 视角有重叠 —— 设计上接受(多视角冗余优于漏检),用户可按需关闭。

每个岗位由一条数据驱动定义(见 §3),便于增删改岗而不动编排代码。

## 3. 角色定义与 rubric

岗位定义为**数据**(一个 `EDITORIAL_ROLES: list[RoleSpec]`,可后续外置为配置/DB):
```
RoleSpec = {
  key, name(中文), department,
  system_prompt,         # 该岗的角色设定与立场
  rubric,                # 该岗评审维度与扣分点(多条派生自 ref/04-report.md)
  enabled(默认 True),
  weight(默认 1.0),      # 终裁加权用(总编可参考)
}
```
rubric 内容直接复用 `ref/04-report.md` 的 A/B/C/D 结论(标题/钩子/去AI味/排版/传播/CTA)与 T6 合规红线。**不新发明评审标准**,把已验证调研拆成各岗 rubric。

## 4. 辩论协议(多轮至收敛)

```
INPUT: generation(待审稿) + source/brief/related(上下文) + 现有单次 ReviewReport(快筛结果)

ROUND 0 — 独立评审(并行,受全局并发≤3):
  每个 enabled 岗位独立审稿 → 产出 RoleOpinion:
    { role_key, scores{维度:0-100}, issues[], stance(pass|revise|reject), key_argument }

ROUND 1..N — 辩论(并行,受并发≤3):
  每个岗位看到【上一轮全体意见摘要】→ 产出本轮 RoleOpinion':
    反驳他人 / 让步 / 补充新证据 / 更新 stance
  执行主编每轮产出结构化 `new_substantive_objection: bool`,判定 convergence:
    收敛 = (new_substantive_objection == false) OR (round == MAX_ROUNDS)
  收敛由该布尔字段**唯一驱动**(不靠自然语言猜测),MAX_ROUNDS 兜底。

MAX_ROUNDS = 4(配置 EDITORIAL_MAX_DEBATE_ROUNDS,硬上限防不收敛)

TERMINAL — 总编终裁:
  chief_editor 综合全部轮次 → EditorialVerdict:
    { decision(pass|revise|reject), final_scores{}, rationale,
      revision_directives[](结构化:位置/问题/改法), dissent_summary }
```

收敛检测由 `managing_editor` 的结构化输出驱动(`new_substantive_objection: bool`),而非自然语言猜测。终止由 `MAX_ROUNDS` 兜底保证。

## 5. 集成(双轨,职责分离)

```
Phase4(EDITORIAL_ENABLED=true 时):
  写稿 → 现有单次审稿(快筛,产出快筛 ReviewReport,记录信号)
       → 【不再在此自动推草稿】将任务置 PENDING_EDITORIAL + 入队 editorial:queue
       (快筛若直接 reject 可早停不入队,作为省算力的可选优化)
board worker: 取稿 → 跑 §4 辩论 → EditorialVerdict
       → 落 editorial_review 表(含全程辩论转写)
       → 写一条【新的】权威 ReviewReport(editorial_review.review_report_id 关联),
         供所有下游门禁读取(下游读"最新 ReviewReport",零改动)
       → decision=pass 且过现有阈值门禁(similarity/policy/factual/score)→ 现有自动推草稿
       → decision=revise → revision_directives 喂现有 `_auto_revise_once`/humanize → 改完重新入队 editorial
       → decision=reject → NEEDS_REGENERATE;门禁不过/需人工 → NEEDS_MANUAL_REVIEW
```

- **双轨语义**:两套审稿**逻辑都跑**(快筛 + 编委会深审),但**推草稿决策权归编委会**。`EDITORIAL_ENABLED` 时 Phase4 不再自动推,把 push 决策延后到编委会终裁——否则会出现"快筛已推、编委会才审"的时序矛盾。`EDITORIAL_ENABLED=false` 时退回纯 Phase4 旧行为。
- 编委会**新建**一条权威 ReviewReport(不改写快筛那条;快筛 ReviewReport 作为信号留存),下游 `wechat_push_policy`/阈值/`/admin/phase5` 读最新 ReviewReport,零改动。
- 新增 `PENDING_EDITORIAL` 任务状态(TaskStatus 枚举 + ACTIVE 集合)。
- **每篇都过编委会**(用户要求)。修改指令复用 Phase4 现有 `_auto_revise_once`/humanize,不另造写稿链路;auto-revise 后重新入队编委会,受 MAX 次数(沿用 `phase4_max_auto_revisions`)约束防死循环。

## 6. 数据模型

新表 `editorial_review`(Alembic 迁移):
```
id, task_id(FK), generation_id(FK), status(running|converged|max_rounds|failed),
rounds_used, decision(pass|revise|reject), final_scores(JSON),
rationale(Text), revision_directives(JSON), dissent_summary(Text),
transcript(JSON: 每轮每岗 opinion 全量), created_at, updated_at
```
+ repository。终裁同时写一条 `ReviewReport`(沿用现有模型,保证下游门禁),`editorial_review.review_report_id` 关联。

## 7. 基建(并发≤3 全局保证)

- 新 Redis 队列:`EDITORIAL_QUEUE_KEY=editorial:queue` / `:processing` / `:pending` / `:dead`(沿用 T3a 队列+重试+DLQ 模式)。
- 新 worker:`scripts/run_editorial_worker.py`,**单实例**,内部 `Semaphore(EDITORIAL_LLM_MAX_CONCURRENCY=3)` 包住所有 GLM 调用。
- **并发≤3 由"单 board worker + 内部 Semaphore"保证全局**。多开 board worker 需 Redis 分布式限流 —— 本期不做,文档与启动脚本注明"editorial worker 只起 1 个实例"。
- 新服务:
  - `EditorialLLMClient` — 专用渠道(§8),OpenAI 兼容,内部并发闸 + 复用现有 `LLMService` 的 JSON 解析/schema 校验(T4 的 `LLMSchemaError` 可重试)。
  - `EditorialBoardService` — 辩论编排(round 循环、收敛判定、终裁、映射 ReviewReport)。
- Phase4 审稿后入队 editorial(`EditorialQueueService.enqueue`)。
- 错误处理复用 T3a:`handle_worker_failure` + 重试分类 + DLQ + 崩溃恢复 `requeue_processing_jobs`。

## 8. 配置与密钥(独立于现有 LLM 配置)

```
EDITORIAL_LLM_API_BASE=https://open.bigmodel.cn/api/coding/paas/v4
EDITORIAL_LLM_MODEL=glm-5.2
EDITORIAL_LLM_API_KEY=<.env only,绝不入代码/PR>
EDITORIAL_LLM_MAX_CONCURRENCY=3
EDITORIAL_MAX_DEBATE_ROUNDS=4
EDITORIAL_ENABLED=true          # 总开关
EDITORIAL_ROLE_DISABLED=        # 逗号分隔关闭某些岗位 key
```
`.env.example` 加占位(无真实值)。真实 key 只进 `.env`(gitignore)。**安全:用户已明文贴出 key,建议轮换。**

## 9. 可观测

- `/admin/phase5`(或新 `/admin/editorial`)增"编委会辩论"视图:某稿的终裁 + 各岗各轮意见转写 + 异议。复用已迁移的 Jinja2 模板基座。
- editorial 队列深度/worker 心跳并入现有 console 监控(沿用 `queue_observability`)。

## 10. 测试策略

- 单元:`EditorialBoardService` 用 mock LLM client 跑通 0 轮独立评审 + 1 轮辩论 + 收敛 + 终裁;收敛检测(无新反对即停)、MAX_ROUNDS 兜底、终裁映射 ReviewReport。
- 并发闸:`EditorialLLMClient` 的 Semaphore 不超过 3 并发(可用计数器断言)。
- 集成:Phase4 审稿后入队 editorial;board worker 消费产出 verdict;decision=revise 触发 auto-revise。
- 复用现有 sqlite 内存 + UUID shim 测试模式;LLM 全程 mock(不打真实渠道)。
- CI 沿用(pytest + ruff E9,F);不引入对真实 GLM 渠道的测试依赖。

## 11. 不做(out of scope · 本期)

- 多 board worker 横向扩展(需分布式并发限流)。
- 编委会角色的可视化拖拽配置(本期 config/数据驱动即可)。
- 替换/移除现有单次审稿(双轨保留)。
- 编委会直接重写终稿(只产裁决+指令,写稿走 Phase4)。
- 真实 GLM 渠道的端到端自动化测试(避免 CI 依赖外部+消耗)。

## 12. 关键风险

- **墙钟**:16 岗 × 多轮,并发≤3 → 单篇评审可能数分钟。异步队列可接受;可关岗或降 MAX_ROUNDS 提速。
- **不收敛**:MAX_ROUNDS 硬兜底 + 收敛检测结构化输出双保险。
- **渠道额度/限流**:GLM 渠道自身限流/额度未知 → `EditorialLLMClient` 复用 T4 可重试 + T3a DLQ,渠道 429/5xx 自动退避重试。
- **质量未验证**:编委会是否真提升真实传播指标,仍需 T5 质量回环用真实数据验证(与全项目同一未闭合缺口)。

## 13. 落地顺序(供 writing-plans 展开)

1. 配置 + `EditorialLLMClient`(专用渠道 + 并发闸)+ 单测。
2. 数据模型 `editorial_review` + 迁移 + repository。
3. 角色定义 `EDITORIAL_ROLES`(16 岗 rubric,派生自 ref/)。
4. `EditorialBoardService`(辩论编排 + 收敛 + 终裁 + ReviewReport 映射)+ 单测。
5. 队列 + `run_editorial_worker.py`(复用 T3a 重试/DLQ)+ Phase4 入队钩子。
6. 后台辩论视图 + 监控并入。
7. 端到端集成测试(全 mock LLM)。
