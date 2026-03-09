from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.generation import Generation
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.schemas.tasks import SelectedGenerationResponse


MANUAL_SELECTION_ACTIONS = [
    "phase5.manual_review.selected_generation",
    "phase5.manual_review.approved",
]


@dataclass(frozen=True)
class SelectedGenerationContext:
    generation: Generation
    source: str
    source_action: Optional[str] = None
    operator: Optional[str] = None
    note: Optional[str] = None
    selected_at: Optional[datetime] = None
    decision: Optional[str] = None


class TaskGenerationSelectionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audits = AuditLogRepository(session)
        self.generations = GenerationRepository(session)
        self.reviews = ReviewReportRepository(session)

    def resolve_selected_generation(self, task_id: str) -> Optional[SelectedGenerationContext]:
        audit = self.audits.get_latest_by_task_id_and_actions(task_id, MANUAL_SELECTION_ACTIONS)
        if audit is None:
            return None
        payload = audit.payload if isinstance(audit.payload, dict) else {}
        generation_id = str(payload.get("generation_id") or "").strip()
        if not generation_id:
            return None
        generation = self.generations.get_by_id(generation_id)
        if generation is None or generation.task_id != task_id or generation.status != "accepted":
            return None
        review = self.reviews.get_latest_by_generation_id(generation.id)
        source = "manual_selected" if audit.action == "phase5.manual_review.selected_generation" else "manual_approved"
        return SelectedGenerationContext(
            generation=generation,
            source=source,
            source_action=audit.action,
            operator=audit.operator,
            note=(payload.get("note") or None) if isinstance(payload.get("note"), str) else None,
            selected_at=audit.created_at,
            decision=review.final_decision if review is not None else None,
        )

    def resolve_current_generation(self, task_id: str) -> Optional[SelectedGenerationContext]:
        selected = self.resolve_selected_generation(task_id)
        if selected is not None:
            return selected

        latest_accepted = self.generations.get_latest_accepted_by_task_id(task_id)
        if latest_accepted is not None:
            review = self.reviews.get_latest_by_generation_id(latest_accepted.id)
            return SelectedGenerationContext(
                generation=latest_accepted,
                source="latest_accepted",
                decision=review.final_decision if review is not None else None,
            )

        latest_generation = self.generations.get_latest_by_task_id(task_id)
        if latest_generation is None:
            return None
        review = self.reviews.get_latest_by_generation_id(latest_generation.id)
        return SelectedGenerationContext(
            generation=latest_generation,
            source="latest_generation",
            decision=review.final_decision if review is not None else None,
        )

    def resolve_current_accepted_generation(self, task_id: str) -> Optional[Generation]:
        current = self.resolve_current_generation(task_id)
        if current is not None and current.generation.status == "accepted":
            return current.generation
        return self.generations.get_latest_accepted_by_task_id(task_id)

    def build_response(self, task_id: str) -> Optional[SelectedGenerationResponse]:
        current = self.resolve_current_generation(task_id)
        if current is None:
            return None
        return SelectedGenerationResponse(
            generation_id=current.generation.id,
            version_no=current.generation.version_no,
            title=current.generation.title,
            status=current.generation.status,
            decision=current.decision,
            source=current.source,
            source_action=current.source_action,
            operator=current.operator,
            note=current.note,
            selected_at=current.selected_at,
        )
