from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import verify_bearer_token
from app.db.session import get_db_session
from app.schemas.admin_monitor import AdminMonitorSnapshotResponse
from app.services.admin_monitor_service import AdminMonitorFilters, AdminMonitorService


router = APIRouter()


@router.get(
    "/admin/monitor/snapshot",
    response_model=AdminMonitorSnapshotResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def get_admin_monitor_snapshot(
    limit: int = Query(default=36, ge=1, le=100),
    active_only: bool = Query(default=False),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    source_type: Optional[str] = Query(default=None, max_length=64),
    query: Optional[str] = Query(default=None, max_length=200),
    created_after: Optional[datetime] = Query(default=None),
    selected_task_id: Optional[str] = Query(default=None),
    session: Session = Depends(get_db_session),
) -> AdminMonitorSnapshotResponse:
    service = AdminMonitorService(session)
    try:
        return service.build_snapshot(
            AdminMonitorFilters(
                limit=limit,
                active_only=active_only,
                status_filter=status_filter,
                source_type=source_type,
                query=query,
                created_after=created_after,
                selected_task_id=selected_task_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
