from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.generation import Generation


class GenerationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, generation_id: str) -> Optional[Generation]:
        return self.session.get(Generation, generation_id)

    def get_latest_by_task_id(self, task_id: str) -> Optional[Generation]:
        statement = (
            select(Generation)
            .where(Generation.task_id == task_id)
            .order_by(Generation.version_no.desc(), Generation.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_latest_accepted_by_task_id(self, task_id: str) -> Optional[Generation]:
        statement = (
            select(Generation)
            .where(Generation.task_id == task_id)
            .where(Generation.status == "accepted")
            .order_by(Generation.version_no.desc(), Generation.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_next_version_no(self, task_id: str) -> int:
        statement = select(func.coalesce(func.max(Generation.version_no), 0)).where(Generation.task_id == task_id)
        return int(self.session.scalar(statement) or 0) + 1

    def create(self, generation: Generation) -> Generation:
        self.session.add(generation)
        self.session.flush()
        return generation
