from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TopicSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topic_sources"
    __table_args__ = (UniqueConstraint("source_key", name="uq_topic_sources_source_key"),)

    source_key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_pillar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=240)
    config: Mapped[Any] = mapped_column(JSON, nullable=False, default=dict)
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
