from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, func, select
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

    def get_latest_by_task_ids(self, task_ids: list[str]) -> dict[str, SourceArticle]:
        if not task_ids:
            return {}

        ranked_articles = (
            select(
                SourceArticle.id.label("article_id"),
                SourceArticle.task_id.label("task_id"),
                func.row_number()
                .over(
                    partition_by=SourceArticle.task_id,
                    order_by=(SourceArticle.created_at.desc(), SourceArticle.id.desc()),
                )
                .label("row_no"),
            )
            .where(SourceArticle.task_id.in_(task_ids))
            .subquery()
        )
        statement = (
            select(SourceArticle)
            .join(ranked_articles, SourceArticle.id == ranked_articles.c.article_id)
            .where(ranked_articles.c.row_no == 1)
        )
        return {item.task_id: item for item in self.session.scalars(statement)}

    def create(self, article: SourceArticle) -> SourceArticle:
        self.session.add(article)
        self.session.flush()
        return article

    def delete_by_task_id(self, task_id: str) -> None:
        self.session.execute(delete(SourceArticle).where(SourceArticle.task_id == task_id))
