from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.admin_ui import admin_overview_card, admin_overview_strip, render_admin_page
from app.core.security import verify_admin_basic_auth
from app.templating import render_template
from app.db.session import get_db_session
from app.schemas.topic_intelligence import (
    TopicCandidateStatusUpdateRequest,
    TopicCandidateStatusUpdateResponse,
    TopicPlanPromoteRequest,
    TopicPlanPromoteResponse,
    TopicSourceEnqueueResponse,
    TopicSourceRunResponse,
)
from app.services.topic_fetch_queue_service import TopicFetchQueueService
from app.services.topic_intelligence_service import TopicIntelligenceService


router = APIRouter()


def _topic_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=status_code, detail=detail)


def _build_candidate_status_update_response(result) -> TopicCandidateStatusUpdateResponse:
    return TopicCandidateStatusUpdateResponse(
        candidate_id=result.candidate_id,
        previous_status=result.previous_status,
        status=result.status,
        changed=result.changed,
    )


@router.post(
    "/admin/api/topics/sources/{source_id}/run",
    response_model=TopicSourceRunResponse,
    tags=["admin-topics"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_run_topic_source(source_id: str, session: Session = Depends(get_db_session)) -> TopicSourceRunResponse:
    try:
        result = TopicIntelligenceService(session).run_source(source_id, trigger_type="admin-web")
    except ValueError as exc:
        raise _topic_error(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.") from exc
    return TopicSourceRunResponse(
        source_id=result.source_id,
        source_key=result.source_key,
        run_id=result.run_id,
        status=result.status,
        fetched_count=result.fetched_count,
        new_signal_count=result.new_signal_count,
        candidate_count=result.candidate_count,
        latest_plan_ids=result.latest_plan_ids,
    )


@router.post(
    "/admin/api/topics/sources/{source_id}/enqueue",
    response_model=TopicSourceEnqueueResponse,
    tags=["admin-topics"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_enqueue_topic_source(source_id: str, session: Session = Depends(get_db_session)) -> TopicSourceEnqueueResponse:
    service = TopicIntelligenceService(session)
    service.sync_registry()
    source = service.sources.get_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic source not found.")
    result = TopicFetchQueueService().enqueue(source_id)
    return TopicSourceEnqueueResponse(
        source_id=result.source_id,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post(
    "/admin/api/topics/candidates/{candidate_id}/watch",
    response_model=TopicCandidateStatusUpdateResponse,
    tags=["admin-topics"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_watch_topic_candidate(
    candidate_id: str,
    payload: TopicCandidateStatusUpdateRequest,
    session: Session = Depends(get_db_session),
) -> TopicCandidateStatusUpdateResponse:
    try:
        result = TopicIntelligenceService(session).update_candidate_status(
            candidate_id,
            status="watching",
            operator=payload.operator,
            note=payload.note,
        )
    except ValueError as exc:
        raise _topic_error(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.") from exc
    return _build_candidate_status_update_response(result)


@router.post(
    "/admin/api/topics/candidates/{candidate_id}/ignore",
    response_model=TopicCandidateStatusUpdateResponse,
    tags=["admin-topics"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_ignore_topic_candidate(
    candidate_id: str,
    payload: TopicCandidateStatusUpdateRequest,
    session: Session = Depends(get_db_session),
) -> TopicCandidateStatusUpdateResponse:
    try:
        result = TopicIntelligenceService(session).update_candidate_status(
            candidate_id,
            status="ignored",
            operator=payload.operator,
            note=payload.note,
        )
    except ValueError as exc:
        raise _topic_error(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.") from exc
    return _build_candidate_status_update_response(result)


@router.post(
    "/admin/api/topics/candidates/{candidate_id}/plan",
    response_model=TopicCandidateStatusUpdateResponse,
    tags=["admin-topics"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_restore_topic_candidate_to_plan(
    candidate_id: str,
    payload: TopicCandidateStatusUpdateRequest,
    session: Session = Depends(get_db_session),
) -> TopicCandidateStatusUpdateResponse:
    try:
        result = TopicIntelligenceService(session).update_candidate_status(
            candidate_id,
            status="planned",
            operator=payload.operator,
            note=payload.note,
        )
    except ValueError as exc:
        raise _topic_error(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.") from exc
    return _build_candidate_status_update_response(result)


@router.post(
    "/admin/api/topics/refresh-candidates",
    response_model=list[str],
    tags=["admin-topics"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_refresh_topic_candidates(session: Session = Depends(get_db_session)) -> list[str]:
    service = TopicIntelligenceService(session)
    try:
        service.sync_registry()
        plan_ids = service.refresh_candidates()
        session.commit()
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.") from exc
    return plan_ids


@router.post(
    "/admin/api/topics/plans/{plan_id}/promote",
    response_model=TopicPlanPromoteResponse,
    tags=["admin-topics"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_promote_topic_plan(
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
        raise _topic_error(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.") from exc
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


@router.get("/admin/topics", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def admin_topics_console() -> str:
    overview_html = admin_overview_strip(
        "选题概览",
        "".join(
            [
                admin_overview_card("启用来源", "0", "当前处于启用状态的抓取来源。", value_id="summary-source-enabled"),
                admin_overview_card("候选总量", "0", "当前候选池规模。", value_id="summary-candidate-total"),
                admin_overview_card("已计划", "0", "已经形成计划但尚未推进到任务。", value_id="summary-planned-total"),
                admin_overview_card(
                    "24h 新信号",
                    "0",
                    "最近 24 小时新进入系统的公开信号。",
                    highlight=True,
                    value_id="summary-new-signal-24h",
                ),
            ]
        ),
    )

    html = render_template("admin/topics.html")

    return render_admin_page(html.replace("__TOPICS_OVERVIEW__", overview_html), "topics")
