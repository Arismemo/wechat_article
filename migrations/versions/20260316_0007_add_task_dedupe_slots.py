"""add task dedupe slots

Revision ID: 20260316_0007
Revises: 20260308_0006
Create Date: 2026-03-16 20:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0007"
down_revision = "20260308_0006"
branch_labels = None
depends_on = None


ACTIVE_STATUSES = (
    "queued",
    "deduping",
    "fetching_source",
    "source_ready",
    "analyzing_source",
    "searching_related",
    "fetching_related",
    "building_brief",
    "brief_ready",
    "generating",
    "reviewing",
    "review_passed",
    "pushing_wechat_draft",
    "needs_manual_source",
    "needs_manual_review",
    "needs_regenerate",
)


def upgrade() -> None:
    op.create_table(
        "task_dedupe_slots",
        sa.Column("task_id", sa.UUID(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index(op.f("ix_task_dedupe_slots_normalized_url"), "task_dedupe_slots", ["normalized_url"], unique=True)

    active_status_sql = ", ".join(f"'{status}'" for status in ACTIVE_STATUSES)
    op.execute(
        sa.text(
            f"""
            INSERT INTO task_dedupe_slots (task_id, normalized_url, created_at, updated_at)
            SELECT ranked.task_id, ranked.normalized_url, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM (
                SELECT
                    tasks.id AS task_id,
                    tasks.normalized_url AS normalized_url,
                    ROW_NUMBER() OVER (
                        PARTITION BY tasks.normalized_url
                        ORDER BY tasks.updated_at DESC, tasks.created_at DESC, tasks.id DESC
                    ) AS row_no
                FROM tasks
                WHERE tasks.status IN ({active_status_sql})
            ) AS ranked
            WHERE ranked.row_no = 1
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_task_dedupe_slots_normalized_url"), table_name="task_dedupe_slots")
    op.drop_table("task_dedupe_slots")
