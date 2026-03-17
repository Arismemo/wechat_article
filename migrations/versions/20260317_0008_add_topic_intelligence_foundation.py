"""add topic intelligence foundation tables

Revision ID: 20260317_0008
Revises: 20260316_0007
Create Date: 2026-03-17 09:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260317_0008"
down_revision = "20260316_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topic_sources",
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("content_pillar", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fetch_interval_minutes", sa.Integer(), nullable=False, server_default="240"),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", name="uq_topic_sources_source_key"),
    )

    op.create_table(
        "topic_fetch_runs",
        sa.Column("source_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("trigger_type", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_signal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["topic_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_topic_fetch_runs_source_id", "topic_fetch_runs", ["source_id"])

    op.create_table(
        "topic_signals",
        sa.Column("source_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("fetch_run_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("signal_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_site", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("source_tier", sa.Text(), nullable=True),
        sa.Column("fetch_status", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["fetch_run_id"], ["topic_fetch_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["topic_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_topic_signals_fetch_run_id", "topic_signals", ["fetch_run_id"])
    op.create_index("ix_topic_signals_normalized_url", "topic_signals", ["normalized_url"])
    op.create_index("ix_topic_signals_source_id", "topic_signals", ["source_id"])

    op.create_table(
        "topic_candidates",
        sa.Column("cluster_key", sa.Text(), nullable=False),
        sa.Column("topic_title", sa.Text(), nullable=False),
        sa.Column("topic_summary", sa.Text(), nullable=True),
        sa.Column("content_pillar", sa.Text(), nullable=True),
        sa.Column("hotness_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("commercial_fit_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("evidence_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("novelty_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("wechat_fit_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("risk_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("total_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("recommended_business_goal", sa.Text(), nullable=True),
        sa.Column("recommended_article_type", sa.Text(), nullable=True),
        sa.Column("canonical_seed_url", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="new"),
        sa.Column("signal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latest_signal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cluster_key", name="uq_topic_candidates_cluster_key"),
    )
    op.create_index("ix_topic_candidates_status", "topic_candidates", ["status"])

    op.create_table(
        "topic_candidate_signals",
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("signal_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("rank_no", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["topic_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signal_id"], ["topic_signals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "signal_id", name="uq_topic_candidate_signals_candidate_signal"),
    )
    op.create_index("ix_topic_candidate_signals_candidate_id", "topic_candidate_signals", ["candidate_id"])
    op.create_index("ix_topic_candidate_signals_signal_id", "topic_candidate_signals", ["signal_id"])

    op.create_table(
        "topic_plans",
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("business_goal", sa.Text(), nullable=True),
        sa.Column("article_type", sa.Text(), nullable=True),
        sa.Column("angle", sa.Text(), nullable=True),
        sa.Column("why_now", sa.Text(), nullable=True),
        sa.Column("target_reader", sa.Text(), nullable=True),
        sa.Column("must_cover", sa.JSON(), nullable=True),
        sa.Column("must_avoid", sa.JSON(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column("search_friendly_title", sa.Text(), nullable=True),
        sa.Column("distribution_friendly_title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("cta_mode", sa.Text(), nullable=True),
        sa.Column("source_grade", sa.Text(), nullable=True),
        sa.Column("recommended_queries", sa.JSON(), nullable=True),
        sa.Column("seed_source_pack", sa.JSON(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["topic_candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_topic_plans_candidate_id", "topic_plans", ["candidate_id"])

    op.create_table(
        "topic_plan_task_links",
        sa.Column("plan_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("operator", sa.Text(), nullable=False, server_default="system"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["topic_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "task_id", name="uq_topic_plan_task_links_plan_task"),
    )
    op.create_index("ix_topic_plan_task_links_plan_id", "topic_plan_task_links", ["plan_id"])
    op.create_index("ix_topic_plan_task_links_task_id", "topic_plan_task_links", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_topic_plan_task_links_task_id", table_name="topic_plan_task_links")
    op.drop_index("ix_topic_plan_task_links_plan_id", table_name="topic_plan_task_links")
    op.drop_table("topic_plan_task_links")
    op.drop_index("ix_topic_plans_candidate_id", table_name="topic_plans")
    op.drop_table("topic_plans")
    op.drop_index("ix_topic_candidate_signals_signal_id", table_name="topic_candidate_signals")
    op.drop_index("ix_topic_candidate_signals_candidate_id", table_name="topic_candidate_signals")
    op.drop_table("topic_candidate_signals")
    op.drop_index("ix_topic_candidates_status", table_name="topic_candidates")
    op.drop_table("topic_candidates")
    op.drop_index("ix_topic_signals_source_id", table_name="topic_signals")
    op.drop_index("ix_topic_signals_normalized_url", table_name="topic_signals")
    op.drop_index("ix_topic_signals_fetch_run_id", table_name="topic_signals")
    op.drop_table("topic_signals")
    op.drop_index("ix_topic_fetch_runs_source_id", table_name="topic_fetch_runs")
    op.drop_table("topic_fetch_runs")
    op.drop_table("topic_sources")
