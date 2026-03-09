from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import APIModel


class TaskResponse(APIModel):
    task_id: str
    status: str
    progress: int
    title: Optional[str] = None
    wechat_media_id: Optional[str] = None
    wechat_draft_url: Optional[str] = None
    wechat_draft_url_direct: bool = False
    wechat_draft_url_hint: Optional[str] = None
    brief_id: Optional[str] = None
    generation_id: Optional[str] = None
    related_article_count: int = 0
    error: Optional[str] = None


class TaskSummaryResponse(APIModel):
    task_id: str
    task_code: str
    source_url: str
    source_type: Optional[str] = None
    status: str
    progress: int
    title: Optional[str] = None
    wechat_media_id: Optional[str] = None
    wechat_draft_url: Optional[str] = None
    wechat_draft_url_direct: bool = False
    wechat_draft_url_hint: Optional[str] = None
    brief_id: Optional[str] = None
    generation_id: Optional[str] = None
    related_article_count: int = 0
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ArticleAnalysisResponse(APIModel):
    analysis_id: str
    theme: Optional[str] = None
    audience: Optional[str] = None
    angle: Optional[str] = None
    tone: Optional[str] = None
    key_points: Optional[dict] = None
    facts: Optional[dict] = None
    hooks: Optional[dict] = None
    risks: Optional[dict] = None
    gaps: Optional[dict] = None
    structure: Optional[dict] = None


class RelatedArticleResponse(APIModel):
    article_id: str
    query_text: str
    rank_no: int
    url: str
    title: Optional[str] = None
    source_site: Optional[str] = None
    summary: Optional[str] = None
    published_at: Optional[datetime] = None
    popularity_score: Optional[float] = None
    relevance_score: Optional[float] = None
    diversity_score: Optional[float] = None
    factual_density_score: Optional[float] = None
    snapshot_path: Optional[str] = None
    fetch_status: Optional[str] = None
    selected: bool


class ContentBriefResponse(APIModel):
    brief_id: str
    brief_version: int
    positioning: Optional[str] = None
    new_angle: Optional[str] = None
    target_reader: Optional[str] = None
    must_cover: Optional[dict] = None
    must_avoid: Optional[dict] = None
    difference_matrix: Optional[dict] = None
    outline: Optional[dict] = None
    title_directions: Optional[dict] = None


class TaskBriefResponse(APIModel):
    task_id: str
    status: str
    analysis: Optional[ArticleAnalysisResponse] = None
    brief: Optional[ContentBriefResponse] = None
    related_articles: list[RelatedArticleResponse]


class GenerationResponse(APIModel):
    generation_id: str
    version_no: int
    prompt_type: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: str
    title: Optional[str] = None
    subtitle: Optional[str] = None
    digest: Optional[str] = None
    markdown_content: Optional[str] = None
    html_content: Optional[str] = None
    score_overall: Optional[float] = None
    score_title: Optional[float] = None
    score_readability: Optional[float] = None
    score_novelty: Optional[float] = None
    score_risk: Optional[float] = None
    status: str


class ReviewRewriteTargetResponse(APIModel):
    block_id: str
    reason: str
    instruction: str


class ReviewReportResponse(APIModel):
    review_report_id: str
    similarity_score: Optional[float] = None
    factual_risk_score: Optional[float] = None
    policy_risk_score: Optional[float] = None
    readability_score: Optional[float] = None
    title_score: Optional[float] = None
    novelty_score: Optional[float] = None
    issues: Optional[dict] = None
    suggestions: Optional[dict] = None
    final_decision: Optional[str] = None
    ai_trace_score: Optional[float] = None
    ai_trace_patterns: list[str] = Field(default_factory=list)
    rewrite_targets: list[ReviewRewriteTargetResponse] = Field(default_factory=list)
    voice_summary: Optional[str] = None
    humanize_applied: bool = False
    humanize_block_ids: list[str] = Field(default_factory=list)


class GenerationAiTraceDiagnosisResponse(APIModel):
    state: str
    triggered: bool = False
    applied: bool = False
    threshold_score: float
    ai_trace_score: Optional[float] = None
    rewrite_target_count: int = 0
    rewrite_target_block_ids: list[str] = Field(default_factory=list)
    policy_risk_score: Optional[float] = None
    policy_risk_max: float
    factual_risk_score: Optional[float] = None
    factual_risk_max: float
    reason_codes: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    last_event_action: Optional[str] = None
    last_event_at: Optional[datetime] = None
    rewritten_block_ids: list[str] = Field(default_factory=list)


class TaskDraftResponse(APIModel):
    task_id: str
    status: str
    generation: Optional[GenerationResponse] = None
    review: Optional[ReviewReportResponse] = None


class SourceArticleDetailResponse(APIModel):
    source_article_id: str
    url: str
    title: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    cover_image_url: Optional[str] = None
    summary: Optional[str] = None
    cleaned_text_excerpt: Optional[str] = None
    snapshot_path: Optional[str] = None
    fetch_status: Optional[str] = None
    word_count: Optional[int] = None
    created_at: datetime


class AuditLogResponse(APIModel):
    audit_log_id: str
    action: str
    operator: str
    payload: Optional[dict] = None
    created_at: datetime


class TaskTimelineEventResponse(APIModel):
    action: str
    stage: str
    status: str
    title: str
    summary: str
    created_at: datetime
    generation_id: Optional[str] = None
    review_report_id: Optional[str] = None
    payload: Optional[dict] = None


class WechatPushPolicyResponse(APIModel):
    mode: str
    can_push: bool
    note: Optional[str] = None
    operator: Optional[str] = None
    source_action: Optional[str] = None
    updated_at: Optional[datetime] = None


class GenerationWorkspaceResponse(GenerationResponse):
    created_at: datetime
    review: Optional[ReviewReportResponse] = None
    ai_trace_diagnosis: Optional[GenerationAiTraceDiagnosisResponse] = None
    is_selected: bool = False
    draft_saved: bool = False
    wechat_media_id: Optional[str] = None


class SelectedGenerationResponse(APIModel):
    generation_id: str
    version_no: int
    title: Optional[str] = None
    status: str
    decision: Optional[str] = None
    source: str
    source_action: Optional[str] = None
    operator: Optional[str] = None
    note: Optional[str] = None
    selected_at: Optional[datetime] = None


class TaskWorkspaceResponse(APIModel):
    task_id: str
    task_code: str
    source_url: str
    source_type: Optional[str] = None
    status: str
    progress: int
    title: Optional[str] = None
    wechat_media_id: Optional[str] = None
    wechat_draft_url: Optional[str] = None
    wechat_draft_url_direct: bool = False
    wechat_draft_url_hint: Optional[str] = None
    brief_id: Optional[str] = None
    generation_id: Optional[str] = None
    related_article_count: int = 0
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    wechat_push_policy: WechatPushPolicyResponse
    source_article: Optional[SourceArticleDetailResponse] = None
    analysis: Optional[ArticleAnalysisResponse] = None
    brief: Optional[ContentBriefResponse] = None
    related_articles: list[RelatedArticleResponse] = Field(default_factory=list)
    selected_generation: Optional[SelectedGenerationResponse] = None
    generations: list[GenerationWorkspaceResponse]
    timeline: list[TaskTimelineEventResponse] = Field(default_factory=list)
    audits: list[AuditLogResponse]
