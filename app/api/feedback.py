from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import verify_bearer_token
from app.db.session import get_db_session
from app.schemas.feedback import (
    PromptExperimentResponse,
    PublicationMetricResponse,
    StyleAssetResponse,
    TaskFeedbackResponse,
)
from app.services.feedback_service import FeedbackService
from app.services.task_service import TaskService


router = APIRouter()


@router.get("/tasks/{task_id}/feedback", response_model=TaskFeedbackResponse, dependencies=[Depends(verify_bearer_token)])
def get_task_feedback(task_id: str, session: Session = Depends(get_db_session)) -> TaskFeedbackResponse:
    task_service = TaskService(session)
    try:
        task = task_service.require_task(task_id)
        metrics = FeedbackService(session).list_task_metrics(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return TaskFeedbackResponse(
        task_id=task.id,
        status=task.status,
        metrics=[
            PublicationMetricResponse(
                metric_id=item.id,
                generation_id=item.generation_id,
                wechat_media_id=item.wechat_media_id,
                prompt_type=item.prompt_type,
                prompt_version=item.prompt_version,
                day_offset=item.day_offset,
                snapshot_at=item.snapshot_at,
                read_count=item.read_count,
                like_count=item.like_count,
                share_count=item.share_count,
                comment_count=item.comment_count,
                click_rate=float(item.click_rate) if item.click_rate is not None else None,
                source_type=item.source_type,
                imported_by=item.imported_by,
                notes=item.notes,
                raw_payload=item.raw_payload,
                created_at=item.created_at,
            )
            for item in metrics
        ],
    )


@router.get(
    "/feedback/experiments",
    response_model=list[PromptExperimentResponse],
    dependencies=[Depends(verify_bearer_token)],
)
def list_feedback_experiments(
    limit: int = Query(default=20, ge=1, le=100),
    prompt_type: Optional[str] = Query(default=None),
    day_offset: Optional[int] = Query(default=None, ge=0),
    session: Session = Depends(get_db_session),
) -> list[PromptExperimentResponse]:
    experiments = FeedbackService(session).list_experiments(limit=limit, prompt_type=prompt_type, day_offset=day_offset)
    return [
        PromptExperimentResponse(
            experiment_id=item.id,
            prompt_type=item.prompt_type,
            prompt_version=item.prompt_version,
            day_offset=item.day_offset,
            sample_count=item.sample_count,
            avg_read_count=float(item.avg_read_count) if item.avg_read_count is not None else None,
            avg_like_count=float(item.avg_like_count) if item.avg_like_count is not None else None,
            avg_share_count=float(item.avg_share_count) if item.avg_share_count is not None else None,
            avg_comment_count=float(item.avg_comment_count) if item.avg_comment_count is not None else None,
            avg_click_rate=float(item.avg_click_rate) if item.avg_click_rate is not None else None,
            best_read_count=item.best_read_count,
            latest_metric_at=item.latest_metric_at,
            last_task_id=item.last_task_id,
            last_generation_id=item.last_generation_id,
            updated_at=item.updated_at,
        )
        for item in experiments
    ]


@router.get(
    "/feedback/style-assets",
    response_model=list[StyleAssetResponse],
    dependencies=[Depends(verify_bearer_token)],
)
def list_style_assets(
    limit: int = Query(default=20, ge=1, le=100),
    asset_type: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: Session = Depends(get_db_session),
) -> list[StyleAssetResponse]:
    items = FeedbackService(session).list_style_assets(limit=limit, asset_type=asset_type, status=status_filter)
    return [
        StyleAssetResponse(
            style_asset_id=item.id,
            asset_type=item.asset_type,
            title=item.title,
            content=item.content,
            tags=item.tags or [],
            status=item.status,
            weight=float(item.weight),
            source_task_id=item.source_task_id,
            source_generation_id=item.source_generation_id,
            notes=item.notes,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]
