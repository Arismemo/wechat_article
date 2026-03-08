from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import APIModel


class ManualReviewActionRequest(APIModel):
    operator: Optional[str] = None
    note: Optional[str] = None


class ManualReviewActionResponse(APIModel):
    task_id: str
    status: str
    generation_id: Optional[str] = None
    decision: str


class WechatPushPolicyActionRequest(APIModel):
    operator: Optional[str] = None
    note: Optional[str] = None


class WechatPushPolicyActionResponse(APIModel):
    task_id: str
    mode: str
    can_push: bool
    note: Optional[str] = None
    operator: str


class Phase2RunResponse(APIModel):
    task_id: str
    status: str
    source_title: Optional[str] = None
    generation_id: Optional[str] = None
    wechat_media_id: Optional[str] = None
    snapshot_path: Optional[str] = None


class Phase2EnqueueResponse(APIModel):
    task_id: str
    status: str
    enqueued: bool
    queue_depth: int


class Phase3RunResponse(APIModel):
    task_id: str
    status: str
    analysis_id: Optional[str] = None
    brief_id: Optional[str] = None
    related_count: int = 0


class Phase3EnqueueResponse(APIModel):
    task_id: str
    status: str
    enqueued: bool
    queue_depth: int


class Phase4RunResponse(APIModel):
    task_id: str
    status: str
    generation_id: Optional[str] = None
    review_report_id: Optional[str] = None
    decision: Optional[str] = None
    auto_revised: bool = False


class Phase4EnqueueResponse(APIModel):
    task_id: str
    status: str
    enqueued: bool
    queue_depth: int


class WechatPushResponse(APIModel):
    task_id: str
    status: str
    generation_id: Optional[str] = None
    wechat_media_id: Optional[str] = None
    reused_existing: bool = False


class FeedbackImportRequest(APIModel):
    generation_id: Optional[str] = None
    day_offset: int = Field(ge=0)
    snapshot_at: Optional[datetime] = None
    prompt_type: Optional[str] = None
    prompt_version: Optional[str] = None
    wechat_media_id: Optional[str] = None
    read_count: Optional[int] = Field(default=None, ge=0)
    like_count: Optional[int] = Field(default=None, ge=0)
    share_count: Optional[int] = Field(default=None, ge=0)
    comment_count: Optional[int] = Field(default=None, ge=0)
    click_rate: Optional[float] = Field(default=None, ge=0)
    source_type: Optional[str] = None
    imported_by: Optional[str] = None
    notes: Optional[str] = None
    raw_payload: Optional[dict] = None
    operator: Optional[str] = None


class FeedbackImportResponse(APIModel):
    task_id: str
    status: str
    generation_id: str
    metric_id: str
    prompt_type: str
    prompt_version: str
    day_offset: int
    sample_count: int


class FeedbackCsvImportRequest(APIModel):
    csv_text: str
    default_task_id: Optional[str] = None
    source_type: Optional[str] = None
    imported_by: Optional[str] = None
    operator: Optional[str] = None


class FeedbackCsvImportRowResponse(APIModel):
    row_no: int
    task_id: str
    status: str
    generation_id: str
    metric_id: str
    prompt_type: str
    prompt_version: str
    day_offset: int
    sample_count: int


class FeedbackCsvImportResponse(APIModel):
    imported_count: int
    results: list[FeedbackCsvImportRowResponse]


class StyleAssetCreateRequest(APIModel):
    asset_type: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    status: Optional[str] = None
    weight: Optional[float] = Field(default=None, gt=0)
    source_task_id: Optional[str] = None
    source_generation_id: Optional[str] = None
    notes: Optional[str] = None
    operator: Optional[str] = None


class StyleAssetCreateResponse(APIModel):
    style_asset_id: str
    asset_type: str
    title: str
    status: str
