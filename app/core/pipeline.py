"""可拔插 Pipeline 核心抽象。

定义 PipelineStep 协议、StepContext 上下文和 StepResult 返回值，
供所有 pipeline 步骤实现统一接口。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class StepContext:
    """Pipeline 上下文——在步骤间传递的共享状态。"""

    task_id: str
    session: Any  # SQLAlchemy Session
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """步骤执行结果。"""

    success: bool
    artifacts: dict[str, Any] = field(default_factory=dict)
    skip_remaining: bool = False
    error: str | None = None


@dataclass(frozen=True)
class StepConfigField:
    """步骤可配置参数的 schema 描述。"""

    key: str
    label: str
    value_type: str  # "float" | "integer" | "boolean" | "string" | "enum"
    default: Any
    description: str = ""


@runtime_checkable
class PipelineStep(Protocol):
    """每个步骤必须实现的协议。"""

    id: str
    label: str
    icon: str
    config_schema: list[StepConfigField]

    def run(self, ctx: StepContext) -> StepResult: ...
