from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TopicPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topic_plans"

    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("topic_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    business_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    article_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    why_now: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_reader: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    must_cover: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    must_avoid: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    keywords: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    search_friendly_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    distribution_friendly_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cta_mode: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_grade: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_queries: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    seed_source_pack: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
