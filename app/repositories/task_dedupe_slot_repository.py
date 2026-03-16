from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.task_dedupe_slot import TaskDedupeSlot


class TaskDedupeSlotRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_task_id(self, task_id: str) -> Optional[TaskDedupeSlot]:
        return self.session.get(TaskDedupeSlot, task_id)

    def get_by_normalized_url(self, normalized_url: str) -> Optional[TaskDedupeSlot]:
        statement = (
            select(TaskDedupeSlot)
            .where(TaskDedupeSlot.normalized_url == normalized_url)
            .limit(1)
        )
        return self.session.scalar(statement)

    def create(self, slot: TaskDedupeSlot) -> TaskDedupeSlot:
        self.session.add(slot)
        self.session.flush()
        return slot

    def delete_by_task_id(self, task_id: str) -> None:
        self.session.execute(delete(TaskDedupeSlot).where(TaskDedupeSlot.task_id == task_id))
