from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ArticleAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "article_analysis"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    theme: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_points: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    facts: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    hooks: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    risks: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    gaps: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    structure: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
