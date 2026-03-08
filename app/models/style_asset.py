from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, JSON, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class StyleAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "style_assets"

    asset_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    weight: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=1.0)
    source_task_id: Mapped[Optional[str]] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    source_generation_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("generations.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
