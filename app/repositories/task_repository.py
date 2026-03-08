from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Select, func, or_, select
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
        statement = self._apply_filters(
            select(Task),
            active_only=active_only,
            status_filter=status_filter,
            source_type=source_type,
            query=query,
            created_after=created_after,
        )
        statement = statement.order_by(Task.created_at.desc()).limit(limit)
        return list(self.session.scalars(statement))

    def count(
        self,
        *,
        active_only: bool = False,
        status_filter: Optional[str] = None,
        status_values: Optional[list[str]] = None,
        source_type: Optional[str] = None,
        query: Optional[str] = None,
        created_after: Optional[datetime] = None,
        updated_before: Optional[datetime] = None,
    ) -> int:
        statement = self._apply_filters(
            select(func.count()).select_from(Task),
            active_only=active_only,
            status_filter=status_filter,
            status_values=status_values,
            source_type=source_type,
            query=query,
            created_after=created_after,
            updated_before=updated_before,
        )
        return int(self.session.scalar(statement) or 0)

    def create(self, task: Task) -> Task:
        self.session.add(task)
        self.session.flush()
        return task

    def delete(self, task: Task) -> None:
        self.session.delete(task)

    def _apply_filters(
        self,
        statement: Select,
        *,
        active_only: bool = False,
        status_filter: Optional[str] = None,
        status_values: Optional[list[str]] = None,
        source_type: Optional[str] = None,
        query: Optional[str] = None,
        created_after: Optional[datetime] = None,
        updated_before: Optional[datetime] = None,
    ) -> Select:
        if active_only:
            statement = statement.where(Task.status.in_([status.value for status in ACTIVE_TASK_STATUSES]))
        if status_filter:
            statement = statement.where(Task.status == status_filter)
        if status_values:
            statement = statement.where(Task.status.in_(status_values))
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
        if updated_before:
            statement = statement.where(Task.updated_at <= updated_before)
        return statement
