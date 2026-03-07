from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import verify_bearer_token
from app.db.session import get_db_session
from app.services.manual_review_service import ManualReviewConflictError, ManualReviewService
from app.services.phase2_pipeline_service import Phase2PipelineService
from app.services.phase2_queue_service import Phase2QueueService
from app.services.phase3_pipeline_service import Phase3PipelineService
from app.services.phase3_queue_service import Phase3QueueService
from app.services.phase4_pipeline_service import Phase4PipelineService
from app.services.phase4_queue_service import Phase4QueueService
from app.services.task_service import TaskService
from app.services.wechat_draft_publish_service import WechatDraftPublishService
from app.schemas.ingest import IngestLinkRequest
from app.schemas.internal import (
    ManualReviewActionRequest,
    ManualReviewActionResponse,
    Phase2EnqueueResponse,
    Phase2RunResponse,
    Phase3EnqueueResponse,
    Phase3RunResponse,
    Phase4EnqueueResponse,
    Phase4RunResponse,
    WechatPushResponse,
)

router = APIRouter()


@router.post("/tasks/{task_id}/run-phase2", response_model=Phase2RunResponse, dependencies=[Depends(verify_bearer_token)])
def run_phase2(task_id: str, session: Session = Depends(get_db_session)) -> Phase2RunResponse:
    try:
        result = Phase2PipelineService(session).run(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return Phase2RunResponse(
        task_id=result.task_id,
        status=result.status,
        source_title=result.source_title,
        generation_id=result.generation_id,
        wechat_media_id=result.wechat_media_id,
        snapshot_path=result.snapshot_path,
    )


@router.post("/tasks/{task_id}/enqueue-phase2", response_model=Phase2EnqueueResponse, dependencies=[Depends(verify_bearer_token)])
def enqueue_phase2(task_id: str, session: Session = Depends(get_db_session)) -> Phase2EnqueueResponse:
    task_service = TaskService(session)
    try:
        task = task_service.require_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    task = task_service.mark_queued_for_phase2(task, reason="manual-enqueue")
    result = Phase2QueueService().enqueue(task.id)
    return Phase2EnqueueResponse(
        task_id=task.id,
        status=task.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post("/phase2/ingest-and-run", response_model=Phase2RunResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_and_run_phase2(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> Phase2RunResponse:
    task, _ = TaskService(session).ingest_link(payload)
    try:
        result = Phase2PipelineService(session).run(task.id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return Phase2RunResponse(
        task_id=result.task_id,
        status=result.status,
        source_title=result.source_title,
        generation_id=result.generation_id,
        wechat_media_id=result.wechat_media_id,
        snapshot_path=result.snapshot_path,
    )


@router.post("/phase2/ingest-and-enqueue", response_model=Phase2EnqueueResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_and_enqueue_phase2(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> Phase2EnqueueResponse:
    task_service = TaskService(session)
    task, _ = task_service.ingest_link(payload)
    task = task_service.mark_queued_for_phase2(task, reason="ingest-and-enqueue")
    result = Phase2QueueService().enqueue(task.id)
    return Phase2EnqueueResponse(
        task_id=task.id,
        status=task.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post("/tasks/{task_id}/run-phase3", response_model=Phase3RunResponse, dependencies=[Depends(verify_bearer_token)])
def run_phase3(task_id: str, session: Session = Depends(get_db_session)) -> Phase3RunResponse:
    try:
        result = Phase3PipelineService(session).run(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return Phase3RunResponse(
        task_id=result.task_id,
        status=result.status,
        analysis_id=result.analysis_id,
        brief_id=result.brief_id,
        related_count=result.related_count,
    )


@router.post("/tasks/{task_id}/enqueue-phase3", response_model=Phase3EnqueueResponse, dependencies=[Depends(verify_bearer_token)])
def enqueue_phase3(task_id: str, session: Session = Depends(get_db_session)) -> Phase3EnqueueResponse:
    task_service = TaskService(session)
    try:
        task = task_service.require_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    task = task_service.mark_queued_for_phase3(task, reason="manual-enqueue")
    result = Phase3QueueService().enqueue(task.id)
    return Phase3EnqueueResponse(
        task_id=task.id,
        status=task.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post("/phase3/ingest-and-run", response_model=Phase3RunResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_and_run_phase3(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> Phase3RunResponse:
    task, _ = TaskService(session).ingest_link(payload)
    try:
        result = Phase3PipelineService(session).run(task.id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return Phase3RunResponse(
        task_id=result.task_id,
        status=result.status,
        analysis_id=result.analysis_id,
        brief_id=result.brief_id,
        related_count=result.related_count,
    )


@router.post("/phase3/ingest-and-enqueue", response_model=Phase3EnqueueResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_and_enqueue_phase3(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> Phase3EnqueueResponse:
    task_service = TaskService(session)
    task, _ = task_service.ingest_link(payload)
    task = task_service.mark_queued_for_phase3(task, reason="ingest-and-enqueue")
    result = Phase3QueueService().enqueue(task.id)
    return Phase3EnqueueResponse(
        task_id=task.id,
        status=task.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post("/tasks/{task_id}/run-phase4", response_model=Phase4RunResponse, dependencies=[Depends(verify_bearer_token)])
def run_phase4(task_id: str, session: Session = Depends(get_db_session)) -> Phase4RunResponse:
    try:
        result = Phase4PipelineService(session).run(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return Phase4RunResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        review_report_id=result.review_report_id,
        decision=result.decision,
        auto_revised=result.auto_revised,
    )


@router.post("/tasks/{task_id}/enqueue-phase4", response_model=Phase4EnqueueResponse, dependencies=[Depends(verify_bearer_token)])
def enqueue_phase4(task_id: str, session: Session = Depends(get_db_session)) -> Phase4EnqueueResponse:
    task_service = TaskService(session)
    try:
        task = task_service.require_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    task = task_service.mark_queued_for_phase4(task, reason="manual-enqueue")
    result = Phase4QueueService().enqueue(task.id)
    return Phase4EnqueueResponse(
        task_id=task.id,
        status=task.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post("/phase4/ingest-and-run", response_model=Phase4RunResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_and_run_phase4(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> Phase4RunResponse:
    task, _ = TaskService(session).ingest_link(payload)
    try:
        result = Phase4PipelineService(session).run(task.id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return Phase4RunResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        review_report_id=result.review_report_id,
        decision=result.decision,
        auto_revised=result.auto_revised,
    )


@router.post("/phase4/ingest-and-enqueue", response_model=Phase4EnqueueResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_and_enqueue_phase4(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> Phase4EnqueueResponse:
    task_service = TaskService(session)
    task, _ = task_service.ingest_link(payload)
    task = task_service.mark_queued_for_phase4(task, reason="ingest-and-enqueue")
    result = Phase4QueueService().enqueue(task.id)
    return Phase4EnqueueResponse(
        task_id=task.id,
        status=task.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post(
    "/tasks/{task_id}/approve-latest-generation",
    response_model=ManualReviewActionResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def approve_latest_generation(
    task_id: str,
    payload: Optional[ManualReviewActionRequest] = None,
    session: Session = Depends(get_db_session),
) -> ManualReviewActionResponse:
    try:
        result = ManualReviewService(session).approve_latest_generation(
            task_id,
            operator=payload.operator if payload else None,
            note=payload.note if payload else None,
        )
    except ManualReviewConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return ManualReviewActionResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        decision=result.decision,
    )


@router.post(
    "/tasks/{task_id}/reject-latest-generation",
    response_model=ManualReviewActionResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def reject_latest_generation(
    task_id: str,
    payload: Optional[ManualReviewActionRequest] = None,
    session: Session = Depends(get_db_session),
) -> ManualReviewActionResponse:
    try:
        result = ManualReviewService(session).reject_latest_generation(
            task_id,
            operator=payload.operator if payload else None,
            note=payload.note if payload else None,
        )
    except ManualReviewConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return ManualReviewActionResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        decision=result.decision,
    )


@router.post("/tasks/{task_id}/push-wechat-draft", response_model=WechatPushResponse, dependencies=[Depends(verify_bearer_token)])
def push_wechat_draft(task_id: str, session: Session = Depends(get_db_session)) -> WechatPushResponse:
    try:
        result = WechatDraftPublishService(session).push_latest_accepted_generation(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return WechatPushResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        wechat_media_id=result.wechat_media_id,
        reused_existing=result.reused_existing,
    )
