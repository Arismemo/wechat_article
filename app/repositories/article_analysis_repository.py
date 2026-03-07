from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.article_analysis import ArticleAnalysis


class ArticleAnalysisRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_latest_by_task_id(self, task_id: str) -> Optional[ArticleAnalysis]:
        statement = (
            select(ArticleAnalysis)
            .where(ArticleAnalysis.task_id == task_id)
            .order_by(ArticleAnalysis.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def delete_by_task_id(self, task_id: str) -> None:
        self.session.execute(delete(ArticleAnalysis).where(ArticleAnalysis.task_id == task_id))

    def create(self, analysis: ArticleAnalysis) -> ArticleAnalysis:
        self.session.add(analysis)
        self.session.flush()
        return analysis
