from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol

import httpx
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.generation import Generation
from app.models.task import Task
from app.models.wechat_draft import WechatDraft
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.wechat_draft_repository import WechatDraftRepository
from app.services.feedback_queue_service import FeedbackQueueService, FeedbackSyncEnqueueResult
from app.services.feedback_service import FeedbackImportResult, FeedbackService
from app.settings import get_settings


class FeedbackSyncProviderError(RuntimeError):
    pass


@dataclass
class FeedbackMetricSnapshot:
    day_offset: int
    snapshot_at: datetime
    read_count: Optional[int] = None
    like_count: Optional[int] = None
    share_count: Optional[int] = None
    comment_count: Optional[int] = None
    click_rate: Optional[float] = None
    wechat_media_id: Optional[str] = None
    source_type: Optional[str] = None
    imported_by: Optional[str] = None
    notes: Optional[str] = None
    raw_payload: Optional[dict] = None


@dataclass
class FeedbackSyncRunResult:
    task_id: str
    status: str
    generation_id: str
    wechat_media_id: str
    provider: str
    requested_day_offsets: list[int]
    imported_count: int
    imported_day_offsets: list[int]
    skipped_day_offsets: list[int]
    results: list[FeedbackImportResult]


@dataclass
class FeedbackSyncBatchEnqueueResult:
    requested_count: int
    enqueued_count: int
    queue_depth: int
    task_ids: list[str]
    day_offsets: list[int]


class FeedbackMetricsProvider(Protocol):
    provider_name: str

    def load_snapshots(
        self,
        *,
        task: Task,
        generation: Generation,
        draft: WechatDraft,
        day_offsets: list[int],
    ) -> list[FeedbackMetricSnapshot]:
        ...


class MockFeedbackMetricsProvider:
    provider_name = "mock"

    def load_snapshots(
        self,
        *,
        task: Task,
        generation: Generation,
        draft: WechatDraft,
        day_offsets: list[int],
    ) -> list[FeedbackMetricSnapshot]:
        del task, generation
        base_seed = sum(ord(char) for char in (draft.media_id or draft.task_id))
        snapshot_at = datetime.now(timezone.utc)
        snapshots: list[FeedbackMetricSnapshot] = []
        for day_offset in day_offsets:
            read_count = 1200 + (base_seed % 400) + (day_offset * 333)
            like_count = max(int(read_count * 0.065), 1)
            share_count = max(int(read_count * 0.011), 1)
            comment_count = max(int(read_count * 0.003), 1)
            snapshots.append(
                FeedbackMetricSnapshot(
                    day_offset=day_offset,
                    snapshot_at=snapshot_at,
                    read_count=read_count,
                    like_count=like_count,
                    share_count=share_count,
                    comment_count=comment_count,
                    click_rate=round(min(0.12 + (day_offset * 0.018), 0.95), 4),
                    wechat_media_id=draft.media_id,
                    source_type="auto:mock",
                    imported_by="feedback-sync-mock",
                    notes="Mock feedback sync snapshot",
                    raw_payload={
                        "provider": self.provider_name,
                        "wechat_media_id": draft.media_id,
                        "day_offset": day_offset,
                    },
                )
            )
        return snapshots


class HttpFeedbackMetricsProvider:
    provider_name = "http"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.endpoint = (self.settings.feedback_sync_http_url or "").strip()
        if not self.endpoint:
            raise ValueError("FEEDBACK_SYNC_HTTP_URL is required when FEEDBACK_SYNC_PROVIDER=http.")

    def load_snapshots(
        self,
        *,
        task: Task,
        generation: Generation,
        draft: WechatDraft,
        day_offsets: list[int],
    ) -> list[FeedbackMetricSnapshot]:
        headers = {"Content-Type": "application/json"}
        if self.settings.feedback_sync_api_key:
            headers["Authorization"] = f"Bearer {self.settings.feedback_sync_api_key}"
        response = httpx.post(
            self.endpoint,
            headers=headers,
            json={
                "task_id": task.id,
                "task_status": task.status,
                "task_source_url": task.source_url,
                "generation_id": generation.id,
                "generation_version": generation.version_no,
                "prompt_type": generation.prompt_type,
                "prompt_version": generation.prompt_version,
                "wechat_media_id": draft.media_id,
                "draft_created_at": draft.created_at.isoformat(),
                "day_offsets": day_offsets,
            },
            timeout=self.settings.feedback_sync_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        provider_name, items = self._extract_items(payload)

        snapshots: dict[int, FeedbackMetricSnapshot] = {}
        for item in items:
            if not isinstance(item, dict):
                raise FeedbackSyncProviderError(f"Unsupported feedback sync item: {item}")
            day_offset = self._parse_day_offset(item.get("day_offset"))
            if day_offset not in day_offsets:
                continue
            snapshots[day_offset] = FeedbackMetricSnapshot(
                day_offset=day_offset,
                snapshot_at=self._parse_snapshot_at(item.get("snapshot_at")),
                read_count=self._parse_optional_int(item.get("read_count"), field_name="read_count"),
                like_count=self._parse_optional_int(item.get("like_count"), field_name="like_count"),
                share_count=self._parse_optional_int(item.get("share_count"), field_name="share_count"),
                comment_count=self._parse_optional_int(item.get("comment_count"), field_name="comment_count"),
                click_rate=self._parse_optional_float(item.get("click_rate"), field_name="click_rate"),
                wechat_media_id=self._normalize_optional_text(item.get("wechat_media_id")) or draft.media_id,
                source_type=self._normalize_optional_text(item.get("source_type")) or f"auto:{provider_name}",
                imported_by=self._normalize_optional_text(item.get("imported_by")) or "feedback-sync",
                notes=self._normalize_optional_text(item.get("notes")),
                raw_payload=item,
            )
        return [snapshots[key] for key in sorted(snapshots)]

    def _extract_items(self, payload: object) -> tuple[str, list[dict]]:
        if isinstance(payload, list):
            return self.provider_name, payload
        if not isinstance(payload, dict):
            raise FeedbackSyncProviderError(f"Unsupported feedback sync response payload: {payload}")
        for key in ("snapshots", "metrics", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                provider_name = self._normalize_optional_text(payload.get("provider")) or self.provider_name
                return provider_name, value
        raise FeedbackSyncProviderError(f"Unsupported feedback sync response payload: {payload}")

    def _parse_day_offset(self, value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise FeedbackSyncProviderError("Feedback snapshot day_offset must be an integer.") from exc
        if parsed < 0:
            raise FeedbackSyncProviderError("Feedback snapshot day_offset must be >= 0.")
        return parsed

    def _parse_snapshot_at(self, value: object) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        text = str(value).strip()
        if not text:
            return datetime.now(timezone.utc)
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise FeedbackSyncProviderError("Feedback snapshot snapshot_at must be ISO datetime.") from exc
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _parse_optional_int(self, value: object, *, field_name: str) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise FeedbackSyncProviderError(f"Feedback snapshot {field_name} must be an integer.") from exc
        if parsed < 0:
            raise FeedbackSyncProviderError(f"Feedback snapshot {field_name} must be >= 0.")
        return parsed

    def _parse_optional_float(self, value: object, *, field_name: str) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise FeedbackSyncProviderError(f"Feedback snapshot {field_name} must be a number.") from exc
        if parsed < 0:
            raise FeedbackSyncProviderError(f"Feedback snapshot {field_name} must be >= 0.")
        return parsed

    def _normalize_optional_text(self, value: object) -> Optional[str]:
        normalized = str(value or "").strip()
        return normalized or None


class FeedbackSyncService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.tasks = TaskRepository(session)
        self.generations = GenerationRepository(session)
        self.wechat_drafts = WechatDraftRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.feedback = FeedbackService(session)
        self.queue = FeedbackQueueService()

    def run(
        self,
        task_id: str,
        *,
        day_offsets: Optional[list[int]] = None,
        operator: Optional[str] = None,
    ) -> FeedbackSyncRunResult:
        task = self._require_task(task_id)
        generation = self._resolve_generation(task.id)
        draft = self._resolve_draft(task.id, generation.id)
        requested_day_offsets = self._normalize_day_offsets(day_offsets)
        normalized_operator = self._normalize_operator(operator)
        provider = self._provider()

        try:
            snapshots = provider.load_snapshots(
                task=task,
                generation=generation,
                draft=draft,
                day_offsets=requested_day_offsets,
            )
            imported_results: list[FeedbackImportResult] = []
            imported_day_offsets: list[int] = []
            for snapshot in snapshots:
                result = self.feedback.import_publication_metric(
                    task.id,
                    generation_id=generation.id,
                    day_offset=snapshot.day_offset,
                    snapshot_at=snapshot.snapshot_at,
                    wechat_media_id=snapshot.wechat_media_id or draft.media_id,
                    read_count=snapshot.read_count,
                    like_count=snapshot.like_count,
                    share_count=snapshot.share_count,
                    comment_count=snapshot.comment_count,
                    click_rate=snapshot.click_rate,
                    source_type=snapshot.source_type or f"auto:{provider.provider_name}",
                    imported_by=snapshot.imported_by or normalized_operator,
                    notes=snapshot.notes,
                    raw_payload=snapshot.raw_payload,
                    operator=normalized_operator,
                    commit=False,
                )
                imported_results.append(result)
                imported_day_offsets.append(snapshot.day_offset)
            skipped_day_offsets = [value for value in requested_day_offsets if value not in set(imported_day_offsets)]
            self._log_action(
                task.id,
                action="phase6.feedback.sync.completed",
                operator=normalized_operator,
                payload={
                    "generation_id": generation.id,
                    "provider": provider.provider_name,
                    "wechat_media_id": draft.media_id,
                    "requested_day_offsets": requested_day_offsets,
                    "imported_day_offsets": imported_day_offsets,
                    "imported_count": len(imported_results),
                },
            )
            self.session.commit()
            return FeedbackSyncRunResult(
                task_id=task.id,
                status=task.status,
                generation_id=generation.id,
                wechat_media_id=draft.media_id or "",
                provider=provider.provider_name,
                requested_day_offsets=requested_day_offsets,
                imported_count=len(imported_results),
                imported_day_offsets=imported_day_offsets,
                skipped_day_offsets=skipped_day_offsets,
                results=imported_results,
            )
        except Exception as exc:
            self.session.rollback()
            self._log_action(
                task.id,
                action="phase6.feedback.sync.failed",
                operator=normalized_operator,
                payload={
                    "generation_id": generation.id,
                    "provider": provider.provider_name,
                    "wechat_media_id": draft.media_id,
                    "requested_day_offsets": requested_day_offsets,
                    "error": str(exc),
                },
            )
            self.session.commit()
            raise

    def enqueue(
        self,
        task_id: str,
        *,
        day_offsets: Optional[list[int]] = None,
        operator: Optional[str] = None,
    ) -> FeedbackSyncEnqueueResult:
        task = self._require_task(task_id)
        generation = self._resolve_generation(task.id)
        draft = self._resolve_draft(task.id, generation.id)
        requested_day_offsets = self._normalize_day_offsets(day_offsets)
        normalized_operator = self._normalize_operator(operator)
        self._provider()
        result = self.queue.enqueue(task.id, day_offsets=requested_day_offsets, operator=normalized_operator)
        self._log_action(
            task.id,
            action="phase6.feedback.sync.enqueued",
            operator=normalized_operator,
            payload={
                "generation_id": generation.id,
                "wechat_media_id": draft.media_id,
                "day_offsets": requested_day_offsets,
                "enqueued": result.enqueued,
                "queue_depth": result.queue_depth,
            },
        )
        self.session.commit()
        return result

    def enqueue_recent(
        self,
        *,
        limit: Optional[int] = None,
        day_offsets: Optional[list[int]] = None,
        operator: Optional[str] = None,
    ) -> FeedbackSyncBatchEnqueueResult:
        requested_limit = max(limit or self.settings.feedback_sync_recent_limit, 1)
        requested_day_offsets = self._normalize_day_offsets(day_offsets)
        normalized_operator = self._normalize_operator(operator)
        self._provider()

        task_ids: list[str] = []
        enqueued_count = 0
        seen_task_ids: set[str] = set()
        drafts = self.wechat_drafts.list_recent_successful(limit=max(requested_limit * 5, requested_limit))
        queue_depth = 0
        for draft in drafts:
            if draft.task_id in seen_task_ids:
                continue
            seen_task_ids.add(draft.task_id)
            task_ids.append(draft.task_id)
            result = self.queue.enqueue(draft.task_id, day_offsets=requested_day_offsets, operator=normalized_operator)
            queue_depth = result.queue_depth
            if result.enqueued:
                enqueued_count += 1
            self._log_action(
                draft.task_id,
                action="phase6.feedback.sync.enqueued",
                operator=normalized_operator,
                payload={
                    "generation_id": draft.generation_id,
                    "wechat_media_id": draft.media_id,
                    "day_offsets": requested_day_offsets,
                    "enqueued": result.enqueued,
                    "queue_depth": result.queue_depth,
                    "source": "recent-drafts-scan",
                },
            )
            if len(task_ids) >= requested_limit:
                break

        self.session.commit()
        return FeedbackSyncBatchEnqueueResult(
            requested_count=len(task_ids),
            enqueued_count=enqueued_count,
            queue_depth=queue_depth,
            task_ids=task_ids,
            day_offsets=requested_day_offsets,
        )

    def _provider(self) -> FeedbackMetricsProvider:
        provider_name = (self.settings.feedback_sync_provider or "").strip().lower()
        if provider_name in {"", "disabled", "none", "off"}:
            raise ValueError("FEEDBACK_SYNC_PROVIDER is disabled.")
        if provider_name == "mock":
            return MockFeedbackMetricsProvider()
        if provider_name == "http":
            return HttpFeedbackMetricsProvider()
        raise ValueError(f"Unsupported FEEDBACK_SYNC_PROVIDER: {self.settings.feedback_sync_provider}")

    def _require_task(self, task_id: str) -> Task:
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")
        return task

    def _resolve_generation(self, task_id: str) -> Generation:
        generation = self.generations.get_latest_accepted_by_task_id(task_id) or self.generations.get_latest_by_task_id(task_id)
        if generation is None:
            raise ValueError("Generation not found for task.")
        return generation

    def _resolve_draft(self, task_id: str, generation_id: str) -> WechatDraft:
        draft = self.wechat_drafts.get_latest_by_generation_id(generation_id) or self.wechat_drafts.get_latest_by_task_id(task_id)
        if draft is None or draft.push_status != "success" or not draft.media_id:
            raise ValueError("Successful wechat draft not found for task.")
        return draft

    def _normalize_day_offsets(self, day_offsets: Optional[list[int]]) -> list[int]:
        values = day_offsets or self._parse_day_offsets_setting()
        normalized = sorted({int(value) for value in values if int(value) >= 0})
        if not normalized:
            raise ValueError("day_offsets must contain at least one non-negative integer.")
        return normalized

    def _parse_day_offsets_setting(self) -> list[int]:
        parsed: list[int] = []
        for item in (self.settings.feedback_sync_day_offsets or "").split(","):
            normalized = item.strip()
            if not normalized:
                continue
            try:
                value = int(normalized)
            except ValueError as exc:
                raise ValueError("FEEDBACK_SYNC_DAY_OFFSETS must be a comma-separated integer list.") from exc
            if value < 0:
                raise ValueError("FEEDBACK_SYNC_DAY_OFFSETS must contain non-negative integers.")
            parsed.append(value)
        return parsed or [1, 3, 7]

    def _normalize_operator(self, operator: Optional[str]) -> str:
        return (operator or "").strip() or "feedback-sync"

    def _log_action(self, task_id: str, *, action: str, operator: str, payload: Optional[dict]) -> None:
        self.audit_logs.create(
            AuditLog(
                task_id=task_id,
                action=action,
                operator=operator,
                payload=payload,
            )
        )
