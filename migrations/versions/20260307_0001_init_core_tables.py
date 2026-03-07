"""init core tables

Revision ID: 20260307_0001
Revises:
Create Date: 2026-03-07 09:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260307_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("task_code", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_code", name="uq_tasks_task_code"),
    )
    op.create_index("ix_tasks_normalized_url", "tasks", ["normalized_url"])

    op.create_table(
        "source_articles",
        sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("cleaned_text", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("snapshot_path", sa.Text(), nullable=True),
        sa.Column("fetch_status", sa.Text(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_articles_task_id", "source_articles", ["task_id"])

    op.create_table(
        "related_articles",
        sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("rank_no", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("source_site", sa.Text(), nullable=True),
        sa.Column("popularity_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("relevance_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("diversity_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("factual_density_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("cleaned_text", sa.Text(), nullable=True),
        sa.Column("fetch_status", sa.Text(), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_related_articles_task_id", "related_articles", ["task_id"])

    op.create_table(
        "article_analysis",
        sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("theme", sa.Text(), nullable=True),
        sa.Column("audience", sa.Text(), nullable=True),
        sa.Column("angle", sa.Text(), nullable=True),
        sa.Column("tone", sa.Text(), nullable=True),
        sa.Column("key_points", sa.JSON(), nullable=True),
        sa.Column("facts", sa.JSON(), nullable=True),
        sa.Column("hooks", sa.JSON(), nullable=True),
        sa.Column("risks", sa.JSON(), nullable=True),
        sa.Column("gaps", sa.JSON(), nullable=True),
        sa.Column("structure", sa.JSON(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_article_analysis_task_id", "article_analysis", ["task_id"])

    op.create_table(
        "content_briefs",
        sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brief_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("positioning", sa.Text(), nullable=True),
        sa.Column("new_angle", sa.Text(), nullable=True),
        sa.Column("target_reader", sa.Text(), nullable=True),
        sa.Column("must_cover", sa.JSON(), nullable=True),
        sa.Column("must_avoid", sa.JSON(), nullable=True),
        sa.Column("outline", sa.JSON(), nullable=True),
        sa.Column("title_directions", sa.JSON(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_briefs_task_id", "content_briefs", ["task_id"])

    op.create_table(
        "generations",
        sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brief_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("subtitle", sa.Text(), nullable=True),
        sa.Column("digest", sa.Text(), nullable=True),
        sa.Column("markdown_content", sa.Text(), nullable=True),
        sa.Column("html_content", sa.Text(), nullable=True),
        sa.Column("score_overall", sa.Numeric(10, 4), nullable=True),
        sa.Column("score_title", sa.Numeric(10, 4), nullable=True),
        sa.Column("score_readability", sa.Numeric(10, 4), nullable=True),
        sa.Column("score_novelty", sa.Numeric(10, 4), nullable=True),
        sa.Column("score_risk", sa.Numeric(10, 4), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="generated"),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["brief_id"], ["content_briefs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generations_task_id", "generations", ["task_id"])

    op.create_table(
        "review_reports",
        sa.Column("generation_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("similarity_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("factual_risk_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("policy_risk_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("readability_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("title_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("novelty_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("issues", sa.JSON(), nullable=True),
        sa.Column("suggestions", sa.JSON(), nullable=True),
        sa.Column("final_decision", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["generation_id"], ["generations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_reports_generation_id", "review_reports", ["generation_id"])

    op.create_table(
        "wechat_drafts",
        sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("media_id", sa.Text(), nullable=True),
        sa.Column("push_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("push_response", sa.JSON(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["generation_id"], ["generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wechat_drafts_task_id", "wechat_drafts", ["task_id"])
    op.create_index("ix_wechat_drafts_generation_id", "wechat_drafts", ["generation_id"])

    op.create_table(
        "prompt_versions",
        sa.Column("prompt_type", sa.Text(), nullable=False),
        sa.Column("version_name", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_template", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("operator", sa.Text(), nullable=False, server_default="system"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_task_id", "audit_logs", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_task_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("prompt_versions")
    op.drop_index("ix_wechat_drafts_generation_id", table_name="wechat_drafts")
    op.drop_index("ix_wechat_drafts_task_id", table_name="wechat_drafts")
    op.drop_table("wechat_drafts")
    op.drop_index("ix_review_reports_generation_id", table_name="review_reports")
    op.drop_table("review_reports")
    op.drop_index("ix_generations_task_id", table_name="generations")
    op.drop_table("generations")
    op.drop_index("ix_content_briefs_task_id", table_name="content_briefs")
    op.drop_table("content_briefs")
    op.drop_index("ix_article_analysis_task_id", table_name="article_analysis")
    op.drop_table("article_analysis")
    op.drop_index("ix_related_articles_task_id", table_name="related_articles")
    op.drop_table("related_articles")
    op.drop_index("ix_source_articles_task_id", table_name="source_articles")
    op.drop_table("source_articles")
    op.drop_index("ix_tasks_normalized_url", table_name="tasks")
    op.drop_table("tasks")
