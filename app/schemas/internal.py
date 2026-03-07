from __future__ import annotations

from typing import Optional

from app.schemas.common import APIModel


class ManualReviewActionRequest(APIModel):
    operator: Optional[str] = None
    note: Optional[str] = None


class ManualReviewActionResponse(APIModel):
    task_id: str
    status: str
    generation_id: Optional[str] = None
    decision: str


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
