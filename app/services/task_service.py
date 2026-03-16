from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import ACTIVE_TASK_STATUSES, TaskStatus
from app.core.progress import get_progress
from app.models.audit_log import AuditLog
from app.models.task import Task
from app.repositories.article_analysis_repository import ArticleAnalysisRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.content_brief_repository import ContentBriefRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.prompt_experiment_repository import PromptExperimentRepository
from app.repositories.publication_metric_repository import PublicationMetricRepository
from app.repositories.related_article_repository import RelatedArticleRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.style_asset_repository import StyleAssetRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.task_dedupe_slot_repository import TaskDedupeSlotRepository
from app.repositories.wechat_draft_repository import WechatDraftRepository
from app.models.task_dedupe_slot import TaskDedupeSlot
from app.schemas.ingest import IngestLinkRequest
from app.services.url_service import detect_source_type, normalize_url
from app.services.wechat_draft_metadata_service import build_wechat_draft_metadata


@dataclass
class TaskSummary:
    task_id: str
    task_code: str
    source_url: str
    source_type: Optional[str]
    status: str
    progress: int
    title: Optional[str]
    wechat_media_id: Optional[str]
    wechat_draft_url: Optional[str]
    wechat_draft_url_direct: bool
    wechat_draft_url_hint: Optional[str]
    brief_id: Optional[str]
    generation_id: Optional[str]
    related_article_count: int
    error: Optional[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class TaskDeleteResult:
    task_id: str
    task_code: str
    deleted: bool


class TaskService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.analyses = ArticleAnalysisRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.source_articles = SourceArticleRepository(session)
        self.content_briefs = ContentBriefRepository(session)
        self.generations = GenerationRepository(session)
        self.prompt_experiments = PromptExperimentRepository(session)
        self.publication_metrics = PublicationMetricRepository(session)
        self.related_articles = RelatedArticleRepository(session)
        self.reviews = ReviewReportRepository(session)
        self.style_assets = StyleAssetRepository(session)
        self.wechat_drafts = WechatDraftRepository(session)
        self.task_dedupe_slots = TaskDedupeSlotRepository(session)

    def ingest_link(self, payload: IngestLinkRequest) -> tuple[Task, bool]:
        normalized_url = normalize_url(str(payload.url))
        existing_task = self._get_deduped_task(normalized_url)
        if existing_task:
            self._log_action(
                task_id=existing_task.id,
                action="task.duplicate_detected",
                payload={"normalized_url": normalized_url},
            )
            self.session.commit()
            return existing_task, True

        try:
            task = self.tasks.create(
                Task(
                    task_code=self._generate_task_code(),
                    source_url=str(payload.url),
                    normalized_url=normalized_url,
                    source_type=detect_source_type(normalized_url),
                    status=TaskStatus.QUEUED.value,
                )
            )
            self.task_dedupe_slots.create(TaskDedupeSlot(task_id=task.id, normalized_url=normalized_url))
            self._log_action(
                task_id=task.id,
                action="task.created",
                payload={
                    "source": payload.source,
                    "device_id": payload.device_id,
                    "trigger": payload.trigger,
                    "note": payload.note,
                },
            )
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing_task = self._get_deduped_task(normalized_url)
            if existing_task is None:
                raise
            self._log_action(
                task_id=existing_task.id,
                action="task.duplicate_detected",
                payload={"normalized_url": normalized_url, "reason": "dedupe_slot_conflict"},
            )
            self.session.commit()
            return existing_task, True

        self.session.refresh(task)
        return task, False

    def require_task(self, task_id: str) -> Task:
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")
        return task

    def mark_queued_for_phase2(self, task: Task, reason: str) -> Task:
        self.tasks.update_runtime_state(
            task,
            status=TaskStatus.QUEUED.value,
            error_code=None,
            error_message=None,
        )
        self._log_action(task.id, "phase2.enqueued", {"reason": reason})
        self.session.commit()
        return task

    def mark_queued_for_phase3(self, task: Task, reason: str) -> Task:
        self.tasks.update_runtime_state(
            task,
            status=TaskStatus.QUEUED.value,
            error_code=None,
            error_message=None,
        )
        self._log_action(task.id, "phase3.enqueued", {"reason": reason})
        self.session.commit()
        return task

    def mark_queued_for_phase4(self, task: Task, reason: str) -> Task:
        self.tasks.update_runtime_state(
            task,
            status=TaskStatus.QUEUED.value,
            error_code=None,
            error_message=None,
        )
        self._log_action(task.id, "phase4.enqueued", {"reason": reason})
        self.session.commit()
        return task

    def list_recent(
        self,
        limit: int = 10,
        *,
        active_only: bool = False,
        status_filter: Optional[str] = None,
        source_type: Optional[str] = None,
        query: Optional[str] = None,
        created_after: Optional[datetime] = None,
    ) -> list[TaskSummary]:
        items: list[TaskSummary] = []
        task_rows = self.tasks.list_recent(
            limit,
            active_only=active_only,
            status_filter=status_filter,
            source_type=source_type,
            query=query,
            created_after=created_after,
        )
        task_ids = [task.id for task in task_rows]
        latest_sources = self.source_articles.get_latest_by_task_ids(task_ids)
        latest_briefs = self.content_briefs.get_latest_by_task_ids(task_ids)
        latest_generations = self.generations.get_latest_by_task_ids(task_ids)
        latest_drafts = self.wechat_drafts.get_latest_by_task_ids(task_ids)
        related_counts = self.related_articles.count_by_task_ids(task_ids, selected_only=True)

        for task in task_rows:
            source_article = latest_sources.get(task.id)
            content_brief = latest_briefs.get(task.id)
            generation = latest_generations.get(task.id)
            wechat_draft = latest_drafts.get(task.id)
            draft_metadata = build_wechat_draft_metadata(wechat_draft)
            related_count = related_counts.get(task.id, 0)
            error = task.error_message or task.error_code
            items.append(
                TaskSummary(
                    task_id=task.id,
                    task_code=task.task_code,
                    source_url=task.source_url,
                    source_type=task.source_type,
                    status=task.status,
                    progress=self._progress_for_status(task.status),
                    title=source_article.title if source_article else None,
                    wechat_media_id=draft_metadata.media_id,
                    wechat_draft_url=draft_metadata.draft_url,
                    wechat_draft_url_direct=draft_metadata.draft_url_direct,
                    wechat_draft_url_hint=draft_metadata.draft_url_hint,
                    brief_id=content_brief.id if content_brief else None,
                    generation_id=generation.id if generation else None,
                    related_article_count=related_count,
                    error=error,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                )
            )
        return items

    def delete_task(self, task_id: str, *, operator: str) -> TaskDeleteResult:
        task = self.require_task(task_id)
        generation_ids = self.generations.list_ids_by_task_id(task.id)

        self.audit_logs.clear_task_refs(task.id)
        self.style_assets.clear_source_task_refs(task.id)
        self.style_assets.clear_source_generation_refs(generation_ids)
        self.prompt_experiments.clear_last_task_refs(task.id)
        self.prompt_experiments.clear_last_generation_refs(generation_ids)

        self.wechat_drafts.delete_by_task_id(task.id)
        self.publication_metrics.delete_by_generation_ids(generation_ids)
        self.publication_metrics.delete_by_task_id(task.id)
        self.reviews.delete_by_generation_ids(generation_ids)
        self.generations.delete_by_task_id(task.id)
        self.content_briefs.delete_by_task_id(task.id)
        self.related_articles.delete_by_task_id(task.id)
        self.source_articles.delete_by_task_id(task.id)
        self.analyses.delete_by_task_id(task.id)
        self.tasks.delete(task)
        self.audit_logs.create(
            AuditLog(
                task_id=None,
                action="task.deleted",
                operator=operator or "system",
                payload={
                    "task_id": task.id,
                    "task_code": task.task_code,
                    "source_url": task.source_url,
                    "status": task.status,
                },
            )
        )
        self.session.commit()
        return TaskDeleteResult(task_id=task.id, task_code=task.task_code, deleted=True)

    def _generate_task_code(self) -> str:
        return f"tsk_{uuid4().hex[:12]}"

    def _get_deduped_task(self, normalized_url: str) -> Optional[Task]:
        dedupe_slot = self.task_dedupe_slots.get_by_normalized_url(normalized_url)
        if dedupe_slot is not None:
            task = self.tasks.get_by_id(dedupe_slot.task_id)
            if task is not None and task.status in {status.value for status in ACTIVE_TASK_STATUSES}:
                return task
            self.task_dedupe_slots.delete_by_task_id(dedupe_slot.task_id)
        return self.tasks.get_active_by_normalized_url(normalized_url)

    def _log_action(self, task_id: str, action: str, payload: Optional[dict]) -> None:
        self.audit_logs.create(
            AuditLog(
                task_id=task_id,
                action=action,
                operator="system",
                payload=payload,
            )
        )

    def _progress_for_status(self, status: str) -> int:
        try:
            return get_progress(TaskStatus(status))
        except ValueError:
            return 0
