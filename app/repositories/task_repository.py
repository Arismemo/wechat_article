from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Select, delete, distinct, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.enums import ACTIVE_TASK_STATUSES
from app.models.source_article import SourceArticle
from app.models.task import Task
from app.models.task_dedupe_slot import TaskDedupeSlot


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

    def count_grouped_by_status(
        self,
        *,
        active_only: bool = False,
        status_filter: Optional[str] = None,
        status_values: Optional[list[str]] = None,
        source_type: Optional[str] = None,
        query: Optional[str] = None,
        created_after: Optional[datetime] = None,
        updated_before: Optional[datetime] = None,
    ) -> dict[str, int]:
        statement = self._apply_filters(
            select(Task.status, func.count()).group_by(Task.status),
            active_only=active_only,
            status_filter=status_filter,
            status_values=status_values,
            source_type=source_type,
            query=query,
            created_after=created_after,
            updated_before=updated_before,
        )
        return {str(status): int(count) for status, count in self.session.execute(statement)}

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
        # 当 query 触发了 outerjoin SourceArticle，需要 distinct 防止重复
        if query:
            statement = statement.distinct()
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

    def list_created_since(
        self,
        *,
        created_after: datetime,
        active_only: bool = False,
        status_filter: Optional[str] = None,
        source_type: Optional[str] = None,
        query: Optional[str] = None,
    ) -> list[Task]:
        statement = self._apply_filters(
            select(Task),
            active_only=active_only,
            status_filter=status_filter,
            source_type=source_type,
            query=query,
            created_after=created_after,
        )
        statement = statement.order_by(Task.created_at.asc())
        return list(self.session.scalars(statement))

    def create(self, task: Task) -> Task:
        self.session.add(task)
        self.session.flush()
        return task

    def update_runtime_state(
        self,
        task: Task,
        *,
        status: str,
        error_code: Optional[str],
        error_message: Optional[str],
    ) -> None:
        self.session.execute(
            update(Task)
            .where(Task.id == task.id)
            .values(
                status=status,
                error_code=error_code,
                error_message=error_message,
                updated_at=func.now(),
            )
        )
        self.session.refresh(task)
        self._sync_dedupe_slot(task, status=status)

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
            # outerjoin SourceArticle 以支持按标题搜索（无源文的任务也保留）
            # 多条 source_article 命中时，由上层调用者负责 .distinct() 去重
            statement = statement.select_from(Task).outerjoin(
                SourceArticle,
                SourceArticle.task_id == Task.id,
            ).where(
                or_(
                    Task.task_code.ilike(pattern),
                    Task.source_url.ilike(pattern),
                    Task.normalized_url.ilike(pattern),
                    SourceArticle.title.ilike(pattern),
                )
            )
        if created_after:
            statement = statement.where(Task.created_at >= created_after)
        if updated_before:
            statement = statement.where(Task.updated_at <= updated_before)
        return statement

    def _sync_dedupe_slot(self, task: Task, *, status: str) -> None:
        active_status_values = {item.value for item in ACTIVE_TASK_STATUSES}
        if status in active_status_values:
            existing_slot = self.session.get(TaskDedupeSlot, task.id)
            if existing_slot is not None:
                if existing_slot.normalized_url != task.normalized_url:
                    existing_slot.normalized_url = task.normalized_url
                    self.session.flush()
                return

            conflicting_slot = self.session.scalar(
                select(TaskDedupeSlot)
                .where(TaskDedupeSlot.normalized_url == task.normalized_url)
                .limit(1)
            )
            if conflicting_slot is not None and conflicting_slot.task_id != task.id:
                # Keep pre-migration duplicate active tasks runnable. New ingest requests still
                # dedupe via the slot owner first and fall back to the tasks table if needed.
                return

            self.session.add(TaskDedupeSlot(task_id=task.id, normalized_url=task.normalized_url))
            self.session.flush()
            return

        self.session.execute(delete(TaskDedupeSlot).where(TaskDedupeSlot.task_id == task.id))
