"""add phase3 research fields

Revision ID: 20260307_0003
Revises: 20260307_0002
Create Date: 2026-03-07 12:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260307_0003"
down_revision = "20260307_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("related_articles", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("related_articles", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("related_articles", sa.Column("snapshot_path", sa.Text(), nullable=True))
    op.add_column("content_briefs", sa.Column("difference_matrix", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("content_briefs", "difference_matrix")
    op.drop_column("related_articles", "snapshot_path")
    op.drop_column("related_articles", "published_at")
    op.drop_column("related_articles", "summary")
