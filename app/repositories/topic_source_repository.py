from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.topic_source import TopicSource


class TopicSourceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, source_id: str) -> Optional[TopicSource]:
        return self.session.get(TopicSource, source_id)

    def get_by_source_key(self, source_key: str) -> Optional[TopicSource]:
        statement = select(TopicSource).where(TopicSource.source_key == source_key).limit(1)
        return self.session.scalar(statement)

    def list_all(self) -> list[TopicSource]:
        statement = select(TopicSource).order_by(TopicSource.source_key.asc())
        return list(self.session.scalars(statement))

    def list_enabled(self) -> list[TopicSource]:
        statement = (
            select(TopicSource)
            .where(TopicSource.enabled.is_(True))
            .order_by(TopicSource.source_key.asc())
        )
        return list(self.session.scalars(statement))

    def upsert(
        self,
        *,
        source_key: str,
        name: str,
        source_type: str,
        content_pillar: Optional[str],
        enabled: bool,
        fetch_interval_minutes: int,
        config: Any,
    ) -> TopicSource:
        source = self.get_by_source_key(source_key)
        if source is None:
            source = TopicSource(
                source_key=source_key,
                name=name,
                source_type=source_type,
                content_pillar=content_pillar,
                enabled=enabled,
                fetch_interval_minutes=fetch_interval_minutes,
                config=config,
            )
            self.session.add(source)
        else:
            source.name = name
            source.source_type = source_type
            source.content_pillar = content_pillar
            source.enabled = enabled
            source.fetch_interval_minutes = fetch_interval_minutes
            source.config = config
        self.session.flush()
        return source

    def update_runtime_state(
        self,
        source: TopicSource,
        *,
        last_fetched_at: Optional[datetime] = None,
        last_success_at: Optional[datetime] = None,
        last_error: Optional[str] = None,
    ) -> TopicSource:
        if last_fetched_at is not None:
            source.last_fetched_at = last_fetched_at
        if last_success_at is not None:
            source.last_success_at = last_success_at
        source.last_error = last_error
        self.session.flush()
        return source
