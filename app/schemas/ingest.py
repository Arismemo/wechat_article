from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field, HttpUrl

from app.schemas.common import APIModel


IngestDispatchMode = Literal["auto", "ingest_only", "phase4_enqueue"]


class IngestLinkRequest(APIModel):
    url: HttpUrl
    source: str = Field(default="ios-shortcuts", max_length=64)
    device_id: Optional[str] = Field(default=None, max_length=128)
    trigger: Optional[str] = Field(default=None, max_length=64)
    note: Optional[str] = Field(default=None, max_length=500)
    dispatch_mode: IngestDispatchMode = Field(default="auto")


class IngestLinkResponse(APIModel):
    task_id: str
    status: str
    deduped: bool
    dispatch_mode: Literal["ingest_only", "phase4_enqueue"]
    enqueued: bool = False
    queue_depth: Optional[int] = None
