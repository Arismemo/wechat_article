from __future__ import annotations

from typing import Optional

from app.schemas.common import APIModel


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
