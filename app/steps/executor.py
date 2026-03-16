"""Pipeline Executor — 统一入口，安全切换新旧执行逻辑。

Worker 脚本调用此模块的 run_pipeline_for_phase() 函数，
根据 settings 中的 feature flag 决定使用旧 Service 还是新 Runner。
"""

from __future__ import annotations

import logging
from typing import Literal

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

PhaseType = Literal["phase2", "phase3", "phase4"]


def run_pipeline_for_phase(phase: PhaseType, session: Session, task_id: str) -> None:
    """统一 pipeline 执行入口。

    先检查 settings 表中的 feature flag，如果启用了可拔插 pipeline 模式，
    使用 PipelineRunner + Step 类执行；否则回退到旧的 Phase*PipelineService。
    """
    if _use_pluggable_pipeline(session, phase):
        logger.info("pipeline.pluggable phase=%s task=%s", phase, task_id)
        _run_with_runner(phase, session, task_id)
    else:
        logger.info("pipeline.legacy phase=%s task=%s", phase, task_id)
        _run_legacy(phase, session, task_id)


def _use_pluggable_pipeline(session: Session, phase: PhaseType) -> bool:
    """检查是否启用可拔插模式。默认关闭。"""
    try:
        from app.services.system_setting_service import SystemSettingService
        svc = SystemSettingService(session)
        val = svc.get_effective_value(f"pipeline.pluggable.{phase}")
        return str(val).lower() in ("true", "1", "yes", "on")
    except Exception:
        return False


def _run_legacy(phase: PhaseType, session: Session, task_id: str) -> None:
    """旧模式：直接调用 Phase*PipelineService.run()。"""
    if phase == "phase2":
        from app.services.phase2_pipeline_service import Phase2PipelineService
        Phase2PipelineService(session).run(task_id)
    elif phase == "phase3":
        from app.services.phase3_pipeline_service import Phase3PipelineService
        Phase3PipelineService(session).run(task_id)
    elif phase == "phase4":
        from app.services.phase4_pipeline_service import Phase4PipelineService
        Phase4PipelineService(session).run(task_id)
    else:
        raise ValueError(f"Unknown phase: {phase}")


def _run_with_runner(phase: PhaseType, session: Session, task_id: str) -> None:
    """新模式：使用 PipelineRunner + Step 类执行。"""
    from app.steps.runner import PipelineRunner

    steps = _build_steps_for_phase(phase)
    runner = PipelineRunner(steps=steps, session=session)
    runner.execute(task_id)


def _build_steps_for_phase(phase: PhaseType) -> list:
    """按 phase 构建对应的 Step 实例列表。"""
    if phase == "phase2":
        from app.steps.fetch_source import FetchSourceStep
        return [FetchSourceStep()]

    elif phase == "phase3":
        from app.steps.analyze_source import AnalyzeSourceStep
        from app.steps.search_related import SearchRelatedStep, FetchRelatedStep
        from app.steps.build_brief import BuildBriefStep
        return [AnalyzeSourceStep(), SearchRelatedStep(), FetchRelatedStep(), BuildBriefStep()]

    elif phase == "phase4":
        from app.steps.produce import (
            GenerateArticleStep,
            ReviewArticleStep,
            HumanizeArticleStep,
            PushDraftStep,
        )
        return [GenerateArticleStep(), ReviewArticleStep(), HumanizeArticleStep(), PushDraftStep()]

    else:
        raise ValueError(f"Unknown phase: {phase}")
