from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, JSON, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ReviewReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_reports"

    generation_id: Mapped[str] = mapped_column(ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True)
    similarity_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    factual_risk_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    policy_risk_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    readability_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    title_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    novelty_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    issues: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    suggestions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    final_decision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
