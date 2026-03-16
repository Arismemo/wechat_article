from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.enums import ACTIVE_TASK_STATUSES, FINAL_FAILURE_STATUSES, TaskStatus
from app.db.redis_client import get_redis_client
from app.repositories.task_repository import TaskRepository
from app.schemas.admin_monitor import (
    AdminMonitorAlertResponse,
    AdminMonitorOperationsResponse,
    AdminMonitorSnapshotResponse,
    AdminMonitorSummaryResponse,
    AdminMonitorTrendPointResponse,
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
    _TREND_BUCKET_COUNT = 8
    _TREND_BUCKET_HOURS = 3

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
        summary = self._build_summary(filters, task_summaries)
        operations = self._build_operations()
        workspace = None
        if filters.selected_task_id:
            task = self.tasks.get_by_id(filters.selected_task_id)
            if task is not None:
                workspace = self.build_workspace(task.id)
        return AdminMonitorSnapshotResponse(
            summary=summary,
            tasks=task_summaries,
            operations=operations,
            alerts=self._build_alerts(summary, operations),
            trends=self._build_trends(filters),
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
        filtered_status_totals = self.tasks.count_grouped_by_status(
            active_only=filters.active_only,
            status_filter=filters.status_filter,
            source_type=filters.source_type,
            query=filters.query,
            created_after=filters.created_after,
        )
        today_status_totals = self.tasks.count_grouped_by_status(created_after=today_start)
        filtered_stuck = sum(
            self.tasks.count_grouped_by_status(
                status_values=active_statuses,
                source_type=filters.source_type,
                query=filters.query,
                created_after=filters.created_after,
                status_filter=filters.status_filter,
                updated_before=stuck_before,
            ).values()
        )

        today_submitted = sum(today_status_totals.values())
        today_draft_saved = sum(today_status_totals.get(status, 0) for status in [TaskStatus.DRAFT_SAVED.value])
        today_failed = sum(today_status_totals.get(status, 0) for status in failure_statuses)
        today_review_success = sum(today_status_totals.get(status, 0) for status in review_success_statuses)
        today_review_outcomes = sum(today_status_totals.get(status, 0) for status in review_outcome_statuses)

        return AdminMonitorSummaryResponse(
            filtered_total=sum(filtered_status_totals.values()),
            filtered_active=sum(filtered_status_totals.get(status, 0) for status in active_statuses),
            filtered_manual=sum(filtered_status_totals.get(status, 0) for status in manual_statuses),
            filtered_review_passed=filtered_status_totals.get(TaskStatus.REVIEW_PASSED.value, 0),
            filtered_draft_saved=filtered_status_totals.get(TaskStatus.DRAFT_SAVED.value, 0),
            filtered_failed=sum(filtered_status_totals.get(status, 0) for status in failure_statuses),
            filtered_stuck=filtered_stuck,
            today_submitted=today_submitted,
            today_draft_saved=today_draft_saved,
            today_failed=today_failed,
            today_review_success_rate=self._percentage(today_review_success, today_review_outcomes),
            today_auto_push_success_rate=self._percentage(
                today_draft_saved,
                sum(today_status_totals.get(status, 0) for status in [TaskStatus.REVIEW_PASSED.value, TaskStatus.DRAFT_SAVED.value]),
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

    def _build_alerts(
        self,
        summary: AdminMonitorSummaryResponse,
        operations: AdminMonitorOperationsResponse,
    ) -> list[AdminMonitorAlertResponse]:
        alerts: list[AdminMonitorAlertResponse] = []
        if not operations.available:
            alerts.append(
                AdminMonitorAlertResponse(
                    key="monitor.operations.unavailable",
                    dedupe_key="monitor.operations.unavailable",
                    level="critical",
                    title="Worker 观测不可用",
                    summary="当前无法读取队列与 worker 观测数据，先恢复监控基础链路。",
                    detail=operations.note,
                    count=1,
                    action_label="留在监控台",
                    action_href="/admin/console",
                )
            )
            return alerts

        abnormal_workers = [item for item in operations.workers if item.status in {"stale", "offline"}]
        if abnormal_workers:
            offline_count = sum(1 for item in abnormal_workers if item.status == "offline")
            detail = "；".join(
                f"{item.label}: {item.status} / queue={item.queue_depth} / processing={item.processing_depth}"
                for item in abnormal_workers
            )
            alerts.append(
                AdminMonitorAlertResponse(
                    key="monitor.workers.abnormal",
                    dedupe_key="monitor.workers.abnormal",
                    level="critical" if offline_count > 0 else "warn",
                    title="Worker 运行异常",
                    summary=f"{len(abnormal_workers)} 条队列观测异常，优先排查离线或堆积 worker。",
                    detail=detail,
                    count=len(abnormal_workers),
                    action_label="查看监控详情",
                    action_href="/admin/console",
                )
            )

        if summary.filtered_stuck > 0:
            alerts.append(
                AdminMonitorAlertResponse(
                    key="monitor.tasks.stuck",
                    dedupe_key="monitor.tasks.stuck",
                    level="critical" if summary.filtered_stuck >= 3 else "warn",
                    title="任务推进卡住",
                    summary=f"当前有 {summary.filtered_stuck} 条任务超过 {summary.stuck_threshold_minutes} 分钟未推进。",
                    detail="建议先在监控台定位对应状态组，再进任务详情看错误、审计轨迹和当前 generation。",
                    count=summary.filtered_stuck,
                    action_label="查看总览主控台",
                    action_href="/admin",
                )
            )

        if summary.filtered_failed > 0:
            alerts.append(
                AdminMonitorAlertResponse(
                    key="monitor.tasks.failed",
                    dedupe_key="monitor.tasks.failed",
                    level="critical" if summary.filtered_failed >= 3 else "warn",
                    title="失败任务需要恢复",
                    summary=f"当前筛选范围内有 {summary.filtered_failed} 条失败任务，今日累计失败 {summary.today_failed} 条。",
                    detail="先看失败任务详情和审计轨迹，再决定是重试、补数据还是转去 Phase 5 / Phase 6 收口。",
                    count=summary.filtered_failed,
                    action_label="查看总览主控台",
                    action_href="/admin",
                )
            )

        return alerts

    def _build_trends(self, filters: AdminMonitorFilters) -> list[AdminMonitorTrendPointResponse]:
        zone = self._timezone()
        bucket_span = timedelta(hours=self._TREND_BUCKET_HOURS)
        now_local = datetime.now(zone)
        aligned_hour = now_local.hour - (now_local.hour % self._TREND_BUCKET_HOURS)
        current_bucket_start_local = now_local.replace(
            hour=aligned_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        bucket_starts_local = [
            current_bucket_start_local - bucket_span * (self._TREND_BUCKET_COUNT - index - 1)
            for index in range(self._TREND_BUCKET_COUNT)
        ]
        points = [
            AdminMonitorTrendPointResponse(
                bucket_start=start_local.astimezone(timezone.utc),
                bucket_end=(start_local + bucket_span).astimezone(timezone.utc),
                label=start_local.strftime("%m-%d %H:%M"),
            )
            for start_local in bucket_starts_local
        ]
        if not points:
            return []

        records = self.tasks.list_created_since(
            created_after=points[0].bucket_start,
            active_only=filters.active_only,
            status_filter=filters.status_filter,
            source_type=filters.source_type,
            query=filters.query,
        )
        review_success_statuses = {TaskStatus.REVIEW_PASSED.value, TaskStatus.DRAFT_SAVED.value}
        review_outcome_statuses = review_success_statuses | {
            TaskStatus.NEEDS_REGENERATE.value,
            TaskStatus.NEEDS_MANUAL_REVIEW.value,
            TaskStatus.REVIEW_FAILED.value,
            TaskStatus.PUSH_FAILED.value,
        }
        failure_statuses = {item.value for item in FINAL_FAILURE_STATUSES}
        for task in records:
            created_at = task.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            for point in points:
                if point.bucket_start <= created_at < point.bucket_end:
                    point.submitted += 1
                    if task.status in review_outcome_statuses:
                        point.review_outcomes += 1
                    if task.status in review_success_statuses:
                        point.review_successes += 1
                    if task.status in {TaskStatus.REVIEW_PASSED.value, TaskStatus.DRAFT_SAVED.value}:
                        point.auto_push_candidates += 1
                    if task.status == TaskStatus.DRAFT_SAVED.value:
                        point.auto_push_successes += 1
                    if task.status in failure_statuses:
                        point.failed += 1
                    break

        for point in points:
            point.review_success_rate = self._percentage(point.review_successes, point.review_outcomes)
            point.auto_push_success_rate = self._percentage(point.auto_push_successes, point.auto_push_candidates)
        return points

    def _timezone(self) -> ZoneInfo:
        return ZoneInfo(self.settings.timezone or "Asia/Shanghai")

    def _start_of_today_utc(self) -> datetime:
        zone = self._timezone()
        now_local = datetime.now(zone)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_local.astimezone(timezone.utc)

    @classmethod
    def _stuck_threshold_delta(cls):
        return timedelta(minutes=cls._STUCK_THRESHOLD_MINUTES)

    @staticmethod
    def _percentage(numerator: int, denominator: int) -> Optional[float]:
        if denominator <= 0:
            return None
        return round((numerator / denominator) * 100, 1)
