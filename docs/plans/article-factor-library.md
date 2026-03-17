# 文章因子库（Article Factor Library）

> **文档版本** 0.1 · 2026-03-17 · 状态：*RFC*

---

## 一、概述

### 1.1 问题定义

当前 Pipeline（Phase 2–4）生成文章时，写作风格和技巧主要硬编码在 Prompt 中，存在三个核心问题：

| 痛点 | 影响 |
|---|---|
| **不可积累** | 看到一篇好文章里某个精妙的修辞/排版技巧，只能靠记忆或笔记，无法系统化复用 |
| **不可检索** | 想在新文章中使用"反直觉开头"或"数据钩子"，没有地方快速找到并指定 |
| **不可度量** | 不知道哪些写作技巧确实提升了成稿质量（审稿评分），无法迭代优化 |

### 1.2 解决方案

构建一个 **因子库（Factor Library）** 系统：

1. **提取**：从优质文章中提取细粒度的、话题无关的写作技巧因子
2. **存储**：将因子标准化存入数据库，支持分类、标签、检索
3. **注入**：在创作时将因子注入到 Brief / Prompt 中，同时提供对应的示例片段作为 few-shot 参考
4. **反馈**：通过审稿评分和人工反馈，持续评估因子效果，形成闭环

### 1.3 核心设计原则

- **原子性**：每个因子描述一个独立的、可迁移的写作技法
- **话题无关性**：因子描述的是"怎么写"而非"写什么"
- **可组合性**：因子之间可以自由组合，但支持冲突检测
- **双轨注入**：Prompt 指令 + few-shot 示例片段并行注入

---

## 二、因子模型

### 2.1 因子的定义

一个**因子（Factor）**是对某种写作技法的结构化描述，包含：

| 字段 | 类型 | 说明 | 示例 |
|---|---|---|---|
| **name** | string | 因子名称（简短可读） | `反直觉数据钩子` |
| **dimension** | enum | 所属维度 | `opening` |
| **technique** | text | 技法描述（给 AI 读的指令） | `开篇用一个违背常识的数据或事实作为钩子，制造读者的认知冲突，激发继续阅读的欲望` |
| **effect** | text | 预期效果（给人读的说明） | `让读者在前 3 秒产生"这不对吧？"的疑问，从而主动往下看` |
| **example_text** | text | 示例片段（匿名化，供 few-shot） | `"中国人均咖啡消费量仅为芬兰的 1/40 —— 但这个数字正在以每年 15% 的速度追赶。"` |
| **anti_example** | text | 反面示例（可选） | `"今天我们来聊聊咖啡。"` |
| **tags** | list[str] | 自由标签 | `["数据驱动", "悬念", "开头"]` |
| **applicable_domains** | list[str] | 适用领域（空=通用） | `["科技", "财经"]` |
| **conflict_group** | string | 冲突组（同组因子互斥） | `opening_style` |
| **source_url** | string | 来源文章链接 | `https://mp.weixin.qq.com/s/...` |
| **source_factor** | enum | 提取方式 | `ai_extracted` 或 `manual` |

### 2.2 因子维度分类体系

基于联网搜索和微信公众号写作最佳实践，将因子分为 **6 个一级维度**，每个维度下设若干子分类：

