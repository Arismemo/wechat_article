from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.schemas.common import APIModel


class TaskResponse(APIModel):
    task_id: str
    status: str
    progress: int
    title: Optional[str] = None
    wechat_media_id: Optional[str] = None
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
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
