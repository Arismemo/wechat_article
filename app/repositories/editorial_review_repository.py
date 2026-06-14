from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.editorial_review import EditorialReview
from app.schemas.editorial import EditorialVerdict


class EditorialReviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, review: EditorialReview) -> EditorialReview:
        self.session.add(review)
        self.session.flush()
        return review

    def get_latest_by_task_id(self, task_id: str) -> Optional[EditorialReview]:
        statement = (
            select(EditorialReview)
            .where(EditorialReview.task_id == task_id)
            .order_by(EditorialReview.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_by_generation_id(self, generation_id: str) -> Optional[EditorialReview]:
        statement = (
            select(EditorialReview)
            .where(EditorialReview.generation_id == generation_id)
            .order_by(EditorialReview.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def update(self, review: EditorialReview) -> EditorialReview:
        self.session.flush()
        return review

    def update_result(
        self,
        review: EditorialReview,
        *,
        status: str,
        rounds_used: int,
        verdict: EditorialVerdict,
        transcript: dict,
        review_report_id: str,
    ) -> EditorialReview:
        review.status = status
        review.rounds_used = rounds_used
        review.decision = verdict.decision
        review.final_scores = verdict.final_scores
        review.rationale = verdict.rationale
        review.revision_directives = [rd.model_dump() for rd in verdict.revision_directives]
        review.dissent_summary = verdict.dissent_summary
        review.transcript = transcript
        review.review_report_id = review_report_id
        self.session.flush()
        return review
