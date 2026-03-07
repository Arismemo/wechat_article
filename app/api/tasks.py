from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.core.progress import get_progress
from app.core.security import verify_bearer_token
from app.db.session import get_db_session
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.tasks import TaskSummaryResponse
from app.repositories.wechat_draft_repository import WechatDraftRepository
from app.schemas.tasks import TaskResponse
from app.services.task_service import TaskService

router = APIRouter()


@router.get("/tasks", response_model=list[TaskSummaryResponse], dependencies=[Depends(verify_bearer_token)])
def list_tasks(limit: int = Query(default=10, ge=1, le=50), session: Session = Depends(get_db_session)) -> list[TaskSummaryResponse]:
    items = TaskService(session).list_recent(limit)
    return [
        TaskSummaryResponse(
            task_id=item.task_id,
            task_code=item.task_code,
            source_url=item.source_url,
            source_type=item.source_type,
            status=item.status,
            progress=item.progress,
            title=item.title,
            wechat_media_id=item.wechat_media_id,
            error=item.error,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]


@router.get("/tasks/{task_id}", response_model=TaskResponse, dependencies=[Depends(verify_bearer_token)])
def get_task(task_id: str, session: Session = Depends(get_db_session)) -> TaskResponse:
    task = TaskRepository(session).get_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    source_article = SourceArticleRepository(session).get_latest_by_task_id(task_id)
    wechat_draft = WechatDraftRepository(session).get_latest_by_task_id(task_id)
    task_status = TaskStatus(task.status)
    error = task.error_message or task.error_code
    return TaskResponse(
        task_id=task.id,
        status=task.status,
        progress=get_progress(task_status),
        title=source_article.title if source_article else None,
        wechat_media_id=wechat_draft.media_id if wechat_draft else None,
        error=error,
    )
