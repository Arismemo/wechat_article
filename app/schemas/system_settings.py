from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import Field

from app.schemas.common import APIModel


class SystemSettingOptionResponse(APIModel):
    value: str
    label: str


class SystemSettingResponse(APIModel):
    key: str
    label: str
    description: str
    category: str
    value_type: str
    default_value: Any
    stored_value: Optional[Any] = None
    effective_value: Any
    has_override: bool
    options: list[SystemSettingOptionResponse] = Field(default_factory=list)
    requires_restart: bool = False
    updated_at: Optional[datetime] = None


class SystemSettingUpdateRequest(APIModel):
    value: Optional[Any] = None
    reset_to_default: bool = False
    operator: Optional[str] = None
    note: Optional[str] = None
