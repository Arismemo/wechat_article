from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.source_article import SourceArticle


class SourceArticleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_latest_by_task_id(self, task_id: str) -> Optional[SourceArticle]:
        statement = (
            select(SourceArticle)
            .where(SourceArticle.task_id == task_id)
            .order_by(SourceArticle.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def create(self, article: SourceArticle) -> SourceArticle:
        self.session.add(article)
        self.session.flush()
        return article

    def delete_by_task_id(self, task_id: str) -> None:
        self.session.execute(delete(SourceArticle).where(SourceArticle.task_id == task_id))
