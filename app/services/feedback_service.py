from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from statistics import fmean
from typing import Optional

from sqlalchemy.orm import Session

from app.core.prompt_versions import (
    DEFAULT_GENERATION_PROMPT_TYPE,
    resolve_generation_prompt_metadata,
)
from app.models.audit_log import AuditLog
from app.models.generation import Generation
from app.models.prompt_experiment import PromptExperiment
from app.models.publication_metric import PublicationMetric
from app.models.style_asset import StyleAsset
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.prompt_experiment_repository import PromptExperimentRepository
from app.repositories.publication_metric_repository import PublicationMetricRepository
from app.repositories.style_asset_repository import StyleAssetRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.wechat_draft_repository import WechatDraftRepository
from app.services.task_generation_selection_service import TaskGenerationSelectionService


@dataclass
class FeedbackImportResult:
    task_id: str
    status: str
    generation_id: str
    metric_id: str
    prompt_type: str
    prompt_version: str
    day_offset: int
    sample_count: int


@dataclass
class FeedbackBatchImportRowResult:
    row_no: int
    task_id: str
    status: str
    generation_id: str
    metric_id: str
    prompt_type: str
    prompt_version: str
    day_offset: int
    sample_count: int


@dataclass
class FeedbackBatchImportResult:
    imported_count: int
    results: list[FeedbackBatchImportRowResult]


@dataclass
class StyleAssetCreateResult:
    style_asset_id: str
    asset_type: str
    title: str
    status: str


