from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, func, select
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

    def get_latest_by_task_ids(self, task_ids: list[str]) -> dict[str, Generation]:
        if not task_ids:
            return {}

        ranked_generations = (
            select(
                Generation.id.label("generation_id"),
                Generation.task_id.label("task_id"),
                func.row_number()
                .over(
                    partition_by=Generation.task_id,
                    order_by=(
                        Generation.version_no.desc(),
                        Generation.created_at.desc(),
                        Generation.id.desc(),
                    ),
                )
                .label("row_no"),
            )
            .where(Generation.task_id.in_(task_ids))
            .subquery()
        )
        statement = (
            select(Generation)
            .join(ranked_generations, Generation.id == ranked_generations.c.generation_id)
            .where(ranked_generations.c.row_no == 1)
        )
        return {item.task_id: item for item in self.session.scalars(statement)}

    def get_latest_accepted_by_task_id(self, task_id: str) -> Optional[Generation]:
        statement = (
            select(Generation)
            .where(Generation.task_id == task_id)
            .where(Generation.status == "accepted")
            .order_by(Generation.version_no.desc(), Generation.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def list_by_task_id(self, task_id: str, limit: int = 10) -> list[Generation]:
        statement = (
            select(Generation)
            .where(Generation.task_id == task_id)
            .order_by(Generation.version_no.desc(), Generation.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def list_ids_by_task_id(self, task_id: str) -> list[str]:
        statement = select(Generation.id).where(Generation.task_id == task_id)
        return [str(item) for item in self.session.scalars(statement)]

    def get_next_version_no(self, task_id: str) -> int:
        statement = select(func.coalesce(func.max(Generation.version_no), 0)).where(Generation.task_id == task_id)
        return int(self.session.scalar(statement) or 0) + 1

    def create(self, generation: Generation) -> Generation:
        self.session.add(generation)
        self.session.flush()
        return generation

    def delete_by_task_id(self, task_id: str) -> None:
        self.session.execute(delete(Generation).where(Generation.task_id == task_id))