```
因子维度
├── opening      开头技法
│   ├── 数据钩子（反直觉数据/统计）
│   ├── 场景代入（故事/画面感开头）
│   ├── 悬念设问（提问/矛盾开头）
│   ├── 名言引用（权威背书开头）
│   └── 对比冲突（今昔/正反对比）
│
├── structure    结构技法
│   ├── 递进式（层层深入）
│   ├── 并列式（多角度并行）
│   ├── 总分总（先结论后展开）
│   ├── 问答式（自问自答推进）
│   └── 时间线（按时间脉络展开）
│
├── rhetoric     修辞与表达
│   ├── 比喻/类比（陌生概念日常化）
│   ├── 排比（节奏感与气势）
│   ├── 反问（引导思考）
│   ├── 对比（突出差异）
│   ├── 留白（点到为止）
│   └── 口语化表达（降低阅读门槛）
│
├── rhythm       行文节奏
│   ├── 长短句交替（避免单调）
│   ├── 段落呼吸（3-5行一段）
│   ├── 信息密度调控（详略得当）
│   ├── 叙述-描写-引语切换
│   └── 节奏变化点（关键处放慢）
│
├── layout       排版技法（微信特化）
│   ├── 视觉分隔（分割线/留白/emoji）
│   ├── 重点标注（加粗/变色/大字号）
│   ├── 层级标题（h1-h3 清晰分层）
│   ├── 列表化表达（要点 bullet 化）
│   └── 图文节奏（图片的节奏性插入）
│
└── closing      结尾技法
    ├── 金句收束（提炼一句精华）
    ├── 首尾呼应（回扣开头元素）
    ├── 开放追问（留给读者思考空间）
    ├── 行动号召（CTA / 引导互动）
    └── 情感回味（真挚感受收尾）
```

### 2.3 冲突组规则

同一 `conflict_group` 内的因子在同一篇文章中互斥。例如：

| 冲突组 | 互斥因子 | 原因 |
|---|---|---|
| `opening_style` | 数据钩子 / 场景代入 / 悬念设问 | 开头只能用一种主模式 |
| `tone_register` | 口语化表达 / 学术化措辞 | 语言寄存器不可混用 |
| `density_level` | 高信息密度 / 留白式表达 | 风格矛盾 |

> **关键约束**：不同维度之间的因子默认可组合（如 `opening.数据钩子` + `rhythm.长短句交替` + `closing.开放追问`）。冲突仅存在于同一维度内的特定子类之间。

---

## 三、系统架构

### 3.1 整体数据流

```
                            ┌─────────────────┐
     手动输入链接            │                 │
    ──────────────────────▶  │   FactorExtractor│
     自动每日抓取            │   (提取引擎)     │
    ──────────────────────▶  │                 │
                            └────────┬────────┘
                                     │ 提取出的因子
                                     ▼
                            ┌─────────────────┐
                            │                 │
                            │  Factor Library  │
                            │  (因子库)        │
                            │                 │
                            └──┬──────────┬───┘
                    人工选定 │            │ 自动推荐
                               ▼            ▼
                            ┌─────────────────┐
                            │ FactorSelector   │
                            │ (因子选择器)     │
                            └────────┬────────┘
                                     │ 已选因子列表
                                     ▼
                  ┌──────────────────────────────────────┐
                  │         因子注入层（双轨）             │
                  │                                      │
                  │  路线 A: Prompt 指令注入              │
                  │  ┌──────────────────────────────┐    │
                  │  │ 在 Brief 的 writing_factors    │    │
                  │  │ 字段中写入因子的 technique 描述 │    │
                  │  └──────────────────────────────┘    │
                  │                                      │
                  │  路线 B: Few-shot 示例注入            │
                  │  ┌──────────────────────────────┐    │
                  │  │ 在 Prompt 的 reference_snippets│    │
                  │  │ 中插入因子的 example_text 片段  │    │
                  │  └──────────────────────────────┘    │
                  └──────────────┬───────────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  Phase4 写稿     │
                        │  GenerateArticle │
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  Phase4 审稿     │
                        │  ReviewArticle   │
                        └────────┬────────┘
                                 │ 审稿评分
                                 ▼
                        ┌─────────────────┐
                        │  因子效果回写    │
                        │  FactorFeedback  │
                        └─────────────────┘
```

### 3.2 与现有 Pipeline 的集成点

