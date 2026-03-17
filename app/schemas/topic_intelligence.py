from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import APIModel


class TopicSourceResponse(APIModel):
    source_id: str
    source_key: str
    name: str
    source_type: str
    content_pillar: Optional[str] = None
    enabled: bool
    fetch_interval_minutes: int
    config: dict = Field(default_factory=dict)
    signal_count: int = 0
    last_fetched_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None


class TopicCandidateSummaryResponse(APIModel):
    candidate_id: str
    cluster_key: str
    topic_title: str
    topic_summary: Optional[str] = None
    content_pillar: Optional[str] = None
    hotness_score: Optional[float] = None
    commercial_fit_score: Optional[float] = None
    evidence_score: Optional[float] = None
    novelty_score: Optional[float] = None
    wechat_fit_score: Optional[float] = None
    risk_score: Optional[float] = None
    total_score: Optional[float] = None
    recommended_business_goal: Optional[str] = None
    recommended_article_type: Optional[str] = None
    canonical_seed_url: Optional[str] = None
    status: str
    signal_count: int
    latest_signal_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TopicSignalResponse(APIModel):
    signal_id: str
    source_id: str
    signal_type: str
    title: str
    url: str
    normalized_url: Optional[str] = None
    summary: Optional[str] = None
    source_site: Optional[str] = None
    source_tier: Optional[str] = None
    published_at: Optional[datetime] = None
    discovered_at: datetime
    fetch_status: Optional[str] = None


class TopicPlanTaskLinkResponse(APIModel):
    link_id: str
    plan_id: str
    task_id: str
    operator: str
    note: Optional[str] = None
    created_at: datetime


class TopicPlanResponse(APIModel):
    plan_id: str
    candidate_id: str
    plan_version: int
    business_goal: Optional[str] = None
    article_type: Optional[str] = None
    angle: Optional[str] = None
    why_now: Optional[str] = None
    target_reader: Optional[str] = None
    must_cover: Optional[dict] = None
    must_avoid: Optional[dict] = None
    keywords: Optional[dict] = None
    search_friendly_title: Optional[str] = None
    distribution_friendly_title: Optional[str] = None
    summary: Optional[str] = None
    cta_mode: Optional[str] = None
    source_grade: Optional[str] = None
    recommended_queries: Optional[dict] = None
    seed_source_pack: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class TopicWorkspaceResponse(APIModel):
    candidate: TopicCandidateSummaryResponse
    plan: TopicPlanResponse
    signals: list[TopicSignalResponse] = Field(default_factory=list)
    task_links: list[TopicPlanTaskLinkResponse] = Field(default_factory=list)


class TopicSnapshotSummaryResponse(APIModel):
    source_total: int
    source_enabled: int
    candidate_total: int
    planned_total: int
    promoted_total: int
    ignored_total: int
    new_signal_24h: int
    generated_at: datetime
    status_counts: dict[str, int] = Field(default_factory=dict)


class TopicSnapshotResponse(APIModel):
    summary: TopicSnapshotSummaryResponse
    sources: list[TopicSourceResponse] = Field(default_factory=list)
    candidates: list[TopicCandidateSummaryResponse] = Field(default_factory=list)
    workspace: Optional[TopicWorkspaceResponse] = None


class TopicSourceRunResponse(APIModel):
    source_id: str
    source_key: str
    run_id: str
    status: str
    fetched_count: int
    new_signal_count: int
    candidate_count: int
    latest_plan_ids: list[str] = Field(default_factory=list)


class TopicSourceEnqueueResponse(APIModel):
    source_id: str
    enqueued: bool
    queue_depth: int


class TopicPlanPromoteRequest(APIModel):
    operator: Optional[str] = None
    note: Optional[str] = None
    enqueue_phase3: bool = True


class TopicPlanPromoteResponse(APIModel):
    plan_id: str
    candidate_id: str
    task_id: str
    task_code: str
    deduped: bool
    status: str
    enqueued: bool
    queue_depth: Optional[int] = None
