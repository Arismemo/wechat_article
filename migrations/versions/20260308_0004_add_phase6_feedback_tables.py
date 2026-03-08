"""add phase6 feedback tables

Revision ID: 20260308_0004
Revises: 20260307_0003
Create Date: 2026-03-08 10:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260308_0004"
down_revision = "20260307_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "publication_metrics",
        sa.Column("task_id", sa.UUID(as_uuid=False), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generation_id", sa.UUID(as_uuid=False), sa.ForeignKey("generations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("wechat_media_id", sa.Text(), nullable=True),
        sa.Column("prompt_type", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("day_offset", sa.Integer(), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_count", sa.Integer(), nullable=True),
        sa.Column("like_count", sa.Integer(), nullable=True),
        sa.Column("share_count", sa.Integer(), nullable=True),
        sa.Column("comment_count", sa.Integer(), nullable=True),
        sa.Column("click_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("imported_by", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generation_id", "day_offset", name="uq_publication_metrics_generation_day_offset"),
    )
    op.create_index(op.f("ix_publication_metrics_task_id"), "publication_metrics", ["task_id"], unique=False)
    op.create_index(op.f("ix_publication_metrics_generation_id"), "publication_metrics", ["generation_id"], unique=False)

    op.create_table(
        "prompt_experiments",
        sa.Column("prompt_type", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("day_offset", sa.Integer(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("avg_read_count", sa.Numeric(12, 4), nullable=True),
        sa.Column("avg_like_count", sa.Numeric(12, 4), nullable=True),
        sa.Column("avg_share_count", sa.Numeric(12, 4), nullable=True),
        sa.Column("avg_comment_count", sa.Numeric(12, 4), nullable=True),
        sa.Column("avg_click_rate", sa.Numeric(12, 4), nullable=True),
        sa.Column("best_read_count", sa.Integer(), nullable=True),
        sa.Column("latest_metric_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_task_id", sa.UUID(as_uuid=False), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "last_generation_id",
            sa.UUID(as_uuid=False),
            sa.ForeignKey("generations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prompt_type", "prompt_version", "day_offset", name="uq_prompt_experiments_prompt_day_offset"),
    )

    op.create_table(
        "style_assets",
        sa.Column("asset_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("weight", sa.Numeric(10, 4), nullable=False),
        sa.Column("source_task_id", sa.UUID(as_uuid=False), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "source_generation_id",
            sa.UUID(as_uuid=False),
            sa.ForeignKey("generations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_style_assets_asset_type"), "style_assets", ["asset_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_style_assets_asset_type"), table_name="style_assets")
    op.drop_table("style_assets")
    op.drop_table("prompt_experiments")
    op.drop_index(op.f("ix_publication_metrics_generation_id"), table_name="publication_metrics")
    op.drop_index(op.f("ix_publication_metrics_task_id"), table_name="publication_metrics")
    op.drop_table("publication_metrics")
