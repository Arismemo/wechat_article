from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TopicCandidateSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topic_candidate_signals"
    __table_args__ = (
        UniqueConstraint("candidate_id", "signal_id", name="uq_topic_candidate_signals_candidate_signal"),
    )

    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("topic_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal_id: Mapped[str] = mapped_column(
        ForeignKey("topic_signals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rank_no: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
