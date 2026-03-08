from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.enums import ACTIVE_TASK_STATUSES, FINAL_FAILURE_STATUSES, TaskStatus
from app.core.progress import get_progress
from app.core.prompt_versions import resolve_generation_prompt_metadata, resolve_generation_prompt_version
from app.models.task import Task
from app.repositories.article_analysis_repository import ArticleAnalysisRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.content_brief_repository import ContentBriefRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.related_article_repository import RelatedArticleRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.wechat_draft_repository import WechatDraftRepository
from app.schemas.admin_monitor import AdminMonitorSnapshotResponse, AdminMonitorSummaryResponse
from app.schemas.tasks import (
    ArticleAnalysisResponse,
    AuditLogResponse,
    ContentBriefResponse,
    GenerationWorkspaceResponse,
    ReviewReportResponse,
    SourceArticleDetailResponse,
    TaskSummaryResponse,
    TaskWorkspaceResponse,
    WechatPushPolicyResponse,
)
from app.services.task_service import TaskService
from app.services.wechat_push_policy_service import WechatPushPolicyService
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
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.tasks = TaskRepository(session)
        self.task_service = TaskService(session)
        self.source_articles = SourceArticleRepository(session)
        self.analyses = ArticleAnalysisRepository(session)
        self.briefs = ContentBriefRepository(session)
        self.generations = GenerationRepository(session)
        self.reviews = ReviewReportRepository(session)
        self.related_articles = RelatedArticleRepository(session)
        self.wechat_drafts = WechatDraftRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.wechat_push_policy = WechatPushPolicyService(session)

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
            workspace=workspace,
        )

    def build_workspace(self, task_id: str) -> TaskWorkspaceResponse:
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")

        source_article = self.source_articles.get_latest_by_task_id(task_id)
        analysis = self.analyses.get_latest_by_task_id(task_id)
        brief = self.briefs.get_latest_by_task_id(task_id)
        generations = self.generations.list_by_task_id(task_id, limit=8)
        audits = self.audit_logs.list_by_task_id(task_id, limit=25)
        related_count = self.related_articles.count_by_task_id(task_id, selected_only=True)
        wechat_draft = self.wechat_drafts.get_latest_by_task_id(task_id)
        push_policy = self.wechat_push_policy.get_policy(task_id)
        error = task.error_message or task.error_code
        task_status = TaskStatus(task.status)

        generation_rows: list[GenerationWorkspaceResponse] = []
        for generation in generations:
            review = self.reviews.get_latest_by_generation_id(generation.id)
            generation_prompt_type, generation_prompt_version = resolve_generation_prompt_metadata(
                generation.model_name,
                stored_prompt_type=generation.prompt_type,
                stored_prompt_version=generation.prompt_version,
            )
            generation_rows.append(
                GenerationWorkspaceResponse(
                    generation_id=generation.id,
                    version_no=generation.version_no,
                    prompt_type=generation_prompt_type,
                    prompt_version=generation_prompt_version,
                    model_name=generation.model_name,
                    title=generation.title,
                    subtitle=generation.subtitle,
                    digest=generation.digest,
                    markdown_content=generation.markdown_content,
                    html_content=generation.html_content,
                    score_overall=float(generation.score_overall) if generation.score_overall is not None else None,
                    score_title=float(generation.score_title) if generation.score_title is not None else None,
                    score_readability=float(generation.score_readability) if generation.score_readability is not None else None,
                    score_novelty=float(generation.score_novelty) if generation.score_novelty is not None else None,
                    score_risk=float(generation.score_risk) if generation.score_risk is not None else None,
                    status=generation.status,
                    created_at=generation.created_at,
                    review=(
                        ReviewReportResponse(
                            review_report_id=review.id,
                            similarity_score=float(review.similarity_score) if review.similarity_score is not None else None,
                            factual_risk_score=float(review.factual_risk_score) if review.factual_risk_score is not None else None,
                            policy_risk_score=float(review.policy_risk_score) if review.policy_risk_score is not None else None,
                            readability_score=float(review.readability_score) if review.readability_score is not None else None,
                            title_score=float(review.title_score) if review.title_score is not None else None,
                            novelty_score=float(review.novelty_score) if review.novelty_score is not None else None,
                            issues=review.issues,
                            suggestions=review.suggestions,
                            final_decision=review.final_decision,
                        )
                        if review
                        else None
                    ),
                )
            )

        return TaskWorkspaceResponse(
            task_id=task.id,
            task_code=task.task_code,
            source_url=task.source_url,
            source_type=task.source_type,
            status=task.status,
            progress=get_progress(task_status),
            title=source_article.title if source_article else None,
            wechat_media_id=wechat_draft.media_id if wechat_draft else None,
            brief_id=brief.id if brief else None,
            generation_id=generations[0].id if generations else None,
            related_article_count=related_count,
            error=error,
            created_at=task.created_at,
            updated_at=task.updated_at,
            wechat_push_policy=WechatPushPolicyResponse(
                mode=push_policy.mode,
                can_push=push_policy.can_push,
                note=push_policy.note,
                operator=push_policy.operator,
                source_action=push_policy.source_action,
                updated_at=push_policy.updated_at,
            ),
            source_article=(
                SourceArticleDetailResponse(
                    source_article_id=source_article.id,
                    url=source_article.url,
                    title=source_article.title,
                    author=source_article.author,
                    published_at=source_article.published_at,
                    cover_image_url=source_article.cover_image_url,
                    summary=source_article.summary,
                    cleaned_text_excerpt=(source_article.cleaned_text or "")[:3000] or None,
                    snapshot_path=source_article.snapshot_path,
                    fetch_status=source_article.fetch_status,
                    word_count=source_article.word_count,
                    created_at=source_article.created_at,
                )
                if source_article
                else None
            ),
            analysis=(
                ArticleAnalysisResponse(
                    analysis_id=analysis.id,
                    theme=analysis.theme,
                    audience=analysis.audience,
                    angle=analysis.angle,
                    tone=analysis.tone,
                    key_points=analysis.key_points,
                    facts=analysis.facts,
                    hooks=analysis.hooks,
                    risks=analysis.risks,
                    gaps=analysis.gaps,
                    structure=analysis.structure,
                )
                if analysis
                else None
            ),
            brief=(
                ContentBriefResponse(
                    brief_id=brief.id,
                    brief_version=brief.brief_version,
                    positioning=brief.positioning,
                    new_angle=brief.new_angle,
                    target_reader=brief.target_reader,
                    must_cover=brief.must_cover,
                    must_avoid=brief.must_avoid,
                    difference_matrix=brief.difference_matrix,
                    outline=brief.outline,
                    title_directions=brief.title_directions,
                )
                if brief
                else None
            ),
            generations=generation_rows,
            audits=[
                AuditLogResponse(
                    audit_log_id=log.id,
                    action=log.action,
                    operator=log.operator,
                    payload=log.payload,
                    created_at=log.created_at,
                )
                for log in audits
            ],
        )

    def _build_summary(
        self,
        filters: AdminMonitorFilters,
        task_summaries: list[TaskSummaryResponse],
    ) -> AdminMonitorSummaryResponse:
        today_start = self._start_of_today_utc()
        status_counts: dict[str, int] = {}
        for item in task_summaries:
            status_counts[item.status] = status_counts.get(item.status, 0) + 1

        active_statuses = [item.value for item in ACTIVE_TASK_STATUSES]
        manual_statuses = [TaskStatus.NEEDS_MANUAL_REVIEW.value, TaskStatus.NEEDS_MANUAL_SOURCE.value, TaskStatus.NEEDS_REGENERATE.value]
        failure_statuses = [item.value for item in FINAL_FAILURE_STATUSES]

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
            today_submitted=self.tasks.count(created_after=today_start),
            today_draft_saved=self.tasks.count(
                status_values=[TaskStatus.DRAFT_SAVED.value],
                created_after=today_start,
            ),
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
            brief_id=item.brief_id,
            generation_id=item.generation_id,
            related_article_count=item.related_article_count,
            error=item.error,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def _start_of_today_utc(self) -> datetime:
        timezone_name = self.settings.timezone or "Asia/Shanghai"
        zone = ZoneInfo(timezone_name)
        now_local = datetime.now(zone)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_local.astimezone(timezone.utc)
