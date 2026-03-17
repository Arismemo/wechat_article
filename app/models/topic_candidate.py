from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TopicCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topic_candidates"
    __table_args__ = (UniqueConstraint("cluster_key", name="uq_topic_candidates_cluster_key"),)

    cluster_key: Mapped[str] = mapped_column(Text, nullable=False)
    topic_title: Mapped[str] = mapped_column(Text, nullable=False)
    topic_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_pillar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hotness_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    commercial_fit_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    evidence_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    novelty_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    wechat_fit_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    total_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    recommended_business_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_article_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    canonical_seed_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="new", index=True)
    signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_signal_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
