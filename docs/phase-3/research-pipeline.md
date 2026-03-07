# 阶段 3 研究层与 Brief 管道

更新时间：2026-03-07
状态：In Progress

## 1. 目标

阶段 3 的目标，是把阶段 2 的“原文抓取与草稿箱验证”扩展为：

`原文 -> 原文分析 -> 同题搜索 -> 相关素材筛选 -> 差异矩阵 -> content_brief`

当前版本先落最小可跑通闭环，不进入正文生成和自动审稿。

## 2. 当前已实现范围

- 基于原文标题、摘要、正文节选生成结构化 `article_analysis`
- 生成三组查询词：
  - 标准主题
  - 热点主题
  - 反向主题
- 调用智谱官方 `web_search` 接口检索同题结果
- 对搜索结果做去重、打分和排序
- 抓取前 `top_k` 相关素材正文并落库到 `related_articles`
- 生成 `difference_matrix` 和 `content_brief`
- 提供同步执行和异步入队两组内部接口
- 提供 `phase3_worker` 轻量 worker 脚本
- 提供 `GET /api/v1/tasks/{task_id}/brief` 查询最新分析、Brief 和相关素材

## 3. 本轮新增接口

### 3.1 同步执行

```http
POST /internal/v1/tasks/{task_id}/run-phase3
Authorization: Bearer <token>
```

返回字段：

- `task_id`
- `status`
- `analysis_id`
- `brief_id`
- `related_count`

### 3.2 异步入队

```http
POST /internal/v1/tasks/{task_id}/enqueue-phase3
Authorization: Bearer <token>
```

### 3.3 合并入口

```http
POST /internal/v1/phase3/ingest-and-run
POST /internal/v1/phase3/ingest-and-enqueue
Authorization: Bearer <token>
Content-Type: application/json
```

### 3.4 Brief 查询

```http
GET /api/v1/tasks/{task_id}/brief
Authorization: Bearer <token>
```

返回内容：

- 最新 `article_analysis`
- 最新 `content_brief`
- 当前入选的 `related_articles`

## 4. 任务状态流

阶段 3 当前使用以下状态：

- `analyzing_source`
- `searching_related`
- `fetching_related`
- `building_brief`
- `brief_ready`

失败状态：

- `analyze_failed`
- `search_failed`
- `brief_failed`

## 5. 数据落库说明

### 5.1 `article_analysis`

保存字段：

- `theme`
- `audience`
- `angle`
- `tone`
- `key_points`
- `facts`
- `hooks`
- `risks`
- `gaps`
- `structure`

当前 JSON 字段统一使用：

```json
{"items": [...]}
```

### 5.2 `related_articles`

当前保存：

- 查询词 `query_text`
- 排名 `rank_no`
- 文章 URL、标题、来源站点
- 搜索摘要 `summary`
- 发布时间 `published_at`
- 排序分数：
  - `popularity_score` 当前用于保存综合排序分
  - `relevance_score`
  - `diversity_score`
  - `factual_density_score`
- 抓取结果：
  - `raw_html`
  - `cleaned_text`
  - `snapshot_path`
  - `fetch_status`
- 是否入选 `selected`

### 5.3 `content_briefs`

当前保存：

- `positioning`
- `new_angle`
- `target_reader`
- `must_cover`
- `must_avoid`
- `difference_matrix`
- `outline`
- `title_directions`

## 6. 搜索与排序策略

当前后端默认使用智谱官方 `web_search` API。

兼容策略：

- 如果 `SEARCH_API_BASE` 直接指向 `/web_search`，则直接使用
- 如果仍配置为旧的 MCP 地址（如 `/mcp/web_search_prime/mcp`），后端会自动回退到官方 `https://open.bigmodel.cn/api/paas/v4/web_search`

当前排序分：

```text
总分 = 相关性 35% + 时效性 20% + 来源质量 20% + 角度差异 15% + 可验证事实密度 10%
```

## 7. 技术约束

- Phase 3 当前仍是“研究层”，不会自动进入生成和推草稿
- LLM 失败时，会退化到启发式分析与 Brief 生成，避免整条链路直接中断
- 搜索失败仍会把任务打到 `search_failed`
- 当前后台页还没有单独做 Phase 3 控台，先以 API 和 worker 为主

## 8. 下一步

建议按这个顺序继续：

1. 在服务器部署 `phase3_worker` 并跑一轮真实 smoke test
2. 为 `article_analysis` 与 `content_brief` 增加后台查看页
3. 为搜索与抓取增加失败重试和监控指标
4. 进入阶段 4：基于 `content_brief` 生成正文与审稿