class FeedbackService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.generations = GenerationRepository(session)
        self.metrics = PublicationMetricRepository(session)
        self.experiments = PromptExperimentRepository(session)
        self.style_assets = StyleAssetRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.wechat_drafts = WechatDraftRepository(session)
        self.selection = TaskGenerationSelectionService(session)

    def import_publication_metric(
        self,
        task_id: str,
        *,
        generation_id: Optional[str] = None,
        day_offset: int,
        snapshot_at: Optional[datetime] = None,
        prompt_type: Optional[str] = None,
        prompt_version: Optional[str] = None,
        wechat_media_id: Optional[str] = None,
        read_count: Optional[int] = None,
        like_count: Optional[int] = None,
        share_count: Optional[int] = None,
        comment_count: Optional[int] = None,
        click_rate: Optional[float] = None,
        source_type: Optional[str] = None,
        imported_by: Optional[str] = None,
        notes: Optional[str] = None,
        raw_payload: Optional[dict] = None,
        operator: Optional[str] = None,
        commit: bool = True,
    ) -> FeedbackImportResult:
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")

        generation = self._resolve_generation(task_id, generation_id)
        resolved_prompt_type, resolved_prompt_version = resolve_generation_prompt_metadata(
            generation.model_name,
            stored_prompt_type=generation.prompt_type,
            stored_prompt_version=generation.prompt_version,
        )
        normalized_prompt_type = (prompt_type or resolved_prompt_type or DEFAULT_GENERATION_PROMPT_TYPE).strip()
        normalized_prompt_version = (prompt_version or resolved_prompt_version or "unknown").strip()
        normalized_snapshot_at = snapshot_at or datetime.now(timezone.utc)
        normalized_source_type = (source_type or "manual").strip() or "manual"
        normalized_operator = (operator or "").strip() or "manual"
        normalized_imported_by = (imported_by or normalized_operator).strip() or "manual"
        normalized_notes = self._normalize_optional_text(notes)
        normalized_media_id = self._resolve_media_id(generation.id, wechat_media_id)

        metric = self.metrics.get_by_generation_id_and_day_offset(generation.id, day_offset)
        if metric is None:
            metric = self.metrics.create(
                PublicationMetric(
                    task_id=task.id,
                    generation_id=generation.id,
                    wechat_media_id=normalized_media_id,
                    prompt_type=normalized_prompt_type,
                    prompt_version=normalized_prompt_version,
                    day_offset=day_offset,
                    snapshot_at=normalized_snapshot_at,
                    read_count=read_count,
                    like_count=like_count,
                    share_count=share_count,
                    comment_count=comment_count,
                    click_rate=click_rate,
                    source_type=normalized_source_type,
                    imported_by=normalized_imported_by,
                    notes=normalized_notes,
                    raw_payload=raw_payload,
                )
            )
        else:
            metric.wechat_media_id = normalized_media_id
            metric.prompt_type = normalized_prompt_type
            metric.prompt_version = normalized_prompt_version
            metric.snapshot_at = normalized_snapshot_at
            metric.read_count = read_count
            metric.like_count = like_count
            metric.share_count = share_count
            metric.comment_count = comment_count
            metric.click_rate = click_rate
            metric.source_type = normalized_source_type
            metric.imported_by = normalized_imported_by
            metric.notes = normalized_notes
            metric.raw_payload = raw_payload

        experiment = self._refresh_prompt_experiment(
            normalized_prompt_type,
            normalized_prompt_version,
            day_offset,
        )
        self._log_action(
            task.id,
            action="phase6.feedback.imported",
            operator=normalized_operator,
            payload={
                "metric_id": metric.id,
                "generation_id": generation.id,
                "prompt_type": normalized_prompt_type,
                "prompt_version": normalized_prompt_version,
                "day_offset": day_offset,
                "read_count": read_count,
                "like_count": like_count,
                "share_count": share_count,
                "comment_count": comment_count,
                "click_rate": click_rate,
                "snapshot_at": normalized_snapshot_at.isoformat(),
            },
        )
        if commit:
            self.session.commit()
        return FeedbackImportResult(
            task_id=task.id,
            status=task.status,
            generation_id=generation.id,
            metric_id=metric.id,
            prompt_type=normalized_prompt_type,
            prompt_version=normalized_prompt_version,
            day_offset=day_offset,
            sample_count=experiment.sample_count,
        )

    def import_publication_metrics_csv(
        self,
        csv_text: str,
        *,
        default_task_id: Optional[str] = None,
        source_type: Optional[str] = None,
        imported_by: Optional[str] = None,
        operator: Optional[str] = None,
    ) -> FeedbackBatchImportResult:
        normalized_text = (csv_text or "").strip()
        if not normalized_text:
            raise ValueError("CSV content is empty.")

        normalized_default_task_id = self._normalize_optional_text(default_task_id)
        normalized_source_type = self._normalize_optional_text(source_type)
        normalized_imported_by = self._normalize_optional_text(imported_by)
        normalized_operator = self._normalize_optional_text(operator) or "manual"

        reader = csv.DictReader(StringIO(normalized_text))
        fieldnames = [field.strip() for field in (reader.fieldnames or []) if field and field.strip()]
        if not fieldnames:
            raise ValueError("CSV header is required.")
        if "day_offset" not in fieldnames:
            raise ValueError("CSV must include day_offset column.")
        if "task_id" not in fieldnames and not normalized_default_task_id:
            raise ValueError("CSV must include task_id column or provide default_task_id.")

        results: list[FeedbackBatchImportRowResult] = []
        try:
            for row_no, raw_row in enumerate(reader, start=2):
                row = {str(key).strip(): (value or "").strip() for key, value in raw_row.items() if key is not None}
                if not any(row.values()):
                    continue

                row_task_id = row.get("task_id") or normalized_default_task_id
                if not row_task_id:
                    raise ValueError(f"Row {row_no}: task_id is required.")

                result = self.import_publication_metric(
                    row_task_id,
                    generation_id=self._normalize_optional_text(row.get("generation_id")),
                    day_offset=self._parse_int_field(row.get("day_offset"), field_name="day_offset", row_no=row_no),
                    snapshot_at=self._parse_datetime_field(row.get("snapshot_at"), row_no=row_no),
                    prompt_type=self._normalize_optional_text(row.get("prompt_type")),
                    prompt_version=self._normalize_optional_text(row.get("prompt_version")),
                    wechat_media_id=self._normalize_optional_text(row.get("wechat_media_id")),
                    read_count=self._parse_optional_int_field(row.get("read_count"), field_name="read_count", row_no=row_no),
                    like_count=self._parse_optional_int_field(row.get("like_count"), field_name="like_count", row_no=row_no),
                    share_count=self._parse_optional_int_field(
                        row.get("share_count"),
                        field_name="share_count",
                        row_no=row_no,
                    ),
                    comment_count=self._parse_optional_int_field(
                        row.get("comment_count"),
                        field_name="comment_count",
                        row_no=row_no,
                    ),
                    click_rate=self._parse_optional_float_field(
                        row.get("click_rate"),
                        field_name="click_rate",
                        row_no=row_no,
                    ),
                    source_type=self._normalize_optional_text(row.get("source_type")) or normalized_source_type,
                    imported_by=self._normalize_optional_text(row.get("imported_by")) or normalized_imported_by,
                    notes=self._normalize_optional_text(row.get("notes")),
                    operator=normalized_operator,
                    commit=False,
                )
                results.append(
                    FeedbackBatchImportRowResult(
                        row_no=row_no,
                        task_id=result.task_id,
                        status=result.status,
                        generation_id=result.generation_id,
                        metric_id=result.metric_id,
                        prompt_type=result.prompt_type,
                        prompt_version=result.prompt_version,
                        day_offset=result.day_offset,
                        sample_count=result.sample_count,
                    )
                )
        except Exception:
            self.session.rollback()
            raise

        self.session.commit()
        return FeedbackBatchImportResult(imported_count=len(results), results=results)

    def list_task_metrics(self, task_id: str) -> list[PublicationMetric]:
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")
        return self.metrics.list_by_task_id(task_id)

    def list_experiments(
        self,
        *,
        limit: int = 20,
        prompt_type: Optional[str] = None,
        day_offset: Optional[int] = None,
    ) -> list[PromptExperiment]:
        return self.experiments.list_recent(limit=limit, prompt_type=prompt_type, day_offset=day_offset)

    def create_style_asset(
        self,
        *,
        asset_type: str,
        title: str,
        content: str,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
        weight: Optional[float] = None,
        source_task_id: Optional[str] = None,
        source_generation_id: Optional[str] = None,
        notes: Optional[str] = None,
        operator: Optional[str] = None,
    ) -> StyleAssetCreateResult:
        normalized_asset_type = asset_type.strip()
        normalized_status = (status or "active").strip() or "active"
        normalized_tags = [item.strip() for item in (tags or []) if item.strip()]
        normalized_operator = (operator or "").strip() or "manual"
        normalized_notes = self._normalize_optional_text(notes)

        source_task = None
        if source_task_id is not None:
            source_task = self.tasks.get_by_id(source_task_id)
            if source_task is None:
                raise ValueError("Source task not found.")

        source_generation = None
        if source_generation_id is not None:
            source_generation = self.generations.get_by_id(source_generation_id)
            if source_generation is None:
                raise ValueError("Source generation not found.")
            if source_task is not None and source_generation.task_id != source_task.id:
                raise ValueError("Source generation does not belong to source task.")
            if source_task is None:
                source_task = self.tasks.get_by_id(source_generation.task_id)

        asset = self.style_assets.create(
            StyleAsset(
                asset_type=normalized_asset_type,
                title=title.strip(),
                content=content.strip(),
                tags=normalized_tags or None,
                status=normalized_status,
                weight=weight if weight is not None else 1.0,
                source_task_id=source_task.id if source_task is not None else None,
                source_generation_id=source_generation.id if source_generation is not None else None,
                notes=normalized_notes,
            )
        )
        if source_task is not None:
            self._log_action(
                source_task.id,
                action="phase6.style_asset.created",
                operator=normalized_operator,
                payload={
                    "style_asset_id": asset.id,
                    "asset_type": asset.asset_type,
                    "title": asset.title,
                    "source_generation_id": asset.source_generation_id,
                },
            )
        self.session.commit()
        return StyleAssetCreateResult(
            style_asset_id=asset.id,
            asset_type=asset.asset_type,
            title=asset.title,
            status=asset.status,
        )

    def list_style_assets(
        self,
        *,
        limit: int = 20,
        asset_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[StyleAsset]:
        return self.style_assets.list_recent(limit=limit, asset_type=asset_type, status=status)

    def _resolve_generation(self, task_id: str, generation_id: Optional[str]) -> Generation:
        generation = self.generations.get_by_id(generation_id) if generation_id is not None else None
        if generation is not None and generation.task_id != task_id:
            raise ValueError("Generation does not belong to task.")
        if generation is None:
            generation = self.selection.resolve_current_accepted_generation(task_id) or self.generations.get_latest_by_task_id(task_id)
        if generation is None:
            raise ValueError("Generation not found for task.")
        return generation

    def _resolve_media_id(self, generation_id: str, supplied_media_id: Optional[str]) -> Optional[str]:
        normalized = self._normalize_optional_text(supplied_media_id)
        if normalized is not None:
            return normalized
        draft = self.wechat_drafts.get_latest_by_generation_id(generation_id)
        if draft is None:
            return None
        return self._normalize_optional_text(draft.media_id)

    def _refresh_prompt_experiment(self, prompt_type: str, prompt_version: str, day_offset: int) -> PromptExperiment:
        metrics = self.metrics.list_by_prompt_key(prompt_type, prompt_version, day_offset)
        experiment = self.experiments.get_by_key(prompt_type, prompt_version, day_offset)
        if experiment is None:
            experiment = self.experiments.create(
                PromptExperiment(
                    prompt_type=prompt_type,
                    prompt_version=prompt_version,
                    day_offset=day_offset,
                    sample_count=0,
                )
            )

        latest_metric = max(metrics, key=lambda item: (item.snapshot_at, item.updated_at, item.created_at), default=None)
        experiment.sample_count = len(metrics)
        experiment.avg_read_count = self._average(metrics, "read_count")
        experiment.avg_like_count = self._average(metrics, "like_count")
        experiment.avg_share_count = self._average(metrics, "share_count")
        experiment.avg_comment_count = self._average(metrics, "comment_count")
        experiment.avg_click_rate = self._average(metrics, "click_rate")
        experiment.best_read_count = self._max_int(metrics, "read_count")
        experiment.latest_metric_at = latest_metric.snapshot_at if latest_metric is not None else None
        experiment.last_task_id = latest_metric.task_id if latest_metric is not None else None
        experiment.last_generation_id = latest_metric.generation_id if latest_metric is not None else None
        return experiment

    def _log_action(
        self,
        task_id: str,
        *,
        action: str,
        operator: Optional[str],
        payload: Optional[dict],
    ) -> None:
        self.audit_logs.create(
            AuditLog(
                task_id=task_id,
                action=action,
                operator=(operator or "").strip() or "system",
                payload=payload,
            )
        )

    def _average(self, metrics: list[PublicationMetric], field_name: str) -> Optional[float]:
        values = [float(value) for value in (getattr(metric, field_name) for metric in metrics) if value is not None]
        if not values:
            return None
        return float(fmean(values))

    def _max_int(self, metrics: list[PublicationMetric], field_name: str) -> Optional[int]:
        values = [int(value) for value in (getattr(metric, field_name) for metric in metrics) if value is not None]
        if not values:
            return None
        return max(values)

    def _normalize_optional_text(self, value: Optional[str]) -> Optional[str]:
        normalized = (value or "").strip()
        return normalized or None

    def _parse_int_field(self, value: Optional[str], *, field_name: str, row_no: int) -> int:
        normalized = self._normalize_optional_text(value)
        if normalized is None:
            raise ValueError(f"Row {row_no}: {field_name} is required.")
        try:
            parsed = int(normalized)
        except ValueError as exc:
            raise ValueError(f"Row {row_no}: {field_name} must be an integer.") from exc
        if parsed < 0:
            raise ValueError(f"Row {row_no}: {field_name} must be >= 0.")
        return parsed

    def _parse_optional_int_field(self, value: Optional[str], *, field_name: str, row_no: int) -> Optional[int]:
        normalized = self._normalize_optional_text(value)
        if normalized is None:
            return None
        try:
            parsed = int(normalized)
        except ValueError as exc:
            raise ValueError(f"Row {row_no}: {field_name} must be an integer.") from exc
        if parsed < 0:
            raise ValueError(f"Row {row_no}: {field_name} must be >= 0.")
        return parsed

    def _parse_optional_float_field(self, value: Optional[str], *, field_name: str, row_no: int) -> Optional[float]:
        normalized = self._normalize_optional_text(value)
        if normalized is None:
            return None
        try:
            parsed = float(normalized)
        except ValueError as exc:
            raise ValueError(f"Row {row_no}: {field_name} must be a number.") from exc
        if parsed < 0:
            raise ValueError(f"Row {row_no}: {field_name} must be >= 0.")
        return parsed

    def _parse_datetime_field(self, value: Optional[str], *, row_no: int) -> Optional[datetime]:
        normalized = self._normalize_optional_text(value)
        if normalized is None:
            return None
        try:
            parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Row {row_no}: snapshot_at must be ISO datetime.") from exc
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
