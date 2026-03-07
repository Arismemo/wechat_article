from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.content_brief import ContentBrief


class ContentBriefRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_latest_by_task_id(self, task_id: str) -> Optional[ContentBrief]:
        statement = (
            select(ContentBrief)
            .where(ContentBrief.task_id == task_id)
            .order_by(ContentBrief.brief_version.desc(), ContentBrief.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_next_brief_version(self, task_id: str) -> int:
        statement = select(func.coalesce(func.max(ContentBrief.brief_version), 0)).where(ContentBrief.task_id == task_id)
        return int(self.session.scalar(statement) or 0) + 1

    def delete_by_task_id(self, task_id: str) -> None:
        self.session.execute(delete(ContentBrief).where(ContentBrief.task_id == task_id))

    def create(self, brief: ContentBrief) -> ContentBrief:
        self.session.add(brief)
        self.session.flush()
        return brief
