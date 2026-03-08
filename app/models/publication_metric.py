from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PublicationMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "publication_metrics"
    __table_args__ = (
        UniqueConstraint("generation_id", "day_offset", name="uq_publication_metrics_generation_day_offset"),
    )

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    generation_id: Mapped[str] = mapped_column(ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True)
    wechat_media_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_type: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    day_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    like_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    share_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comment_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    click_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    source_type: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    imported_by: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
