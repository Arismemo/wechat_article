from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.review_report import ReviewReport


class ReviewReportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_latest_by_generation_id(self, generation_id: str) -> Optional[ReviewReport]:
        statement = (
            select(ReviewReport)
            .where(ReviewReport.generation_id == generation_id)
            .order_by(ReviewReport.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def create(self, report: ReviewReport) -> ReviewReport:
        self.session.add(report)
        self.session.flush()
        return report