| 现有环节 | 因子库集成方式 | 影响范围 |
|---|---|---|
| **Phase 2 抓源文** | 可作为因子提取的输入来源 | `FetchSourceStep` 之后触发 `FactorExtractor` |
| **Phase 3 Build Brief** | `ContentBrief` 新增 `writing_factors` 字段 | `BuildBriefStep` 中注入因子的 technique 指令 |
| **Phase 4 写稿** | Prompt 中追加 `reference_snippets` 段 | `_generate_generation()` 的 prompt 构建逻辑 |
| **Phase 4 审稿** | 审稿结果回写因子效果评分 | `_review_generation()` 完成后触发 `FactorFeedback` |
| **Phase 5 工作台** | 看板展示因子使用情况 | 工作台 UI 新增因子选择面板 |

---

## 四、因子提取引擎

### 4.1 提取 Prompt 设计

因子提取的核心是一个结构化的 LLM 分析任务。输入一篇文章的 Markdown 文本，输出结构化的因子列表。

**Prompt 模板**（精简版，实际使用时需要更详细的分类说明和示例）：

```
你是一个资深的内容分析师。请分析以下文章，提取其中的写作技巧因子。

## 规则
1. 每个因子必须是**通用的、话题无关的**写作技法，而不是特定于文章话题的观点
2. 每个因子必须足够**原子化**——描述一个独立的、可迁移到其他文章的技法
3. 每个因子必须包含一段**脱敏示例片段**（去掉专有名词，保留技法本身）
4. 排除以下内容：文章的具体观点、特定事实、话题相关的论据
5. 重点关注六个维度：开头、结构、修辞、节奏、排版、结尾

## 输出格式（JSON 数组）
[
  {
    "name": "因子名称（4-12字）",
    "dimension": "opening|structure|rhetoric|rhythm|layout|closing",
    "technique": "技法描述（给 AI 写稿时用的指令，50-150 字）",
    "effect": "预期效果描述（给人读的说明，30-80 字）",
    "example_text": "从原文中提取的示例片段（脱敏后，50-200 字）",
    "tags": ["标签1", "标签2"]
  }
]

## 文章内容
{article_markdown}
```

### 4.2 提取去重与合并

同一因子可能从多篇文章中被反复提取。需要一个**去重与合并**流程：

1. **语义相似度检测**：新提取的因子与库中既有因子计算 embedding 相似度
2. **阈值判定**：相似度 > 0.85 视为同一因子，仅追加新的 example_text
3. **人工确认**：相似度 0.65-0.85 的因子进入人工确认队列
4. **累积权重**：每被独立提取一次，因子的 `extract_count` +1，代表其"通用程度"

### 4.3 来源管道

| 来源 | 触发方式 | 说明 |
|---|---|---|
| **Phase 2 源文** | Pipeline 自动 | 每次成功抓取的源文可选择性触发因子提取 |
| **手动输入链接** | 工作台手动 | 运营人员看到好文章，输入链接提交提取 |
| **定时批量抓取** | 每日定时任务 | 配置一批 RSS / 白名单账号，每日自动抓取并提取 |
| **人工直接创建** | 工作台手动 | 不从文章提取，运营人员凭经验直接手写因子 |

---

## 五、因子注入机制（双轨制）

### 5.1 路线 A：Prompt 指令注入

在 `ContentBrief` 中新增 `writing_factors` JSON 字段，格式为因子 technique 列表：

```json
{
  "writing_factors": [
    {
      "factor_id": "f-001",
      "name": "反直觉数据钩子",
      "dimension": "opening",
      "technique": "开篇用一个违背常识的数据或事实作为钩子..."
    },
    {
      "factor_id": "f-042",
      "name": "长短句交替",
      "dimension": "rhythm",
      "technique": "在叙述性段落中交替使用短句（≤10字）和长句（20-40字）..."
    }
  ]
}
```

在 Phase4 写稿 Prompt 中渲染为：

```
## 写作因子要求
本文必须运用以下写作技法，并确保在成稿中可以清楚辨识到每个技法的运用：

【开头】反直觉数据钩子
开篇用一个违背常识的数据或事实作为钩子，制造读者的认知冲突。

【节奏】长短句交替
在叙述性段落中交替使用短句（≤10字）和长句（20-40字），避免节奏单调。
```

