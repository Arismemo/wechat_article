from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import verify_bearer_token
from app.db.session import get_db_session
from app.services.phase2_pipeline_service import Phase2PipelineService
from app.services.phase2_queue_service import Phase2QueueService
from app.services.task_service import TaskService
from app.schemas.ingest import IngestLinkRequest
from app.schemas.internal import Phase2EnqueueResponse, Phase2RunResponse

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
