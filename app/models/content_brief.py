from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ContentBrief(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_briefs"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    brief_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    positioning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_reader: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    must_cover: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    must_avoid: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    difference_matrix: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    outline: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    title_directions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
