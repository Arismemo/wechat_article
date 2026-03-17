from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Factor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """写作因子 —— 从优质文章中提取的原子化写作技法。"""

    __tablename__ = "factors"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    dimension: Mapped[str] = mapped_column(Text, nullable=False)  # opening/structure/rhetoric/rhythm/layout/closing
    technique: Mapped[str] = mapped_column(Text, nullable=False)  # 给 AI 的指令描述
    effect: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 给人读的效果说明
    example_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 示例片段（few-shot 用）
    anti_example: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 反面示例
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=list)  # 自由标签
    applicable_domains: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=list)  # 适用领域
    conflict_group: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 冲突组标识
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 来源文章链接
    source_type: Mapped[str] = mapped_column(Text, nullable=False, default="manual")  # ai_extracted / manual
    extract_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 被独立提取次数
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")  # pending/draft/active/deprecated/archived
    avg_effect_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 综合效果分
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 使用次数