### 5.2 路线 B：Few-shot 示例注入

在 Prompt 中附加因子的 `example_text` 作为参考片段：

```
## 写法参考片段
以下片段展示了本文需要运用的写作技法。请不要复制内容，而是学习其中的技法并应用到新文章中。

--- 片段 1: 反直觉数据钩子 ---
"中国人均咖啡消费量仅为芬兰的 1/40 —— 但这个数字正在以每年 15% 的速度追赶。
比起数据本身，更值得玩味的是：这波增长完全不是星巴克推动的。"

--- 片段 2: 长短句交替 ---
"她停了下来。
这不是犹豫，而是一种经过计算的沉默——她知道，接下来说出的每一个字都会被录音笔忠实地记录。
三秒。
'我拒绝回答这个问题。'"
```

### 5.3 双轨合并策略

两条路线**同时生效**，在 Prompt 中按以下顺序组织：

```
[系统角色设定]
[Brief 核心信息：定位/角度/目标读者/大纲]
[路线 A: 写作因子要求]          <-- 因子的 technique 作为明确指令
[路线 B: 写法参考片段]          <-- 因子的 example_text 作为 few-shot
[原文摘要/素材]
[输出格式要求]
```

**双轨合并的优势**：
- 路线 A 给出**明确约束**（"必须用什么手法"），防止 AI 遗忘
- 路线 B 给出**具体示范**（"这个手法长什么样"），降低 AI 的理解偏差
- 两者结合使因子落地率显著高于单独使用任一路线

### 5.4 Token 预算控制

因子注入会增加 Prompt 长度。需要控制：

| 约束 | 默认值 | 说明 |
|---|---|---|
| 单次最多注入因子数 | 5 个 | 过多因子会分散 AI 注意力 |
| example_text 最大长度 | 200 字/因子 | 控制 few-shot 片段长度 |
| 因子指令总 token 上限 | 1500 tokens | 不超过 Prompt 总量的 15% |

---

## 六、因子选择与推荐

### 6.1 人工选择

在 Phase 5 工作台中新增**因子选择面板**：

- 按维度分组展示因子库
- 搜索和筛选（按名称/标签/维度/适用领域）
- 拖拽或勾选因子到当前任务
- 冲突检测：选中互斥因子时弹出警告
- 选择结果写入 `ContentBrief.writing_factors`

### 6.2 自动推荐

当未人工指定因子时，系统自动推荐因子组合：

**推荐策略**：

```python
def recommend_factors(brief, analysis, factor_pool):
    """根据 Brief 和源文分析自动推荐因子组合"""
    recommended = []

    # 1. 必选维度：opening + closing 各选一个
    recommended.append(pick_best("opening", factor_pool, analysis))
    recommended.append(pick_best("closing", factor_pool, analysis))

    # 2. 可选维度：rhetoric + rhythm 中按效果评分选 top-1
    recommended.append(pick_best("rhetoric", factor_pool, analysis))
    recommended.append(pick_best("rhythm", factor_pool, analysis))

    # 3. 冲突检查
    recommended = resolve_conflicts(recommended)

    # 4. Token 预算裁剪
    recommended = trim_to_budget(recommended, max_tokens=1500)

    return recommended
```

**pick_best 的排序依据**：
1. `avg_effect_score`（历史使用的平均审稿评分提升）
2. `extract_count`（被独立提取次数 = 通用程度）
3. `applicable_domains` 与当前文章主题的匹配度

---

## 七、效果反馈闭环

### 7.1 因子效果记录

每次任务使用了因子并完成审稿后，将审稿评分回写到因子的使用记录中：

```
TaskFactorUsage:
  - task_id
  - factor_id
  - injected_via: "prompt" | "brief" | "both"
  - review_score_overall: 85.2
  - review_score_readability: 90
  - review_score_novelty: 78
  - human_feedback: "good" | "neutral" | "bad"（人工复评）
```

### 7.2 因子效果评估

