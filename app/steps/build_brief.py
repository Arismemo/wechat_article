"""Phase 3 步骤实现：生成 Brief。

根据原文分析和素材生成创作纲要（ContentBrief）。
"""

from __future__ import annotations

from app.core.pipeline import StepConfigField, StepContext, StepResult
from app.core.enums import TaskStatus
from app.models.audit_log import AuditLog
from app.models.content_brief import ContentBrief
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.content_brief_repository import ContentBriefRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.article_analysis_repository import ArticleAnalysisRepository
from app.repositories.task_repository import TaskRepository


class BuildBriefStep:
    """生成 Brief — 对应 Phase3 的 brief 阶段。"""

    id = "build_brief"
    label = "生成 Brief"
    icon = "📋"
    config_schema: list[StepConfigField] = []

    def run(self, ctx: StepContext) -> StepResult:
        session = ctx.session
        tasks = TaskRepository(session)
        briefs = ContentBriefRepository(session)
        audit_logs = AuditLogRepository(session)

        task = tasks.get_by_id(ctx.task_id)
        if task is None:
            return StepResult(success=False, error="Task not found")

        source = ctx.artifacts.get("source_article") or SourceArticleRepository(session).get_latest_by_task_id(task.id)
        analysis = ctx.artifacts.get("analysis") or ArticleAnalysisRepository(session).get_latest_by_task_id(task.id)
        related = ctx.artifacts.get("related_articles", [])

        if source is None or analysis is None:
            return StepResult(success=False, error="Source or analysis not found")

        task.status = TaskStatus.BUILDING_BRIEF
        audit_logs.create(AuditLog(task_id=task.id, action="build_brief.started", details={"related_count": len(related)}))
        session.commit()

        try:
            from app.services.phase3_pipeline_service import Phase3PipelineService
            phase3 = Phase3PipelineService(session)
            payload = phase3._build_brief(source, analysis, related)
        except Exception as exc:
            task.status = TaskStatus.BRIEF_FAILED
            session.commit()
            return StepResult(success=False, error=str(exc))

        brief = briefs.create(
            ContentBrief(
                task_id=task.id,
                brief_version=briefs.get_next_brief_version(task.id),
                positioning=payload["positioning"],
                new_angle=payload["new_angle"],
                target_reader=payload["target_reader"],
                must_cover=phase3._wrap_list(payload["must_cover"]),
                must_avoid=phase3._wrap_list(payload["must_avoid"]),
                difference_matrix=phase3._wrap_list(payload["difference_matrix"]),
                outline=phase3._wrap_list(payload["outline"]),
                title_directions=phase3._wrap_list(payload["title_directions"]),
            )
        )
        task.status = TaskStatus.BRIEF_READY
        audit_logs.create(AuditLog(task_id=task.id, action="build_brief.completed", details={"brief_id": brief.id}))
        session.commit()

        return StepResult(success=True, artifacts={"brief": brief})
