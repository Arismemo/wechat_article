from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class WechatDraft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wechat_drafts"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    generation_id: Mapped[str] = mapped_column(ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True)
    media_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    push_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    push_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
