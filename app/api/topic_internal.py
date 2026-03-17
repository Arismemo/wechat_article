from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import verify_bearer_token
from app.db.session import get_db_session
from app.schemas.topic_intelligence import (
    TopicPlanPromoteRequest,
    TopicPlanPromoteResponse,
    TopicSourceEnqueueResponse,
    TopicSourceRunResponse,
)
from app.services.topic_fetch_queue_service import TopicFetchQueueService
from app.services.topic_intelligence_service import TopicIntelligenceService


router = APIRouter()


def _raise_internal_server_error(exc: Exception) -> None:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error.",
    ) from exc


@router.post(
    "/topic-sources/{source_id}/run",
    response_model=TopicSourceRunResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def run_topic_source(source_id: str, session: Session = Depends(get_db_session)) -> TopicSourceRunResponse:
    try:
        result = TopicIntelligenceService(session).run_source(source_id, trigger_type="manual-run")
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:
        _raise_internal_server_error(exc)
    return TopicSourceRunResponse(
        source_id=result.source_id,
        source_key=result.source_key,
        run_id=result.run_id,
        status=result.status,
        fetched_count=result.fetched_count,
        new_signal_count=result.new_signal_count,
        candidate_count=result.candidate_count,
        latest_plan_ids=result.latest_plan_ids,
    )


@router.post(
    "/topic-sources/{source_id}/enqueue",
    response_model=TopicSourceEnqueueResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def enqueue_topic_source(source_id: str, session: Session = Depends(get_db_session)) -> TopicSourceEnqueueResponse:
    service = TopicIntelligenceService(session)
    service.sync_registry()
    source = service.sources.get_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic source not found.")
    result = TopicFetchQueueService().enqueue(source_id)
    return TopicSourceEnqueueResponse(
        source_id=result.source_id,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post(
    "/topics/refresh-candidates",
    response_model=list[str],
    dependencies=[Depends(verify_bearer_token)],
)
def refresh_topic_candidates(session: Session = Depends(get_db_session)) -> list[str]:
    try:
        plan_ids = TopicIntelligenceService(session).refresh_candidates()
        session.commit()
    except Exception as exc:
        session.rollback()
        _raise_internal_server_error(exc)
    return plan_ids


@router.post(
    "/topics/plans/{plan_id}/promote",
    response_model=TopicPlanPromoteResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def promote_topic_plan_internal(
    plan_id: str,
    payload: TopicPlanPromoteRequest,
    session: Session = Depends(get_db_session),
) -> TopicPlanPromoteResponse:
    try:
        result = TopicIntelligenceService(session).promote_plan(
            plan_id,
            operator=payload.operator,
            note=payload.note,
            enqueue_phase3=payload.enqueue_phase3,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:
        _raise_internal_server_error(exc)
    return TopicPlanPromoteResponse(
        plan_id=result.plan_id,
        candidate_id=result.candidate_id,
        task_id=result.task_id,
        task_code=result.task_code,
        deduped=result.deduped,
        status=result.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )
