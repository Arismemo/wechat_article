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

    def select_generation(
        self,
        task_id: str,
        generation_id: str,
        *,
        operator: Optional[str] = None,
        note: Optional[str] = None,
    ) -> ManualReviewResult:
        task = self._require_task(task_id)
        generation = self._require_generation_for_task(task.id, generation_id)

        selected_draft = self.wechat_drafts.get_latest_by_generation_id(generation.id)
        selected_has_saved_draft = self._has_saved_draft(selected_draft)
        latest_task_draft = self.wechat_drafts.get_latest_successful_by_task_id(task.id)
        if (
            latest_task_draft is not None
            and latest_task_draft.generation_id != generation.id
            and not selected_has_saved_draft
        ):
            raise ManualReviewConflictError(
                "Another generation has already been pushed to WeChat draft. Select that version or clear the draft relationship first."
            )

        previous_task_status = task.status
        previous_generation_status = generation.status
        generation.status = "accepted"
        self.tasks.update_runtime_state(
            task,
            status=TaskStatus.DRAFT_SAVED.value if selected_has_saved_draft else TaskStatus.REVIEW_PASSED.value,
            error_code=None,
            error_message=None,
        )
        self._log_action(
            task.id,
            action="phase5.manual_review.selected_generation",
            operator=operator,
            payload={
                "generation_id": generation.id,
                "selected_version_no": generation.version_no,
                "previous_generation_status": previous_generation_status,
                "previous_task_status": previous_task_status,
                "resulting_task_status": task.status,
                "has_saved_draft": selected_has_saved_draft,
                "media_id": selected_draft.media_id if selected_has_saved_draft and selected_draft else None,
                "note": self._normalize_note(note),
            },
        )
        self.session.commit()
        return ManualReviewResult(
            task_id=task.id,
            status=task.status,
            generation_id=generation.id,
            decision="selected",
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
        task = self._require_task(task_id)
        generation = self.generations.get_latest_by_task_id(task.id)
        if generation is None:
            raise ValueError("Latest generation not found.")
        return task, generation

    def _require_task(self, task_id: str) -> Task:
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")
        return task

    def _require_generation_for_task(self, task_id: str, generation_id: str) -> Generation:
        generation = self.generations.get_by_id(generation_id)
        if generation is None:
            raise ValueError("Generation not found.")
        if generation.task_id != task_id:
            raise ValueError("Generation does not belong to task.")
        return generation

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

    def _has_saved_draft(self, draft: Optional[object]) -> bool:
        return bool(draft and getattr(draft, "push_status", None) == "success" and getattr(draft, "media_id", None))
