from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.enums import ACTIVE_TASK_STATUSES, FINAL_FAILURE_STATUSES, TaskStatus
from app.db.redis_client import get_redis_client
from app.repositories.task_repository import TaskRepository
from app.schemas.admin_monitor import (
    AdminMonitorOperationsResponse,
    AdminMonitorSnapshotResponse,
    AdminMonitorSummaryResponse,
    QueueWorkerStatusResponse,
)
from app.schemas.tasks import TaskSummaryResponse, TaskWorkspaceResponse
from app.services.feedback_queue_service import FeedbackQueueService
from app.services.phase2_queue_service import Phase2QueueService
from app.services.phase3_queue_service import Phase3QueueService
from app.services.phase4_queue_service import Phase4QueueService
from app.services.task_service import TaskService
from app.services.task_workspace_query_service import TaskWorkspaceQueryService
from app.settings import get_settings


@dataclass(frozen=True)
class AdminMonitorFilters:
    limit: int = 36
    active_only: bool = False
    status_filter: Optional[str] = None
    source_type: Optional[str] = None
    query: Optional[str] = None
    created_after: Optional[datetime] = None
    selected_task_id: Optional[str] = None


class AdminMonitorService:
    _STUCK_THRESHOLD_MINUTES = 30

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.tasks = TaskRepository(session)
        self.task_service = TaskService(session)
        self.workspace_query = TaskWorkspaceQueryService(session)

    def build_snapshot(self, filters: AdminMonitorFilters) -> AdminMonitorSnapshotResponse:
        task_rows = self.task_service.list_recent(
            filters.limit,
            active_only=filters.active_only,
            status_filter=filters.status_filter,
            source_type=filters.source_type,
            query=filters.query,
            created_after=filters.created_after,
        )
        task_summaries = [self._build_task_summary_response(item) for item in task_rows]
        workspace = None
        if filters.selected_task_id:
            task = self.tasks.get_by_id(filters.selected_task_id)
            if task is not None:
                workspace = self.build_workspace(task.id)
        return AdminMonitorSnapshotResponse(
            summary=self._build_summary(filters, task_summaries),
            tasks=task_summaries,
            operations=self._build_operations(),
            workspace=workspace,
        )

    def build_workspace(self, task_id: str) -> TaskWorkspaceResponse:
        return self.workspace_query.build_workspace(task_id)

    def _build_summary(
        self,
        filters: AdminMonitorFilters,
        task_summaries: list[TaskSummaryResponse],
    ) -> AdminMonitorSummaryResponse:
        today_start = self._start_of_today_utc()
        stuck_before = datetime.now(timezone.utc) - self._stuck_threshold_delta()
        status_counts: dict[str, int] = {}
        for item in task_summaries:
            status_counts[item.status] = status_counts.get(item.status, 0) + 1

        active_statuses = [item.value for item in ACTIVE_TASK_STATUSES]
        manual_statuses = [TaskStatus.NEEDS_MANUAL_REVIEW.value, TaskStatus.NEEDS_MANUAL_SOURCE.value, TaskStatus.NEEDS_REGENERATE.value]
        failure_statuses = [item.value for item in FINAL_FAILURE_STATUSES]
        review_success_statuses = [TaskStatus.REVIEW_PASSED.value, TaskStatus.DRAFT_SAVED.value]
        review_outcome_statuses = review_success_statuses + [
            TaskStatus.NEEDS_REGENERATE.value,
            TaskStatus.NEEDS_MANUAL_REVIEW.value,
            TaskStatus.REVIEW_FAILED.value,
            TaskStatus.PUSH_FAILED.value,
        ]
        today_submitted = self.tasks.count(created_after=today_start)
        today_draft_saved = self.tasks.count(
            status_values=[TaskStatus.DRAFT_SAVED.value],
            created_after=today_start,
        )
        today_failed = self.tasks.count(
            status_values=failure_statuses,
            created_after=today_start,
        )
        today_review_success = self.tasks.count(
            status_values=review_success_statuses,
            created_after=today_start,
        )
        today_review_outcomes = self.tasks.count(
            status_values=review_outcome_statuses,
            created_after=today_start,
        )

        return AdminMonitorSummaryResponse(
            filtered_total=self.tasks.count(
                active_only=filters.active_only,
                status_filter=filters.status_filter,
                source_type=filters.source_type,
                query=filters.query,
                created_after=filters.created_after,
            ),
            filtered_active=self.tasks.count(
                status_values=active_statuses,
                source_type=filters.source_type,
                query=filters.query,
                created_after=filters.created_after,
                status_filter=filters.status_filter,
            ),
            filtered_manual=self.tasks.count(
                status_values=manual_statuses,
                source_type=filters.source_type,
                query=filters.query,
                created_after=filters.created_after,
                status_filter=filters.status_filter,
            ),
            filtered_review_passed=self.tasks.count(
                status_values=[TaskStatus.REVIEW_PASSED.value],
                source_type=filters.source_type,
                query=filters.query,
                created_after=filters.created_after,
                status_filter=filters.status_filter,
            ),
            filtered_draft_saved=self.tasks.count(
                status_values=[TaskStatus.DRAFT_SAVED.value],
                source_type=filters.source_type,
                query=filters.query,
                created_after=filters.created_after,
                status_filter=filters.status_filter,
            ),
            filtered_failed=self.tasks.count(
                status_values=failure_statuses,
                source_type=filters.source_type,
                query=filters.query,
                created_after=filters.created_after,
                status_filter=filters.status_filter,
            ),
            filtered_stuck=self.tasks.count(
                status_values=active_statuses,
                source_type=filters.source_type,
                query=filters.query,
                created_after=filters.created_after,
                status_filter=filters.status_filter,
                updated_before=stuck_before,
            ),
            today_submitted=today_submitted,
            today_draft_saved=today_draft_saved,
            today_failed=today_failed,
            today_review_success_rate=self._percentage(today_review_success, today_review_outcomes),
            today_auto_push_success_rate=self._percentage(
                today_draft_saved,
                self.tasks.count(
                    status_values=[TaskStatus.REVIEW_PASSED.value, TaskStatus.DRAFT_SAVED.value],
                    created_after=today_start,
                ),
            ),
            stuck_threshold_minutes=self._STUCK_THRESHOLD_MINUTES,
            status_counts=status_counts,
            selected_task_id=filters.selected_task_id,
            generated_at=datetime.now(timezone.utc),
        )

    def _build_task_summary_response(self, item) -> TaskSummaryResponse:
        return TaskSummaryResponse(
            task_id=item.task_id,
            task_code=item.task_code,
            source_url=item.source_url,
            source_type=item.source_type,
            status=item.status,
            progress=item.progress,
            title=item.title,
            wechat_media_id=item.wechat_media_id,
            wechat_draft_url=item.wechat_draft_url,
            wechat_draft_url_direct=item.wechat_draft_url_direct,
            wechat_draft_url_hint=item.wechat_draft_url_hint,
            brief_id=item.brief_id,
            generation_id=item.generation_id,
            related_article_count=item.related_article_count,
            error=item.error,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def _build_operations(self) -> AdminMonitorOperationsResponse:
        try:
            redis_client = get_redis_client()
            workers = [
                Phase2QueueService(redis_client).runtime_snapshot(),
                Phase3QueueService(redis_client).runtime_snapshot(),
                Phase4QueueService(redis_client).runtime_snapshot(),
                FeedbackQueueService(redis_client).runtime_snapshot(),
            ]
            return AdminMonitorOperationsResponse(
                available=True,
                workers=[
                    QueueWorkerStatusResponse(
                        name=item.name,
                        label=item.label,
                        queue_depth=item.queue_depth,
                        processing_depth=item.processing_depth,
                        pending_count=item.pending_count,
                        last_seen_at=item.last_seen_at,
                        current_task_id=item.current_task_id,
                        healthy=item.healthy,
                        status=item.status,
                        stale_after_seconds=item.stale_after_seconds,
                    )
                    for item in workers
                ],
            )
        except Exception as exc:  # noqa: BLE001
            return AdminMonitorOperationsResponse(
                available=False,
                workers=[],
                note=f"worker observability unavailable: {exc}",
            )

    def _start_of_today_utc(self) -> datetime:
        timezone_name = self.settings.timezone or "Asia/Shanghai"
        zone = ZoneInfo(timezone_name)
        now_local = datetime.now(zone)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_local.astimezone(timezone.utc)

    @classmethod
    def _stuck_threshold_delta(cls):
        from datetime import timedelta

        return timedelta(minutes=cls._STUCK_THRESHOLD_MINUTES)

    @staticmethod
    def _percentage(numerator: int, denominator: int) -> Optional[float]:
        if denominator <= 0:
            return None
        return round((numerator / denominator) * 100, 1)
