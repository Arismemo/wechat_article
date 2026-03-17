# ADR-0002: 在 Phase 3 前引入长期选题情报层

## Status
Proposed

## Context

当前系统已经能稳定完成：

`URL ingest -> source fetch -> analysis -> related search -> content_brief -> generation -> review -> wechat draft`

但系统的选题入口仍然偏被动：

- 依赖人工提交一篇 URL
- 或者依赖人工先给出一个题目

这不适合“持续运营公众号内容资产”的商业目标，因为真正缺的是：

- 稳定发现值得写的主题
- 用统一标准筛选热点与长期价值
- 将发布反馈反向作用于下一轮选题

同时，现有系统已经在 `task`、Phase 3、Phase 4、监控、反馈和后台页上形成了一条稳定主链路。
如果直接再做一条新的“选题到成稿”并行流水线，会显著增加维护成本和回归风险。

## Decision

采用“长期选题情报层”作为现有主链路的前置能力层，而不是重做一套独立写稿流水线。

具体决策如下：

1. 在 Phase 3 前新增 `topic intelligence layer`，负责持续抓取公开信号、聚类候选选题、生成选题打法包。
2. 第一阶段不推翻当前 `task` 以 `source_url` 为起点的模型，而是使用 `canonical_seed_url` 桥接到现有任务流。
3. 第一阶段先落最小表结构、两类 worker、候选池 API 和后台只读候选池。
4. 第二阶段再让 Phase 3 显式消费 `topic_plan` 上下文。
5. 第三阶段再把 `publication_metrics` 和实验结果回写为选题排序因子。
6. 多 source pack 的“无唯一原文”任务模型推迟到后续阶段，不在第一阶段实施。

## Consequences

### Positive

- 最大化复用现有 Phase 3 / Phase 4、监控、反馈和后台能力
- 第一阶段改动面更小，风险可控
- 可以先跑出“持续发现选题 -> 人工推进 -> 正常产稿”的最小闭环
- 评分逻辑可解释，便于后续根据运营结果调权重

### Negative

- 第一阶段仍然受当前 `task.source_url` 设计约束
- 某些更适合“多源综合研究”的选题，需要先选一个 `canonical_seed_url`
- 选题层和任务层之间会暂时存在桥接逻辑

### Neutral

- 后续仍可能把任务模型演进为 `topic_plan + source_pack` 驱动
- 第一阶段不会自动提高内容质量上限，但会显著提高选题来源稳定性

## Alternatives Considered

### 方案 A：继续保持人工给题

- 优点：零开发成本
- 缺点：无法形成持续发现、沉淀和反馈闭环
- 结论：不满足长期目标

### 方案 B：独立做一套从选题到写稿的新流水线

- 优点：概念上整洁
- 缺点：与现有 task、Phase 3、Phase 4、监控、反馈形成双系统
- 结论：当前阶段过重，维护成本过高

### 方案 C：立即把现有 task 改成无 source_url 的多源任务模型

- 优点：从模型上更理想
- 缺点：会同时影响 ingest、Phase 2/3/4、后台、测试和线上兼容
- 结论：应作为后续演进方向，不适合第一阶段

## References

- [/Users/liukun/j/code/wechat_artical/docs/plans/2026-03-16-topic-intelligence-blueprint.md](/Users/liukun/j/code/wechat_artical/docs/plans/2026-03-16-topic-intelligence-blueprint.md)
- [/Users/liukun/j/code/wechat_artical/docs/wechat-content-factory-plan.md](/Users/liukun/j/code/wechat_artical/docs/wechat-content-factory-plan.md)
- [/Users/liukun/j/code/wechat_artical/docs/phase-3/research-pipeline.md](/Users/liukun/j/code/wechat_artical/docs/phase-3/research-pipeline.md)
- [/Users/liukun/j/code/wechat_artical/docs/phase-4/generation-and-review.md](/Users/liukun/j/code/wechat_artical/docs/phase-4/generation-and-review.md)
