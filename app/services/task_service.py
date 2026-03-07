from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.core.progress import get_progress
from app.models.audit_log import AuditLog
from app.models.task import Task
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.content_brief_repository import ContentBriefRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.related_article_repository import RelatedArticleRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.wechat_draft_repository import WechatDraftRepository
from app.schemas.ingest import IngestLinkRequest
from app.services.url_service import detect_source_type, normalize_url


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
    brief_id: Optional[str]
    generation_id: Optional[str]
    related_article_count: int
    error: Optional[str]
    created_at: datetime
    updated_at: datetime


class TaskService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.source_articles = SourceArticleRepository(session)
        self.content_briefs = ContentBriefRepository(session)
        self.generations = GenerationRepository(session)
        self.related_articles = RelatedArticleRepository(session)
        self.wechat_drafts = WechatDraftRepository(session)

    def ingest_link(self, payload: IngestLinkRequest) -> tuple[Task, bool]:
        normalized_url = normalize_url(str(payload.url))
        existing_task = self.tasks.get_active_by_normalized_url(normalized_url)
        if existing_task:
            self._log_action(
                task_id=existing_task.id,
                action="task.duplicate_detected",
                payload={"normalized_url": normalized_url},
            )
            self.session.commit()
            return existing_task, True

        task = self.tasks.create(
            Task(
                task_code=self._generate_task_code(),
                source_url=str(payload.url),
                normalized_url=normalized_url,
                source_type=detect_source_type(normalized_url),
                status=TaskStatus.QUEUED.value,
            )
        )
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
        self.session.refresh(task)
        return task, False

    def require_task(self, task_id: str) -> Task:
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")
        return task

    def mark_queued_for_phase2(self, task: Task, reason: str) -> Task:
        task.status = TaskStatus.QUEUED.value
        task.error_code = None
        task.error_message = None
        self._log_action(task.id, "phase2.enqueued", {"reason": reason})
        self.session.commit()
        return task

    def mark_queued_for_phase3(self, task: Task, reason: str) -> Task:
        task.status = TaskStatus.QUEUED.value
        task.error_code = None
        task.error_message = None
        self._log_action(task.id, "phase3.enqueued", {"reason": reason})
        self.session.commit()
        return task

    def mark_queued_for_phase4(self, task: Task, reason: str) -> Task:
        task.status = TaskStatus.QUEUED.value
        task.error_code = None
        task.error_message = None
        self._log_action(task.id, "phase4.enqueued", {"reason": reason})
        self.session.commit()
        return task

    def list_recent(self, limit: int = 10) -> list[TaskSummary]:
        items: list[TaskSummary] = []
        for task in self.tasks.list_recent(limit):
            source_article = self.source_articles.get_latest_by_task_id(task.id)
            content_brief = self.content_briefs.get_latest_by_task_id(task.id)
            generation = self.generations.get_latest_by_task_id(task.id)
            wechat_draft = self.wechat_drafts.get_latest_by_task_id(task.id)
            related_count = self.related_articles.count_by_task_id(task.id, selected_only=True)
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
                    wechat_media_id=wechat_draft.media_id if wechat_draft else None,
                    brief_id=content_brief.id if content_brief else None,
                    generation_id=generation.id if generation else None,
                    related_article_count=related_count,
                    error=error,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                )
            )
        return items

    def _generate_task_code(self) -> str:
        return f"tsk_{uuid4().hex[:12]}"

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
