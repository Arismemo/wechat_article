from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import APIModel


class AdminLLMProviderResponse(APIModel):
    provider_id: str
    vendor: str
    label: str
    api_base: str
    models: list[str] = Field(default_factory=list)
    has_api_key: bool
    api_key_preview: Optional[str] = None
    is_env_default: bool = False


class AdminLLMSelectionResponse(APIModel):
    active_provider_id: str
    analyze_model: str
    write_model: str
    review_model: str


class AdminLLMConfigResponse(APIModel):
    providers: list[AdminLLMProviderResponse] = Field(default_factory=list)
    selection: AdminLLMSelectionResponse


class AdminLLMProviderUpdate(APIModel):
    provider_id: str
    vendor: str
    label: str
    api_base: str
    models: list[str] = Field(default_factory=list)
    api_key: Optional[str] = None


class AdminLLMConfigUpdateRequest(APIModel):
    providers: list[AdminLLMProviderUpdate] = Field(default_factory=list)
    active_provider_id: str
    analyze_model: str
    write_model: str
    review_model: str
    operator: Optional[str] = None
    note: Optional[str] = None


class AdminLLMTestRequest(APIModel):
    provider_id: str
    model: Optional[str] = None
    operator: Optional[str] = None
    note: Optional[str] = None


class AdminLLMTestResponse(APIModel):
    success: bool
    provider_id: str
    provider_label: str
    model: str
    base_url_preview: Optional[str] = None
    response_payload: Optional[dict] = None
    error: Optional[str] = None
    tested_at: datetime
    latency_ms: int
