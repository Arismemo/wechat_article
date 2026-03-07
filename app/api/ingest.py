from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import verify_bearer_token
from app.db.session import get_db_session
from app.schemas.ingest import IngestLinkRequest, IngestLinkResponse
from app.services.task_service import TaskService

router = APIRouter()


@router.post("/ingest/link", response_model=IngestLinkResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_link(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> IngestLinkResponse:
    task, deduped = TaskService(session).ingest_link(payload)
    return IngestLinkResponse(task_id=task.id, status=task.status, deduped=deduped)
