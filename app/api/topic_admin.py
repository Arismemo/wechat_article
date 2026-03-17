from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import verify_admin_api_auth
from app.db.session import get_db_session
from app.schemas.topic_intelligence import (
    TopicCandidateSummaryResponse,
    TopicPlanPromoteRequest,
    TopicPlanPromoteResponse,
    TopicPlanResponse,
    TopicPlanTaskLinkResponse,
    TopicSignalResponse,
    TopicSnapshotResponse,
    TopicSnapshotSummaryResponse,
    TopicSourceResponse,
    TopicWorkspaceResponse,
)
from app.services.topic_intelligence_service import TopicIntelligenceService, TopicSnapshotFilters


router = APIRouter()


def _build_source_response(item) -> TopicSourceResponse:
    config = dict(item.config or {})
    signal_count = int(getattr(item, "_signal_count", 0))
    return TopicSourceResponse(
        source_id=item.id,
        source_key=item.source_key,
        name=item.name,
        source_type=item.source_type,
        content_pillar=item.content_pillar,
        enabled=item.enabled,
        fetch_interval_minutes=item.fetch_interval_minutes,
        config=config,
        signal_count=signal_count,
        last_fetched_at=item.last_fetched_at,
        last_success_at=item.last_success_at,
        last_error=item.last_error,
    )


def _build_candidate_response(item) -> TopicCandidateSummaryResponse:
    return TopicCandidateSummaryResponse(
        candidate_id=item.id,
        cluster_key=item.cluster_key,
        topic_title=item.topic_title,
        topic_summary=item.topic_summary,
        content_pillar=item.content_pillar,
        hotness_score=float(item.hotness_score) if item.hotness_score is not None else None,
        commercial_fit_score=float(item.commercial_fit_score) if item.commercial_fit_score is not None else None,
        evidence_score=float(item.evidence_score) if item.evidence_score is not None else None,
        novelty_score=float(item.novelty_score) if item.novelty_score is not None else None,
        wechat_fit_score=float(item.wechat_fit_score) if item.wechat_fit_score is not None else None,
        risk_score=float(item.risk_score) if item.risk_score is not None else None,
        total_score=float(item.total_score) if item.total_score is not None else None,
        recommended_business_goal=item.recommended_business_goal,
        recommended_article_type=item.recommended_article_type,
        canonical_seed_url=item.canonical_seed_url,
        status=item.status,
        signal_count=item.signal_count,
        latest_signal_at=item.latest_signal_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _build_plan_response(item) -> TopicPlanResponse:
    return TopicPlanResponse(
        plan_id=item.id,
        candidate_id=item.candidate_id,
        plan_version=item.plan_version,
        business_goal=item.business_goal,
        article_type=item.article_type,
        angle=item.angle,
        why_now=item.why_now,
        target_reader=item.target_reader,
        must_cover=item.must_cover,
        must_avoid=item.must_avoid,
        keywords=item.keywords,
        search_friendly_title=item.search_friendly_title,
        distribution_friendly_title=item.distribution_friendly_title,
        summary=item.summary,
        cta_mode=item.cta_mode,
        source_grade=item.source_grade,
        recommended_queries=item.recommended_queries,
        seed_source_pack=item.seed_source_pack,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _build_workspace_response(workspace: dict) -> TopicWorkspaceResponse:
    return TopicWorkspaceResponse(
        candidate=_build_candidate_response(workspace["candidate"]),
        plan=_build_plan_response(workspace["plan"]),
        signals=[
            TopicSignalResponse(
                signal_id=item.id,
                source_id=item.source_id,
                signal_type=item.signal_type,
                title=item.title,
                url=item.url,
                normalized_url=item.normalized_url,
                summary=item.summary,
                source_site=item.source_site,
                source_tier=item.source_tier,
                published_at=item.published_at,
                discovered_at=item.discovered_at,
                fetch_status=item.fetch_status,
            )
            for item in workspace["signals"]
        ],
        task_links=[
            TopicPlanTaskLinkResponse(
                link_id=item.id,
                plan_id=item.plan_id,
                task_id=item.task_id,
                operator=item.operator,
                note=item.note,
                created_at=item.created_at,
            )
            for item in workspace["task_links"]
        ],
    )


@router.get(
    "/admin/topics/snapshot",
    response_model=TopicSnapshotResponse,
    dependencies=[Depends(verify_admin_api_auth)],
)
def get_topic_snapshot(
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    content_pillar: Optional[str] = Query(default=None, max_length=64),
    selected_plan_id: Optional[str] = Query(default=None),
    selected_candidate_id: Optional[str] = Query(default=None),
    session: Session = Depends(get_db_session),
) -> TopicSnapshotResponse:
    service = TopicIntelligenceService(session)
    try:
        payload = service.build_snapshot(
            TopicSnapshotFilters(
                limit=limit,
                status=status_filter,
                content_pillar=content_pillar,
                selected_plan_id=selected_plan_id,
                selected_candidate_id=selected_candidate_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TopicSnapshotResponse(
        summary=TopicSnapshotSummaryResponse(**payload["summary"]),
        sources=[_build_source_response(item) for item in payload["sources"]],
        candidates=[_build_candidate_response(item) for item in payload["candidates"]],
        workspace=_build_workspace_response(payload["workspace"]) if payload["workspace"] else None,
    )


@router.get(
    "/admin/topics/sources",
    response_model=list[TopicSourceResponse],
    dependencies=[Depends(verify_admin_api_auth)],
)
def list_topic_sources(session: Session = Depends(get_db_session)) -> list[TopicSourceResponse]:
    rows = TopicIntelligenceService(session).list_sources()
    return [_build_source_response(item) for item in rows]


@router.get(
    "/admin/topics/candidates",
    response_model=list[TopicCandidateSummaryResponse],
    dependencies=[Depends(verify_admin_api_auth)],
)
def list_topic_candidates(
    limit: int = Query(default=50, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    content_pillar: Optional[str] = Query(default=None, max_length=64),
    session: Session = Depends(get_db_session),
) -> list[TopicCandidateSummaryResponse]:
    items = TopicIntelligenceService(session).list_candidates(
        limit=limit,
        status=status_filter,
        content_pillar=content_pillar,
    )
    return [_build_candidate_response(item) for item in items]


@router.get(
    "/admin/topics/plans/{plan_id}",
    response_model=TopicWorkspaceResponse,
    dependencies=[Depends(verify_admin_api_auth)],
)
def get_topic_plan(plan_id: str, session: Session = Depends(get_db_session)) -> TopicWorkspaceResponse:
    try:
        workspace = TopicIntelligenceService(session).get_plan_workspace(plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _build_workspace_response(workspace)


@router.post(
    "/admin/topics/plans/{plan_id}/promote",
    response_model=TopicPlanPromoteResponse,
    dependencies=[Depends(verify_admin_api_auth)],
)
def promote_topic_plan(
    plan_id: str,
    payload: TopicPlanPromoteRequest,
    session: Session = Depends(get_db_session),
) -> TopicPlanPromoteResponse:
    try:
        result = TopicIntelligenceService(session).promote_plan(
            plan_id,
            operator=payload.operator,
            note=payload.note,
            enqueue_phase3=payload.enqueue_phase3,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return TopicPlanPromoteResponse(
        plan_id=result.plan_id,
        candidate_id=result.candidate_id,
        task_id=result.task_id,
        task_code=result.task_code,
        deduped=result.deduped,
        status=result.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )
