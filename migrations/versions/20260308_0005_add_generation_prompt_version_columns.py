"""add generation prompt version columns

Revision ID: 20260308_0005
Revises: 20260308_0004
Create Date: 2026-03-08 11:25:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260308_0005"
down_revision = "20260308_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generations", sa.Column("prompt_type", sa.Text(), nullable=True))
    op.add_column("generations", sa.Column("prompt_version", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "prompt_version")
    op.drop_column("generations", "prompt_type")
