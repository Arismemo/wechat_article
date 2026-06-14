from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class EditorialReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "editorial_reviews"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    generation_id: Mapped[str] = mapped_column(ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True)
    review_report_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")  # running|converged|max_rounds|failed
    rounds_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # pass|revise|reject
    final_scores: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revision_directives: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    dissent_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {rounds:[{round_no, opinions:[...]}]}
