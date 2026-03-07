# 阶段 1 数据库初版说明

更新时间：2026-03-07
状态：In Progress

## 1. 目标

阶段 1 只落地 MVP 主链路需要的核心表，不把阶段 6 的反馈表提前塞进首个 migration。

## 2. 初版核心表

- `tasks`
- `source_articles`
- `related_articles`
- `article_analysis`
- `content_briefs`
- `generations`
- `review_reports`
- `wechat_drafts`
- `prompt_versions`
- `audit_logs`

## 3. 设计说明

- `tasks` 是状态机主表
- `audit_logs` 记录重要系统动作
- `prompt_versions` 从阶段 1 就建好，避免后续 Prompt 无版本化
- `source_articles` 与 `related_articles` 为阶段 2 和阶段 3 预留
- `generations`、`review_reports`、`wechat_drafts` 为阶段 4 和阶段 2 后半段预留

## 4. 后续扩展表

以下表延后到后续阶段再加入：

- `style_assets`
- `publication_metrics`
- `prompt_experiments`

原因：

- 它们不阻塞阶段 1 和阶段 2 的基础链路
- 延后建表可以减少首批 migration 的复杂度
