"""Pipeline Registry API — 提供流程定义和配置 schema 给前端。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.pipeline_registry import ARTICLE_PIPELINE, serialize_pipeline
from app.core.security import verify_admin_api_auth

router = APIRouter()


@router.get(
    "/admin/pipeline/registry",
    dependencies=[Depends(verify_admin_api_auth)],
    tags=["admin-pipeline"],
)
def get_pipeline_registry() -> dict:
    """返回完整的 pipeline 定义，包括所有步骤和配置 schema。"""
    return serialize_pipeline(ARTICLE_PIPELINE)
