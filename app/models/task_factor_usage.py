from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TaskFactorUsage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """任务使用因子的记录 —— 追踪哪些因子被用于哪个任务，以及效果反馈。"""

    __tablename__ = "task_factor_usages"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    factor_id: Mapped[str] = mapped_column(ForeignKey("factors.id", ondelete="CASCADE"), nullable=False, index=True)
    injected_via: Mapped[str] = mapped_column(Text, nullable=False, default="both")  # prompt / brief / both
    review_score_overall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_score_readability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_score_novelty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    human_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # good / neutral / bad
