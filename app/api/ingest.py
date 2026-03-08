from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import verify_bearer_token
from app.db.session import get_db_session
from app.schemas.ingest import IngestLinkRequest, IngestLinkResponse
from app.services.phase4_queue_service import Phase4QueueService
from app.services.task_service import TaskService
from app.settings import get_settings

router = APIRouter()


SHORTCUT_SOURCES = {"ios-shortcuts", "ios-share-sheet"}


def _resolve_dispatch_mode(payload: IngestLinkRequest) -> str:
    if payload.dispatch_mode == "phase4_enqueue":
        return "phase4_enqueue"
    if payload.dispatch_mode == "ingest_only":
        return "ingest_only"
    settings = get_settings()
    if settings.ingest_shortcut_auto_enqueue_phase4 and payload.source.strip().lower() in SHORTCUT_SOURCES:
        return "phase4_enqueue"
    return "ingest_only"


@router.post("/ingest/link", response_model=IngestLinkResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_link(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> IngestLinkResponse:
    task_service = TaskService(session)
    task, deduped = task_service.ingest_link(payload)
    dispatch_mode = _resolve_dispatch_mode(payload)

    if dispatch_mode == "phase4_enqueue" and not deduped:
        task = task_service.mark_queued_for_phase4(task, reason="public-ingest")
        queue_result = Phase4QueueService().enqueue(task.id)
        return IngestLinkResponse(
            task_id=task.id,
            status=task.status,
            deduped=deduped,
            dispatch_mode=dispatch_mode,
            enqueued=queue_result.enqueued,
            queue_depth=queue_result.queue_depth,
        )

    return IngestLinkResponse(
        task_id=task.id,
        status=task.status,
        deduped=deduped,
        dispatch_mode=dispatch_mode,
        enqueued=False,
        queue_depth=None,
    )
