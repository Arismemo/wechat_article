from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import APIModel
from app.schemas.tasks import TaskSummaryResponse, TaskWorkspaceResponse


class AdminMonitorSummaryResponse(APIModel):
    filtered_total: int
    filtered_active: int
    filtered_manual: int
    filtered_review_passed: int
    filtered_draft_saved: int
    filtered_failed: int
    filtered_stuck: int
    today_submitted: int
    today_draft_saved: int
    today_failed: int
    today_review_success_rate: Optional[float] = None
    today_auto_push_success_rate: Optional[float] = None
    stuck_threshold_minutes: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    selected_task_id: Optional[str] = None
    generated_at: datetime


class QueueWorkerStatusResponse(APIModel):
    name: str
    label: str
    queue_depth: int
    processing_depth: int
    pending_count: int
    last_seen_at: Optional[datetime] = None
    current_task_id: Optional[str] = None
    healthy: bool
    status: str
    stale_after_seconds: int


class AdminMonitorOperationsResponse(APIModel):
    available: bool
    workers: list[QueueWorkerStatusResponse] = Field(default_factory=list)
    note: Optional[str] = None


class AdminMonitorSnapshotResponse(APIModel):
    summary: AdminMonitorSummaryResponse
    tasks: list[TaskSummaryResponse]
    operations: AdminMonitorOperationsResponse
    workspace: Optional[TaskWorkspaceResponse] = None
