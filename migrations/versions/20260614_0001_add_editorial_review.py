"""add editorial_reviews table

Revision ID: 20260614_0001
Revises: 20260317_0010
Create Date: 2026-06-14 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260614_0001"
down_revision = "20260317_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "editorial_reviews",
        sa.Column("id", UUID(as_uuid=False), nullable=False),
        sa.Column("task_id", UUID(as_uuid=False), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generation_id", UUID(as_uuid=False), sa.ForeignKey("generations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_report_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("rounds_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("final_scores", sa.JSON(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("revision_directives", sa.JSON(), nullable=True),
        sa.Column("dissent_summary", sa.Text(), nullable=True),
        sa.Column("transcript", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_editorial_reviews_task_id"), "editorial_reviews", ["task_id"], unique=False)
    op.create_index(op.f("ix_editorial_reviews_generation_id"), "editorial_reviews", ["generation_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_editorial_reviews_generation_id"), table_name="editorial_reviews")
    op.drop_index(op.f("ix_editorial_reviews_task_id"), table_name="editorial_reviews")
    op.drop_table("editorial_reviews")
