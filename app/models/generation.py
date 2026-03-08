from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Generation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generations"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    brief_id: Mapped[Optional[str]] = mapped_column(ForeignKey("content_briefs.id", ondelete="SET NULL"), nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    prompt_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subtitle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    digest: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    markdown_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    html_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score_overall: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    score_title: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    score_readability: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    score_novelty: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    score_risk: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="generated")
