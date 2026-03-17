from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.topic_signal import TopicSignal


class TopicSignalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, signal_id: str) -> Optional[TopicSignal]:
        return self.session.get(TopicSignal, signal_id)

    def list_recent(self, limit: int = 50) -> list[TopicSignal]:
        statement = select(TopicSignal).order_by(TopicSignal.discovered_at.desc(), TopicSignal.created_at.desc()).limit(limit)
        return list(self.session.scalars(statement))

    def list_by_source_id(self, source_id: str, limit: int = 50) -> list[TopicSignal]:
        statement = (
            select(TopicSignal)
            .where(TopicSignal.source_id == source_id)
            .order_by(TopicSignal.discovered_at.desc(), TopicSignal.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def get_latest_by_source_and_normalized_url(self, source_id: str, normalized_url: str) -> Optional[TopicSignal]:
        statement = (
            select(TopicSignal)
            .where(
                TopicSignal.source_id == source_id,
                TopicSignal.normalized_url == normalized_url,
            )
            .order_by(TopicSignal.discovered_at.desc(), TopicSignal.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def count_by_source_id(self, source_id: str) -> int:
        statement = select(func.count(TopicSignal.id)).where(TopicSignal.source_id == source_id)
        return int(self.session.scalar(statement) or 0)

    def create(self, signal: TopicSignal) -> TopicSignal:
        self.session.add(signal)
        self.session.flush()
        return signal
