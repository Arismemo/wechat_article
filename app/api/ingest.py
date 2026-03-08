import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import HttpUrl
from sqlalchemy.orm import Session

from app.core.security import verify_bearer_token
from app.db.session import get_db_session
from app.schemas.ingest import IngestDispatchMode, IngestLinkRequest, IngestLinkResponse
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


def _ingest_link_impl(payload: IngestLinkRequest, session: Session) -> IngestLinkResponse:
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


def _verify_shortcut_key(key: str) -> None:
    settings = get_settings()
    expected = settings.ingest_shortcut_shared_key or settings.api_bearer_token
    if not key or not secrets.compare_digest(key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid shortcut key.",
        )


@router.post("/ingest/link", response_model=IngestLinkResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_link(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> IngestLinkResponse:
    return _ingest_link_impl(payload, session)


@router.get("/ingest/shortcut", response_model=IngestLinkResponse)
def ingest_shortcut(
    url: HttpUrl,
    key: str = Query(..., min_length=1),
    source: str = Query(default="ios-shortcuts", max_length=64),
    device_id: Optional[str] = Query(default="iphone-shortcuts", max_length=128),
    trigger: Optional[str] = Query(default="back-tap", max_length=64),
    note: Optional[str] = Query(default=None, max_length=500),
    dispatch_mode: IngestDispatchMode = Query(default="auto"),
    session: Session = Depends(get_db_session),
) -> IngestLinkResponse:
    _verify_shortcut_key(key)
    payload = IngestLinkRequest(
        url=url,
        source=source,
        device_id=device_id,
        trigger=trigger,
        note=note,
        dispatch_mode=dispatch_mode,
    )
    return _ingest_link_impl(payload, session)
