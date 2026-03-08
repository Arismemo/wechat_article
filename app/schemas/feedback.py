from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.schemas.common import APIModel


class PublicationMetricResponse(APIModel):
    metric_id: str
    generation_id: str
    wechat_media_id: Optional[str] = None
    prompt_type: str
    prompt_version: str
    day_offset: int
    snapshot_at: datetime
    read_count: Optional[int] = None
    like_count: Optional[int] = None
    share_count: Optional[int] = None
    comment_count: Optional[int] = None
    click_rate: Optional[float] = None
    source_type: str
    imported_by: str
    notes: Optional[str] = None
    raw_payload: Optional[dict] = None
    created_at: datetime


class PromptExperimentResponse(APIModel):
    experiment_id: str
    prompt_type: str
    prompt_version: str
    day_offset: int
    sample_count: int
    avg_read_count: Optional[float] = None
    avg_like_count: Optional[float] = None
    avg_share_count: Optional[float] = None
    avg_comment_count: Optional[float] = None
    avg_click_rate: Optional[float] = None
    best_read_count: Optional[int] = None
    latest_metric_at: Optional[datetime] = None
    last_task_id: Optional[str] = None
    last_generation_id: Optional[str] = None
    updated_at: datetime


class StyleAssetResponse(APIModel):
    style_asset_id: str
    asset_type: str
    title: str
    content: str
    tags: list[str]
    status: str
    weight: float
    source_task_id: Optional[str] = None
    source_generation_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TaskFeedbackResponse(APIModel):
    task_id: str
    status: str
    metrics: list[PublicationMetricResponse]
