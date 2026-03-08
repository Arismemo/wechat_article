from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.enums import ACTIVE_TASK_STATUSES
from app.models.task import Task


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, task_id: str) -> Optional[Task]:
        return self.session.get(Task, task_id)

    def get_active_by_normalized_url(self, normalized_url: str) -> Optional[Task]:
        statement = (
            select(Task)
            .where(Task.normalized_url == normalized_url)
            .where(Task.status.in_([status.value for status in ACTIVE_TASK_STATUSES]))
            .order_by(Task.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def list_recent(
        self,
        limit: int = 10,
        *,
        active_only: bool = False,
        status_filter: Optional[str] = None,
        source_type: Optional[str] = None,
        query: Optional[str] = None,
        created_after: Optional[datetime] = None,
    ) -> list[Task]:
        statement = select(Task)
        if active_only:
            statement = statement.where(Task.status.in_([status.value for status in ACTIVE_TASK_STATUSES]))
        if status_filter:
            statement = statement.where(Task.status == status_filter)
        if source_type:
            statement = statement.where(Task.source_type == source_type)
        if query:
            pattern = f"%{query.strip()}%"
            statement = statement.where(
                or_(
                    Task.task_code.ilike(pattern),
                    Task.source_url.ilike(pattern),
                    Task.normalized_url.ilike(pattern),
                )
            )
        if created_after:
            statement = statement.where(Task.created_at >= created_after)
        statement = statement.order_by(Task.created_at.desc()).limit(limit)
        return list(self.session.scalars(statement))

    def create(self, task: Task) -> Task:
        self.session.add(task)
        self.session.flush()
        return task
