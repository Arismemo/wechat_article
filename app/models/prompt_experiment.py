from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PromptExperiment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "prompt_experiments"
    __table_args__ = (
        UniqueConstraint("prompt_type", "prompt_version", "day_offset", name="uq_prompt_experiments_prompt_day_offset"),
    )

    prompt_type: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    day_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_read_count: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    avg_like_count: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    avg_share_count: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    avg_comment_count: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    avg_click_rate: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    best_read_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latest_metric_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_task_id: Mapped[Optional[str]] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    last_generation_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("generations.id", ondelete="SET NULL"),
        nullable=True,
    )
