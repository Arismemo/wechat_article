"""add source article metadata

Revision ID: 20260307_0002
Revises: 20260307_0001
Create Date: 2026-03-07 16:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260307_0002"
down_revision = "20260307_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_articles", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("source_articles", sa.Column("cover_image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("source_articles", "cover_image_url")
    op.drop_column("source_articles", "published_at")
