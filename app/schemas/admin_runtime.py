from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import APIModel


class RuntimeEnvStatusResponse(APIModel):
    key: str
    label: str
    category: str
    configured: bool
    required: bool
    secret: bool
    preview: Optional[str] = None
    note: Optional[str] = None


class RuntimeAlertStatusResponse(APIModel):
    enabled: bool
    provider: str
    destination_preview: Optional[str] = None
    note: Optional[str] = None


class AdminRuntimeStatusResponse(APIModel):
    environment: list[RuntimeEnvStatusResponse] = Field(default_factory=list)
    alerts: RuntimeAlertStatusResponse


class AdminAlertTestRequest(APIModel):
    operator: Optional[str] = None
    note: Optional[str] = None


class AdminAlertTestResponse(APIModel):
    sent: bool
    provider: str
    destination_preview: Optional[str] = None
    sent_at: datetime
    note: Optional[str] = None
