from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.related_article import RelatedArticle


class RelatedArticleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_task_id(self, task_id: str) -> list[RelatedArticle]:
        statement = (
            select(RelatedArticle)
            .where(RelatedArticle.task_id == task_id)
            .order_by(RelatedArticle.selected.desc(), RelatedArticle.rank_no.asc(), RelatedArticle.created_at.asc())
        )
        return list(self.session.scalars(statement))

    def list_selected_by_task_id(self, task_id: str) -> list[RelatedArticle]:
        statement = (
            select(RelatedArticle)
            .where(RelatedArticle.task_id == task_id)
            .where(RelatedArticle.selected.is_(True))
            .order_by(RelatedArticle.rank_no.asc(), RelatedArticle.created_at.asc())
        )
        return list(self.session.scalars(statement))

    def count_by_task_id(self, task_id: str, *, selected_only: bool = False) -> int:
        statement = select(func.count()).select_from(RelatedArticle).where(RelatedArticle.task_id == task_id)
        if selected_only:
            statement = statement.where(RelatedArticle.selected.is_(True))
        return int(self.session.scalar(statement) or 0)

    def count_by_task_ids(self, task_ids: list[str], *, selected_only: bool = False) -> dict[str, int]:
        if not task_ids:
            return {}

        statement = select(RelatedArticle.task_id, func.count()).where(RelatedArticle.task_id.in_(task_ids))
        if selected_only:
            statement = statement.where(RelatedArticle.selected.is_(True))
        statement = statement.group_by(RelatedArticle.task_id)
        return {str(task_id): int(count) for task_id, count in self.session.execute(statement)}

    def get_latest_selected_by_url(self, task_id: str, url: str) -> Optional[RelatedArticle]:
        statement = (
            select(RelatedArticle)
            .where(RelatedArticle.task_id == task_id)
            .where(RelatedArticle.url == url)
            .where(RelatedArticle.selected.is_(True))
            .order_by(RelatedArticle.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def delete_by_task_id(self, task_id: str) -> None:
        self.session.execute(delete(RelatedArticle).where(RelatedArticle.task_id == task_id))

    def create(self, article: RelatedArticle) -> RelatedArticle:
        self.session.add(article)
        self.session.flush()
        return article
