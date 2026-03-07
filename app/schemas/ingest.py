from __future__ import annotations

from typing import Optional

from pydantic import Field, HttpUrl

from app.schemas.common import APIModel


class IngestLinkRequest(APIModel):
    url: HttpUrl
    source: str = Field(default="ios-shortcuts", max_length=64)
    device_id: Optional[str] = Field(default=None, max_length=128)
    trigger: Optional[str] = Field(default=None, max_length=64)
    note: Optional[str] = Field(default=None, max_length=500)


class IngestLinkResponse(APIModel):
    task_id: str
    status: str
    deduped: bool
