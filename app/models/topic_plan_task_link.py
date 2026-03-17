from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TopicPlanTaskLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topic_plan_task_links"
    __table_args__ = (UniqueConstraint("plan_id", "task_id", name="uq_topic_plan_task_links_plan_task"),)

    plan_id: Mapped[str] = mapped_column(ForeignKey("topic_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    operator: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