定期（每周 / 每 N 次使用后）计算因子的效果指标：

| 指标 | 计算方式 | 用途 |
|---|---|---|
| **平均审稿分提升** | 使用了该因子的文章平均分 - 未使用的平均分 | 量化因子价值 |
| **使用频率** | 该因子被选用的总次数 | 衡量受欢迎程度 |
| **人工好评率** | good / (good + neutral + bad) | 反映实际体感 |
| **综合效果分** | 加权综合以上三项 | 排序推荐用 |

### 7.3 因子生命周期

```
draft (草稿)
  ↓ 人工审核通过
active (有效)
  ↓ 效果评估持续低于阈值 或 人工标记
deprecated (废弃)
  ↓ 彻底清理
archived (归档)
```

---

## 八、数据模型设计

### 8.1 新增表

```sql
-- 因子表
CREATE TABLE factors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    dimension VARCHAR(50) NOT NULL,          -- opening/structure/rhetoric/rhythm/layout/closing
    technique TEXT NOT NULL,                  -- 给 AI 的指令描述
    effect TEXT,                              -- 给人读的效果说明
    example_text TEXT,                        -- 示例片段（few-shot 用）
    anti_example TEXT,                        -- 反面示例（可选）
    tags JSONB DEFAULT '[]',                  -- 自由标签
    applicable_domains JSONB DEFAULT '[]',    -- 适用领域（空=通用）
    conflict_group VARCHAR(100),             -- 冲突组标识
    source_url TEXT,                          -- 来源文章链接
    source_factor VARCHAR(20) DEFAULT 'manual', -- ai_extracted / manual
    extract_count INT DEFAULT 1,             -- 被独立提取次数
    status VARCHAR(20) DEFAULT 'draft',      -- draft/active/deprecated/archived
    avg_effect_score FLOAT,                  -- 综合效果分（定期刷新）
    usage_count INT DEFAULT 0,               -- 使用次数
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- 因子使用记录表
CREATE TABLE task_factor_usages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    factor_id UUID NOT NULL REFERENCES factors(id) ON DELETE CASCADE,
    injected_via VARCHAR(20) DEFAULT 'both', -- prompt / brief / both
    review_score_overall FLOAT,
    review_score_readability FLOAT,
    review_score_novelty FLOAT,
    human_feedback VARCHAR(20),              -- good / neutral / bad
    created_at TIMESTAMP DEFAULT now()
);

-- 因子提取任务表（追踪从哪些文章提取了因子）
CREATE TABLE factor_extraction_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_url TEXT NOT NULL,
    source_title TEXT,
    extracted_count INT DEFAULT 0,
    merged_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',    -- pending/running/completed/failed
    error TEXT,
    created_at TIMESTAMP DEFAULT now()
);

-- 因子-提取来源 关联表
CREATE TABLE factor_source_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    factor_id UUID NOT NULL REFERENCES factors(id) ON DELETE CASCADE,
    extraction_run_id UUID NOT NULL REFERENCES factor_extraction_runs(id) ON DELETE CASCADE,
    example_text_from_source TEXT,            -- 该来源提取的示例片段
    created_at TIMESTAMP DEFAULT now()
);
```

### 8.2 现有表修改

```sql
-- ContentBrief 新增字段
ALTER TABLE content_briefs
    ADD COLUMN writing_factors JSONB DEFAULT NULL;
    -- 存储 [{factor_id, name, dimension, technique}] 结构
```

---

## 九、API 设计

### 9.1 因子 CRUD

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/factors` | 列表（支持 dimension/tags/status/query 筛选） |
| `GET` | `/api/v1/factors/{id}` | 详情 |
| `POST` | `/api/v1/factors` | 手动创建因子 |
| `PUT` | `/api/v1/factors/{id}` | 更新因子 |
| `PATCH` | `/api/v1/factors/{id}/status` | 状态变更（draft→active→deprecated） |

### 9.2 因子提取

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/factors/extract` | 提交文章链接，触发因子提取 |
| `GET` | `/api/v1/factors/extractions` | 查看提取任务列表 |
| `POST` | `/api/v1/factors/extractions/{id}/confirm` | 人工确认 / 合并提取结果 |

