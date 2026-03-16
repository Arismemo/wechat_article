"""Pipeline Registry — 数据驱动的流程定义。

声明所有 pipeline、phase、step 定义和步骤的可配置参数 schema，
前端页面和 API 均从此处读取数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StepDefinition:
    """单个步骤的定义。"""

    id: str
    label: str
    icon: str
    phase: str  # 所属 phase ID
    configurable: bool = False
    settings: list[str] = field(default_factory=list)  # SystemSettingService 键名
    children: list[StepDefinition] | None = None  # 复合节点的子流程


@dataclass(frozen=True)
class PhaseDefinition:
    """Pipeline 阶段的定义。"""

    id: str
    label: str
    steps: list[str]  # step ID 列表


@dataclass(frozen=True)
class PipelineDefinition:
    """完整 pipeline 的定义。"""

    id: str
    label: str
    description: str
    phases: list[PhaseDefinition]


# ---- 步骤定义 ----

STEP_DEFINITIONS: dict[str, StepDefinition] = {}


def _register(*steps: StepDefinition) -> None:
    for s in steps:
        STEP_DEFINITIONS[s.id] = s


_register(
    StepDefinition(
        id="fetch_source",
        label="抓取原文",
        icon="📥",
        phase="fetch",
    ),
    StepDefinition(
        id="analyze_source",
        label="深度分析",
        icon="🔍",
        phase="prepare",
    ),
    StepDefinition(
        id="search_related",
        label="搜索素材",
        icon="🌐",
        phase="prepare",
    ),
    StepDefinition(
        id="fetch_related",
        label="抓取素材",
        icon="📎",
        phase="prepare",
    ),
    StepDefinition(
        id="build_brief",
        label="生成 Brief",
        icon="📋",
        phase="prepare",
    ),
    StepDefinition(
        id="generate_article",
        label="AI 写稿",
        icon="✍️",
        phase="produce",
        configurable=True,
        settings=["phase4.write_model"],
    ),
    StepDefinition(
        id="review_article",
        label="AI 审核",
        icon="🔎",
        phase="produce",
        configurable=True,
        settings=[
            "phase4.review_pass_score",
            "phase4.similarity_max",
            "phase4.policy_risk_max",
            "phase4.factual_risk_max",
            "phase4.ai_trace_rewrite_threshold",
            "phase4.max_auto_revisions",
        ],
    ),
    StepDefinition(
        id="humanize_article",
        label="人类化改写",
        icon="🧬",
        phase="produce",
        children=[
            StepDefinition(id="humanize.detect", label="AI 痕迹检测", icon="🔬", phase="produce"),
            StepDefinition(id="humanize.rewrite", label="段落改写", icon="✂️", phase="produce"),
            StepDefinition(id="humanize.review", label="二次审核", icon="📝", phase="produce"),
        ],
    ),
    StepDefinition(
        id="push_draft",
        label="推送草稿",
        icon="📤",
        phase="produce",
        configurable=True,
        settings=["phase4.auto_push_wechat_draft"],
    ),
)


# ---- Pipeline 定义 ----

ARTICLE_PIPELINE = PipelineDefinition(
    id="article_pipeline",
    label="文章处理 Pipeline",
    description="从微信链接到推送草稿的完整流程",
    phases=[
        PhaseDefinition(
            id="fetch",
            label="Phase 2 · 抓取",
            steps=["fetch_source"],
        ),
        PhaseDefinition(
            id="prepare",
            label="Phase 3 · 准备",
            steps=["analyze_source", "search_related", "fetch_related", "build_brief"],
        ),
        PhaseDefinition(
            id="produce",
            label="Phase 4 · 生产",
            steps=["generate_article", "review_article", "humanize_article", "push_draft"],
        ),
    ],
)


# ---- API 序列化 ----

def serialize_step(step: StepDefinition) -> dict[str, Any]:
    """将 StepDefinition 序列化为 JSON 友好的 dict。"""
    result: dict[str, Any] = {
        "id": step.id,
        "label": step.label,
        "icon": step.icon,
        "phase": step.phase,
        "configurable": step.configurable,
        "settings": step.settings,
    }
    if step.children:
        result["children"] = [serialize_step(c) for c in step.children]
    return result


def serialize_pipeline(pipeline: PipelineDefinition) -> dict[str, Any]:
    """将 PipelineDefinition 序列化为完整的 JSON 响应。"""
    all_steps = []
    for phase in pipeline.phases:
        for step_id in phase.steps:
            step = STEP_DEFINITIONS.get(step_id)
            if step:
                all_steps.append(serialize_step(step))

    return {
        "id": pipeline.id,
        "label": pipeline.label,
        "description": pipeline.description,
        "phases": [
            {
                "id": p.id,
                "label": p.label,
                "steps": p.steps,
            }
            for p in pipeline.phases
        ],
        "all_steps": all_steps,
    }
