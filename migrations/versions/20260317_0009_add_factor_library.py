"""add factor library tables

Revision ID: 20260317_0009
Revises: 20260317_0008
Create Date: 2026-03-17 10:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260317_0009"
down_revision = "20260317_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 因子表
    op.create_table(
        "factors",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("technique", sa.Text(), nullable=False),
        sa.Column("effect", sa.Text(), nullable=True),
        sa.Column("example_text", sa.Text(), nullable=True),
        sa.Column("anti_example", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("applicable_domains", sa.JSON(), nullable=True),
        sa.Column("conflict_group", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("extract_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("avg_effect_score", sa.Float(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 任务-因子使用关联表
    op.create_table(
        "task_factor_usages",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("task_id", sa.UUID(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("factor_id", sa.UUID(), sa.ForeignKey("factors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("injected_via", sa.Text(), nullable=False, server_default="both"),
        sa.Column("review_score_overall", sa.Float(), nullable=True),
        sa.Column("review_score_readability", sa.Float(), nullable=True),
        sa.Column("review_score_novelty", sa.Float(), nullable=True),
        sa.Column("human_feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_task_factor_usages_task_id", "task_factor_usages", ["task_id"])
    op.create_index("ix_task_factor_usages_factor_id", "task_factor_usages", ["factor_id"])


def downgrade() -> None:
    op.drop_index("ix_task_factor_usages_factor_id", table_name="task_factor_usages")
    op.drop_index("ix_task_factor_usages_task_id", table_name="task_factor_usages")
    op.drop_table("task_factor_usages")
    op.drop_table("factors")
