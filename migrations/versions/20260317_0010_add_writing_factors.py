"""add writing_factors to content_briefs

Revision ID: 20260317_0010
Revises: 20260317_0009
Create Date: 2026-03-17 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260317_0010"
down_revision = "20260317_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_briefs", sa.Column("writing_factors", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("content_briefs", "writing_factors")