### 9.3 因子选择与推荐

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/tasks/{id}/recommended-factors` | 获取自动推荐因子 |
| `POST` | `/api/v1/tasks/{id}/factors` | 为任务选定因子 |
| `GET` | `/api/v1/tasks/{id}/factors` | 查看任务已选因子 |

### 9.4 因子效果

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/factors/{id}/stats` | 因子效果统计 |
| `POST` | `/api/v1/factors/usages/{id}/feedback` | 人工效果反馈 |
| `GET` | `/api/v1/factors/leaderboard` | 因子效果排行榜 |

---

## 十、实施计划

### Phase A：最小闭环（人工驱动）

**目标**：验证因子粒度定义和注入效果

| 步骤 | 具体工作 | 优先级 |
|---|---|---|
| A1 | 数据模型：建 `factors` 和 `task_factor_usages` 表 | P0 |
| A2 | API：Factor CRUD + 任务因子选择接口 | P0 |
| A3 | Brief：`ContentBrief` 新增 `writing_factors` 字段 | P0 |
| A4 | 注入：Phase4 写稿 Prompt 中渲染因子指令 + 示例片段 | P0 |
| A5 | 种子数据：人工创建 20-30 个高质量因子 | P0 |
| A6 | 工作台：Phase5 因子选择面板 | P1 |

**验收标准**：手动选择 3 个因子 → 生成文章 → 审稿评分 ≥ 80 → 人工确认因子技法可辨识

### Phase B：自动提取

**目标**：实现自动因子提取和去重

| 步骤 | 具体工作 | 优先级 |
|---|---|---|
| B1 | 因子提取 Prompt 开发与调优 | P0 |
| B2 | 提取去重：embedding 相似度 + 合并逻辑 | P0 |
| B3 | API：提取任务 + 人工确认流程 | P1 |
| B4 | 集成 Phase2：源文抓取后可选触发因子提取 | P1 |

### Phase C：自动推荐 + 反馈闭环

**目标**：实现因子的自动推荐和效果度量

| 步骤 | 具体工作 | 优先级 |
|---|---|---|
| C1 | 自动推荐算法实现 | P1 |
| C2 | 审稿评分回写 `task_factor_usages` | P1 |
| C3 | 效果统计和因子排行榜 | P2 |
| C4 | 因子生命周期管理（自动降级低效因子） | P2 |

### Phase D：定时抓取 + 大规模运营

**目标**：构建持续增长的因子资产

| 步骤 | 具体工作 | 优先级 |
|---|---|---|
| D1 | 定时抓取白名单账号文章 | P2 |
| D2 | 批量因子提取和审核流程 | P2 |
| D3 | 因子市场化（导出/导入/共享） | P3 |

---

## 十一、风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| **因子粒度定义不当** | 太粗→无法组合；太细→无意义 | Phase A 手动创建 20 个种子因子，验证粒度后再做自动提取 |
| **因子注入导致 AI 忽略 Brief** | 因子指令与 Brief 冲突，AI 不知道优先哪个 | Prompt 中明确优先级：Brief > 因子 |
| **Token 预算溢出** | 过多因子 + 示例片段超出上下文窗口 | 硬限制最多 5 因子 + 1500 token 上限 |
| **效果度量假阳性** | A/B 测试不充分，误以为某因子有效 | 需积累足够样本（≥20 次使用）后才计入排行 |
| **提取出话题相关的因子** | "用供应链数据论证宏观经济"不是通用因子 | 提取 Prompt 中强调话题无关性 + 人工审核 |

---

## 附录 A：因子示例库（种子因子）

以下 10 个因子可作为 Phase A 的种子数据：

