from __future__ import annotations

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class TaskDedupeSlot(TimestampMixin, Base):
    __tablename__ = "task_dedupe_slots"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
