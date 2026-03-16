"""Phase 2 步骤实现：抓取原文。

委托给 Phase2PipelineService 内部方法，
通过 StepContext.artifacts 传递 SourceArticle 给后续步骤。
"""

from __future__ import annotations

from app.core.pipeline import StepConfigField, StepContext, StepResult
from app.core.enums import TaskStatus
from app.models.audit_log import AuditLog
from app.models.source_article import SourceArticle
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.task_repository import TaskRepository
from app.services.source_fetch_service import SourceFetchService


class FetchSourceStep:
    """抓取原文 — 对应 Phase2 的 fetch 阶段。"""

    id = "fetch_source"
    label = "抓取原文"
    icon = "📥"
    config_schema: list[StepConfigField] = []

    def run(self, ctx: StepContext) -> StepResult:
        session = ctx.session
        tasks = TaskRepository(session)
        sources = SourceArticleRepository(session)
        audit_logs = AuditLogRepository(session)
        fetcher = SourceFetchService()

        task = tasks.get_by_id(ctx.task_id)
        if task is None:
            return StepResult(success=False, error="Task not found")

        task.status = TaskStatus.FETCHING_SOURCE
        audit_logs.create(AuditLog(task_id=task.id, action="fetch_source.started", details={"url": task.source_url}))
        session.commit()

        try:
            fetched = fetcher.fetch(task.id, task.source_url, task.source_type or "web")
        except Exception as exc:
            task.status = TaskStatus.FETCH_FAILED
            session.commit()
            return StepResult(success=False, error=str(exc))

        # 保存/更新 SourceArticle
        source = sources.get_latest_by_task_id(task.id)
        if source is None:
            source = sources.create(SourceArticle(task_id=task.id, url=fetched.final_url))

        source.url = fetched.final_url
        source.title = fetched.title
        source.author = fetched.author
        source.published_at = fetched.published_at
        source.cover_image_url = fetched.cover_image_url
        source.raw_html = fetched.raw_html
        source.cleaned_text = fetched.cleaned_text
        source.summary = fetched.summary
        source.snapshot_path = fetched.snapshot_path
        source.fetch_status = "success"
        source.word_count = fetched.word_count
        source.content_hash = fetched.content_hash

        task.status = TaskStatus.SOURCE_READY
        audit_logs.create(AuditLog(task_id=task.id, action="fetch_source.completed", details={"title": fetched.title}))
        session.commit()

        return StepResult(success=True, artifacts={"source_article": source, "fetched": fetched})