### A1. 反直觉数据钩子
- **维度**：opening
- **技法**：开篇引述一个违背读者直觉的数据或统计事实，然后用一句话点明"反常之处"，制造认知冲突。
- **效果**：让读者在前 3 秒产生"这不对吧？"的疑问，主动往下阅读。
- **示例**：`"某国人均咖啡消费量仅为某北欧国家的 1/40 —— 但这个数字正在以每年 15% 的速度追赶。"`

### A2. 场景闪回式开头
- **维度**：opening
- **技法**：开篇直接描写一个具体场景的画面，用感官细节（视觉/听觉/触觉）让读者"身临其境"，然后在第二段点明主题。
- **效果**：让读者先进入情境再理解主题，降低理解门槛，增强带入感。
- **示例**：`"凌晨 3 点的实验室依旧亮着灯。屏幕上的曲线刚刚经历了第 47 次坍塌，他摘下眼镜揉了揉眼角——这次不一样。"`

### A3. 金句前置结构
- **维度**：structure
- **技法**：每个核心段落以一句加粗金句（≤20 字）开头，后文展开解释，让读者扫读时也能抓到要点。
- **效果**：降低长文的阅读疲劳，让跳读也能获取核心信息。

### A4. 递进三段论
- **维度**：structure
- **技法**：围绕一个论点分三层递进：表象 → 本质 → 启示。每层之间用"但更值得关注的是""深一层看"等过渡词连接。
- **效果**：让论证有层次感，避免平铺直叙。

### A5. 日常类比降维
- **维度**：rhetoric
- **技法**：将专业概念用日常生活场景类比，例如"数据库索引就像图书馆的目录卡"。类比对象必须是读者 100% 熟悉的。
- **效果**：让非专业读者也能秒懂复杂概念。

### A6. 短句爆破节奏
- **维度**：rhythm
- **技法**：在情绪转折处连续使用 3-5 个短句（每句 ≤8 字），制造节奏的突然变化。
- **效果**：在长段落的"匀速阅读"中制造"刹车感"，迫使读者注意力集中。
- **示例**：`"她停下了。不是犹豫。是决定。"`

### A7. 呼吸式分段
- **维度**：layout
- **技法**：正文每 3-5 行后留一个空行，关键段落前后增加双倍空行。段落之间不使用任何装饰性分割线。
- **效果**：在手机屏幕上阅读时给眼睛"喘息"空间，降低视觉疲劳。

### A8. 重点三层标注
- **维度**：layout
- **技法**：全文使用三级重点标注——加粗（核心观点）、斜体（次要强调）、引用块（名言/数据来源）。每种标注在全文中出现次数不超过 5 次。
- **效果**：让读者的视线自然被引导到关键信息，而不是满篇加粗导致"什么都不重要"。

### A9. 开放式追问收尾
- **维度**：closing
- **技法**：结尾不给结论，而是抛出一个读者可以代入自身的开放问题，邀请读者在评论区回答。
- **效果**：制造"未完成感"，读者倾向于留言回应（提升互动率）。

### A10. 首尾数据呼应
- **维度**：closing
- **技法**：结尾回扣开头提到的同一个数据/事实，但给出新的解读角度或更新的数据，形成认知闭环。
- **效果**：让文章产生"圆满"的结构感，同时强化记忆点。

---

## 附录 B：参考资料

- **AI 风格迁移**：AI writing style transfer 通过 factor decomposition 将风格与内容解耦，提取出 vocabulary、syntax、tone、rhetoric 等原子维度
- **Content DNA**：Content DNA 的概念来自品牌传播领域，指一个品牌/内容创作者的核心身份元素（价值观、语气、人格）的指纹化表达
- **Few-shot Prompt 工程**：最佳实践建议 2-5 个示例，多样化覆盖，一致格式，结合 Chain-of-Thought 推理
- **原子化写作**：将复杂内容拆解为结构化、标准化的最小单元，提高检索效果和知识库数据质量
- **微信公众号排版**：行间距 1.5-1.75 倍，正文 16px，3-5 行一段，重点不超过 5 处加粗
