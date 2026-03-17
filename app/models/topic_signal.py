from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TopicSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topic_signals"

    source_id: Mapped[str] = mapped_column(ForeignKey("topic_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    fetch_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("topic_fetch_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    signal_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_site: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    raw_payload: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_tier: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fetch_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
