"""Phase 3 步骤实现：深度分析。

通过 LLM 对原文进行主题/受众/角度/风险分析，
结果存入 ArticleAnalysis 表并传递给后续步骤。
"""

from __future__ import annotations

from app.core.pipeline import StepConfigField, StepContext, StepResult
from app.core.enums import TaskStatus
from app.models.article_analysis import ArticleAnalysis
from app.models.audit_log import AuditLog
from app.repositories.article_analysis_repository import ArticleAnalysisRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.task_repository import TaskRepository
from app.services.llm_runtime_service import LLMRuntimeService


class AnalyzeSourceStep:
    """深度分析 — 对应 Phase3 的 analyze 阶段。"""

    id = "analyze_source"
    label = "深度分析"
    icon = "🔍"
    config_schema: list[StepConfigField] = []

    def run(self, ctx: StepContext) -> StepResult:
        session = ctx.session
        tasks = TaskRepository(session)
        sources = SourceArticleRepository(session)
        analyses = ArticleAnalysisRepository(session)
        audit_logs = AuditLogRepository(session)

        task = tasks.get_by_id(ctx.task_id)
        if task is None:
            return StepResult(success=False, error="Task not found")

        source = ctx.artifacts.get("source_article") or sources.get_latest_by_task_id(task.id)
        if source is None:
            return StepResult(success=False, error="Source article not found")

        task.status = TaskStatus.ANALYZING_SOURCE
        audit_logs.create(AuditLog(task_id=task.id, action="analyze_source.started", details={"title": source.title}))
        session.commit()

        try:
            # 委托给 Phase3PipelineService 的分析方法
            from app.services.phase3_pipeline_service import Phase3PipelineService
            phase3 = Phase3PipelineService(session)
            payload = phase3._analyze_source(source)
        except Exception as exc:
            task.status = TaskStatus.ANALYZE_FAILED
            session.commit()
            return StepResult(success=False, error=str(exc))

        analysis = analyses.create(
            ArticleAnalysis(
                task_id=task.id,
                theme=payload["theme"],
                audience=payload["audience"],
                angle=payload["angle"],
                tone=payload["tone"],
                key_points=phase3._wrap_list(payload["key_points"]),
                facts=phase3._wrap_list(payload["facts"]),
                hooks=phase3._wrap_list(payload["hooks"]),
                risks=phase3._wrap_list(payload["risks"]),
                gaps=phase3._wrap_list(payload["gaps"]),
                structure=phase3._wrap_list(payload["structure"]),
            )
        )
        audit_logs.create(AuditLog(task_id=task.id, action="analyze_source.completed", details={"theme": analysis.theme}))
        session.commit()

        return StepResult(success=True, artifacts={"analysis": analysis})
