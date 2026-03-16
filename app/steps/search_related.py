"""Phase 3 步骤实现：搜索素材 + 抓取素材。

搜索相关文章并抓取内容，结果传递给 Brief 生成步骤。
"""

from __future__ import annotations

from app.core.pipeline import StepConfigField, StepContext, StepResult
from app.core.enums import TaskStatus
from app.models.audit_log import AuditLog
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.article_analysis_repository import ArticleAnalysisRepository
from app.repositories.related_article_repository import RelatedArticleRepository
from app.repositories.task_repository import TaskRepository


class SearchRelatedStep:
    """搜索素材 — 对应 Phase3 的搜索阶段。"""

    id = "search_related"
    label = "搜索素材"
    icon = "🌐"
    config_schema: list[StepConfigField] = []

    def run(self, ctx: StepContext) -> StepResult:
        session = ctx.session
        tasks = TaskRepository(session)
        audit_logs = AuditLogRepository(session)

        task = tasks.get_by_id(ctx.task_id)
        if task is None:
            return StepResult(success=False, error="Task not found")

        task.status = TaskStatus.SEARCHING_RELATED
        audit_logs.create(AuditLog(task_id=task.id, action="search_related.started", details={}))
        session.commit()

        try:
            from app.services.phase3_pipeline_service import Phase3PipelineService
            phase3 = Phase3PipelineService(session)
            source = ctx.artifacts.get("source_article") or SourceArticleRepository(session).get_latest_by_task_id(task.id)
            analysis = ctx.artifacts.get("analysis") or ArticleAnalysisRepository(session).get_latest_by_task_id(task.id)
            if source is None or analysis is None:
                return StepResult(success=False, error="Source or analysis not found")

            queries = phase3._build_queries(source, analysis)
            raw_results = phase3.search.search_many(queries, count_per_query=phase3.settings.phase3_search_per_query)
            ranked_results = phase3.search.rank_results(
                source_url=source.url,
                source_title=source.title or "",
                analysis_theme=analysis.theme or "",
                query_texts=queries,
                results=raw_results,
            )
        except Exception as exc:
            task.status = TaskStatus.SEARCH_FAILED
            session.commit()
            return StepResult(success=False, error=str(exc))

        audit_logs.create(AuditLog(task_id=task.id, action="search_related.completed", details={"count": len(ranked_results)}))
        session.commit()

        return StepResult(success=True, artifacts={"ranked_results": ranked_results, "queries": queries})


class FetchRelatedStep:
    """抓取素材 — 对应 Phase3 的抓取相关文章阶段。"""

    id = "fetch_related"
    label = "抓取素材"
    icon = "📎"
    config_schema: list[StepConfigField] = []

    def run(self, ctx: StepContext) -> StepResult:
        session = ctx.session
        tasks = TaskRepository(session)
        audit_logs = AuditLogRepository(session)
        related_repo = RelatedArticleRepository(session)

        task = tasks.get_by_id(ctx.task_id)
        if task is None:
            return StepResult(success=False, error="Task not found")

        ranked_results = ctx.artifacts.get("ranked_results", [])
        if not ranked_results:
            # 搜索没有结果，跳过但不算失败
            return StepResult(success=True, artifacts={"related_articles": []})

        task.status = TaskStatus.FETCHING_RELATED
        audit_logs.create(AuditLog(task_id=task.id, action="fetch_related.started", details={"count": len(ranked_results)}))
        session.commit()

        try:
            from app.services.phase3_pipeline_service import Phase3PipelineService
            phase3 = Phase3PipelineService(session)
            related_repo.delete_by_task_id(task.id)
            fetched = phase3._fetch_related_articles(task, ranked_results)
        except Exception as exc:
            task.status = TaskStatus.SEARCH_FAILED
            session.commit()
            return StepResult(success=False, error=str(exc))

        audit_logs.create(AuditLog(task_id=task.id, action="fetch_related.completed", details={"fetched_count": len(fetched)}))
        session.commit()

        return StepResult(success=True, artifacts={"related_articles": fetched})
