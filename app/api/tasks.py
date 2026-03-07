from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.core.progress import get_progress
from app.core.security import verify_bearer_token
from app.db.session import get_db_session
from app.repositories.article_analysis_repository import ArticleAnalysisRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.content_brief_repository import ContentBriefRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.related_article_repository import RelatedArticleRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.wechat_draft_repository import WechatDraftRepository
from app.schemas.tasks import (
    ArticleAnalysisResponse,
    AuditLogResponse,
    ContentBriefResponse,
    GenerationResponse,
    GenerationWorkspaceResponse,
    RelatedArticleResponse,
    ReviewReportResponse,
    TaskBriefResponse,
    TaskDraftResponse,
    TaskResponse,
    TaskSummaryResponse,
    TaskWorkspaceResponse,
    SourceArticleDetailResponse,
)
from app.services.task_service import TaskService

router = APIRouter()


@router.get("/tasks", response_model=list[TaskSummaryResponse], dependencies=[Depends(verify_bearer_token)])
def list_tasks(
    limit: int = Query(default=10, ge=1, le=50),
    active_only: bool = Query(default=False),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: Session = Depends(get_db_session),
) -> list[TaskSummaryResponse]:
    if status_filter is not None:
        try:
            TaskStatus(status_filter)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status filter.") from exc
    items = TaskService(session).list_recent(limit, active_only=active_only, status_filter=status_filter)
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
            brief_id=item.brief_id,
            generation_id=item.generation_id,
            related_article_count=item.related_article_count,
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
    content_brief = ContentBriefRepository(session).get_latest_by_task_id(task_id)
    generation = GenerationRepository(session).get_latest_by_task_id(task_id)
    related_count = RelatedArticleRepository(session).count_by_task_id(task_id, selected_only=True)
    wechat_draft = WechatDraftRepository(session).get_latest_by_task_id(task_id)
    task_status = TaskStatus(task.status)
    error = task.error_message or task.error_code
    return TaskResponse(
        task_id=task.id,
        status=task.status,
        progress=get_progress(task_status),
        title=source_article.title if source_article else None,
        wechat_media_id=wechat_draft.media_id if wechat_draft else None,
        brief_id=content_brief.id if content_brief else None,
        generation_id=generation.id if generation else None,
        related_article_count=related_count,
        error=error,
    )


@router.get("/tasks/{task_id}/brief", response_model=TaskBriefResponse, dependencies=[Depends(verify_bearer_token)])
def get_task_brief(task_id: str, session: Session = Depends(get_db_session)) -> TaskBriefResponse:
    task = TaskRepository(session).get_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    analysis = ArticleAnalysisRepository(session).get_latest_by_task_id(task_id)
    brief = ContentBriefRepository(session).get_latest_by_task_id(task_id)
    related_articles = RelatedArticleRepository(session).list_selected_by_task_id(task_id)
    return TaskBriefResponse(
        task_id=task.id,
        status=task.status,
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
        related_articles=[
            RelatedArticleResponse(
                article_id=item.id,
                query_text=item.query_text,
                rank_no=item.rank_no,
                url=item.url,
                title=item.title,
                source_site=item.source_site,
                summary=item.summary,
                published_at=item.published_at,
                popularity_score=float(item.popularity_score) if item.popularity_score is not None else None,
                relevance_score=float(item.relevance_score) if item.relevance_score is not None else None,
                diversity_score=float(item.diversity_score) if item.diversity_score is not None else None,
                factual_density_score=float(item.factual_density_score) if item.factual_density_score is not None else None,
                snapshot_path=item.snapshot_path,
                fetch_status=item.fetch_status,
                selected=item.selected,
            )
            for item in related_articles
        ],
    )


@router.get("/tasks/{task_id}/draft", response_model=TaskDraftResponse, dependencies=[Depends(verify_bearer_token)])
def get_task_draft(task_id: str, session: Session = Depends(get_db_session)) -> TaskDraftResponse:
    task = TaskRepository(session).get_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    generation = GenerationRepository(session).get_latest_by_task_id(task_id)
    review = ReviewReportRepository(session).get_latest_by_generation_id(generation.id) if generation else None
    return TaskDraftResponse(
        task_id=task.id,
        status=task.status,
        generation=(
            GenerationResponse(
                generation_id=generation.id,
                version_no=generation.version_no,
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
            )
            if generation
            else None
        ),
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


@router.get("/tasks/{task_id}/workspace", response_model=TaskWorkspaceResponse, dependencies=[Depends(verify_bearer_token)])
def get_task_workspace(task_id: str, session: Session = Depends(get_db_session)) -> TaskWorkspaceResponse:
    task = TaskRepository(session).get_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    source_article_repo = SourceArticleRepository(session)
    analysis_repo = ArticleAnalysisRepository(session)
    brief_repo = ContentBriefRepository(session)
    generation_repo = GenerationRepository(session)
    review_repo = ReviewReportRepository(session)
    related_repo = RelatedArticleRepository(session)
    wechat_draft_repo = WechatDraftRepository(session)
    audit_repo = AuditLogRepository(session)

    source_article = source_article_repo.get_latest_by_task_id(task_id)
    analysis = analysis_repo.get_latest_by_task_id(task_id)
    brief = brief_repo.get_latest_by_task_id(task_id)
    generations = generation_repo.list_by_task_id(task_id, limit=8)
    audits = audit_repo.list_by_task_id(task_id, limit=25)
    related_count = related_repo.count_by_task_id(task_id, selected_only=True)
    wechat_draft = wechat_draft_repo.get_latest_by_task_id(task_id)
    error = task.error_message or task.error_code
    task_status = TaskStatus(task.status)

    generation_rows: list[GenerationWorkspaceResponse] = []
    for generation in generations:
        review = review_repo.get_latest_by_generation_id(generation.id)
        generation_rows.append(
            GenerationWorkspaceResponse(
                generation_id=generation.id,
                version_no=generation.version_no,
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
                prompt_version=_prompt_version_for_generation(generation.model_name),
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


def _prompt_version_for_generation(model_name: str) -> str:
    if model_name in {"glm-5", "phase4-fallback-template"}:
        return "phase4-v1"
    return "unknown"
