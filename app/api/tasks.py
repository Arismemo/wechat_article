from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.core.progress import get_progress
from app.core.prompt_versions import resolve_generation_prompt_version
from app.core.security import verify_bearer_token
from app.db.session import get_db_session
from app.repositories.article_analysis_repository import ArticleAnalysisRepository
from app.repositories.content_brief_repository import ContentBriefRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.related_article_repository import RelatedArticleRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.wechat_draft_repository import WechatDraftRepository
from app.schemas.tasks import (
    ArticleAnalysisResponse,
    ContentBriefResponse,
    GenerationResponse,
    RelatedArticleResponse,
    SourceArticleDetailResponse,
    TaskBriefResponse,
    TaskDraftResponse,
    TaskResponse,
    TaskSummaryResponse,
    TaskWorkspaceResponse,
)
from app.services.review_report_response_service import build_review_report_response
from app.services.task_service import TaskService
from app.services.task_workspace_query_service import TaskWorkspaceQueryService
from app.services.wechat_draft_metadata_service import build_wechat_draft_metadata
from app.services.wechat_push_policy_service import WechatPushPolicyService

router = APIRouter()


@router.get("/tasks", response_model=list[TaskSummaryResponse], dependencies=[Depends(verify_bearer_token)])
def list_tasks(
    limit: int = Query(default=10, ge=1, le=100),
    active_only: bool = Query(default=False),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    source_type: Optional[str] = Query(default=None, max_length=64),
    query: Optional[str] = Query(default=None, max_length=200),
    created_after: Optional[datetime] = Query(default=None),
    session: Session = Depends(get_db_session),
) -> list[TaskSummaryResponse]:
    if status_filter is not None:
        try:
            TaskStatus(status_filter)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status filter.") from exc
    items = TaskService(session).list_recent(
        limit,
        active_only=active_only,
        status_filter=status_filter,
        source_type=source_type,
        query=query,
        created_after=created_after,
    )
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
    draft_metadata = build_wechat_draft_metadata(wechat_draft)
    task_status = TaskStatus(task.status)
    push_policy = WechatPushPolicyService(session).get_policy(task_id)
    error = task.error_message or task.error_code
    return TaskResponse(
        task_id=task.id,
        status=task.status,
        progress=get_progress(task_status),
        title=source_article.title if source_article else None,
        wechat_media_id=draft_metadata.media_id,
        wechat_draft_url=draft_metadata.draft_url,
        wechat_draft_url_direct=draft_metadata.draft_url_direct,
        wechat_draft_url_hint=draft_metadata.draft_url_hint,
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
                prompt_type=(generation.prompt_type or None),
                prompt_version=resolve_generation_prompt_version(
                    generation.model_name,
                    prompt_type=generation.prompt_type or None,
                    stored_prompt_version=generation.prompt_version,
                ),
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
            build_review_report_response(review)
        ),
    )


@router.get("/tasks/{task_id}/workspace", response_model=TaskWorkspaceResponse, dependencies=[Depends(verify_bearer_token)])
def get_task_workspace(task_id: str, session: Session = Depends(get_db_session)) -> TaskWorkspaceResponse:
    try:
        return TaskWorkspaceQueryService(session).build_workspace(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
