from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.models.audit_log import AuditLog
from app.models.generation import Generation
from app.models.task import Task
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.wechat_draft_repository import WechatDraftRepository


@dataclass
class ManualReviewResult:
    task_id: str
    status: str
    generation_id: Optional[str]
    decision: str


class ManualReviewConflictError(ValueError):
    pass


class ManualReviewService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.generations = GenerationRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.wechat_drafts = WechatDraftRepository(session)

    def approve_latest_generation(
        self,
        task_id: str,
        *,
        operator: Optional[str] = None,
        note: Optional[str] = None,
    ) -> ManualReviewResult:
        task, generation = self._require_task_and_generation(task_id)
        previous_task_status = task.status
        previous_generation_status = generation.status
        existing_draft = self.wechat_drafts.get_latest_by_generation_id(generation.id)
        has_saved_draft = bool(existing_draft and existing_draft.push_status == "success")

        generation.status = "accepted"
        self.tasks.update_runtime_state(
            task,
            status=TaskStatus.DRAFT_SAVED.value if has_saved_draft else TaskStatus.REVIEW_PASSED.value,
            error_code=None,
            error_message=None,
        )
        self._log_action(
            task.id,
            action="phase5.manual_review.approved",
            operator=operator,
            payload={
                "generation_id": generation.id,
                "previous_generation_status": previous_generation_status,
                "previous_task_status": previous_task_status,
                "resulting_task_status": task.status,
                "has_saved_draft": has_saved_draft,
                "note": self._normalize_note(note),
            },
        )
        self.session.commit()
        return ManualReviewResult(
            task_id=task.id,
            status=task.status,
            generation_id=generation.id,
            decision="approved",
        )

    def reject_latest_generation(
        self,
        task_id: str,
        *,
        operator: Optional[str] = None,
        note: Optional[str] = None,
    ) -> ManualReviewResult:
        task, generation = self._require_task_and_generation(task_id)
        existing_draft = self.wechat_drafts.get_latest_by_generation_id(generation.id)
        if existing_draft and existing_draft.push_status == "success":
            raise ManualReviewConflictError(
                "Latest generation has already been pushed to WeChat draft and cannot be rejected."
            )

        previous_task_status = task.status
        previous_generation_status = generation.status
        generation.status = "rejected"
        self.tasks.update_runtime_state(
            task,
            status=TaskStatus.NEEDS_REGENERATE.value,
            error_code=None,
            error_message=None,
        )
        self._log_action(
            task.id,
            action="phase5.manual_review.rejected",
            operator=operator,
            payload={
                "generation_id": generation.id,
                "previous_generation_status": previous_generation_status,
                "previous_task_status": previous_task_status,
                "resulting_task_status": task.status,
                "note": self._normalize_note(note),
            },
        )
        self.session.commit()
        return ManualReviewResult(
            task_id=task.id,
            status=task.status,
            generation_id=generation.id,
            decision="rejected",
        )

    def _require_task_and_generation(self, task_id: str) -> tuple[Task, Generation]:
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")

        generation = self.generations.get_latest_by_task_id(task.id)
        if generation is None:
            raise ValueError("Latest generation not found.")
        return task, generation

    def _log_action(
        self,
        task_id: str,
        *,
        action: str,
        operator: Optional[str],
        payload: Optional[dict],
    ) -> None:
        normalized_operator = (operator or "").strip() or "manual"
        self.audit_logs.create(
            AuditLog(
                task_id=task_id,
                action=action,
                operator=normalized_operator,
                payload=payload,
            )
        )

    def _normalize_note(self, note: Optional[str]) -> Optional[str]:
        normalized = (note or "").strip()
        return normalized or None
