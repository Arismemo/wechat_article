from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.topic_fetch_run import TopicFetchRun


class TopicFetchRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, run_id: str) -> Optional[TopicFetchRun]:
        return self.session.get(TopicFetchRun, run_id)

    def list_recent_by_source_id(self, source_id: str, limit: int = 20) -> list[TopicFetchRun]:
        statement = (
            select(TopicFetchRun)
            .where(TopicFetchRun.source_id == source_id)
            .order_by(TopicFetchRun.started_at.desc(), TopicFetchRun.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def create(self, run: TopicFetchRun) -> TopicFetchRun:
        self.session.add(run)
        self.session.flush()
        return run

    def mark_finished(
        self,
        run: TopicFetchRun,
        *,
        status: str,
        finished_at: Optional[datetime],
        fetched_count: int,
        new_signal_count: int,
        error_message: Optional[str],
    ) -> TopicFetchRun:
        run.status = status
        run.finished_at = finished_at
        run.fetched_count = fetched_count
        run.new_signal_count = new_signal_count
        run.error_message = error_message
        self.session.flush()
        return run
