from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TopicFetchRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topic_fetch_runs"

    source_id: Mapped[str] = mapped_column(ForeignKey("topic_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
