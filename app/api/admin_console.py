from __future__ import annotations

import json
from datetime import datetime
from time import sleep
from textwrap import dedent
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.security import verify_admin_basic_auth
from app.db.session import get_db_session, get_session_factory
from app.api.admin_ui import admin_section_nav, admin_section_nav_styles
from app.schemas.admin_monitor import AdminMonitorSnapshotResponse
from app.schemas.ingest import IngestLinkRequest, IngestLinkResponse
from app.schemas.internal import ManualReviewActionResponse, Phase4EnqueueResponse, TaskDeleteResponse, WechatPushResponse
from app.services.admin_monitor_service import AdminMonitorFilters, AdminMonitorService
from app.services.manual_review_service import ManualReviewConflictError, ManualReviewService
from app.services.phase4_queue_service import Phase4QueueService
from app.services.task_service import TaskService
from app.services.wechat_draft_publish_service import WechatDraftPublishService
from app.services.wechat_push_policy_service import WechatPushBlockedError


router = APIRouter()


@router.get(
    "/admin/api/home-snapshot",
    response_model=AdminMonitorSnapshotResponse,
    tags=["admin"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_home_snapshot(
    limit: int = Query(default=18, ge=1, le=50),
    selected_task_id: Optional[str] = Query(default=None),
    session: Session = Depends(get_db_session),
) -> AdminMonitorSnapshotResponse:
    return AdminMonitorService(session).build_snapshot(
        AdminMonitorFilters(
            limit=limit,
            active_only=False,
            selected_task_id=selected_task_id,
        )
    )


@router.post(
    "/admin/api/ingest",
    response_model=IngestLinkResponse,
    tags=["admin"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_ingest(
    payload: IngestLinkRequest,
    session: Session = Depends(get_db_session),
) -> IngestLinkResponse:
    task_service = TaskService(session)
    task, deduped = task_service.ingest_link(
        IngestLinkRequest(
            url=payload.url,
            source="admin-web",
            device_id="admin-browser",
            trigger="admin-home",
            note=payload.note,
            dispatch_mode="phase4_enqueue",
        )
    )
    if not deduped:
        task = task_service.mark_queued_for_phase4(task, reason="admin-home")
        queue_result = Phase4QueueService().enqueue(task.id)
        return IngestLinkResponse(
            task_id=task.id,
            status=task.status,
            deduped=deduped,
            dispatch_mode="phase4_enqueue",
            enqueued=queue_result.enqueued,
            queue_depth=queue_result.queue_depth,
        )

    return IngestLinkResponse(
        task_id=task.id,
        status=task.status,
        deduped=deduped,
        dispatch_mode="phase4_enqueue",
        enqueued=False,
        queue_depth=None,
    )


@router.post(
    "/admin/api/tasks/{task_id}/retry",
    response_model=Phase4EnqueueResponse,
    tags=["admin"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_retry_phase4(task_id: str, session: Session = Depends(get_db_session)) -> Phase4EnqueueResponse:
    task_service = TaskService(session)
    try:
        task = task_service.require_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    task = task_service.mark_queued_for_phase4(task, reason="admin-retry")
    result = Phase4QueueService().enqueue(task.id)
    return Phase4EnqueueResponse(
        task_id=task.id,
        status=task.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post(
    "/admin/api/tasks/{task_id}/approve",
    response_model=ManualReviewActionResponse,
    tags=["admin"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_approve_latest_generation(
    task_id: str,
    session: Session = Depends(get_db_session),
) -> ManualReviewActionResponse:
    try:
        result = ManualReviewService(session).approve_latest_generation(task_id, operator="admin-home")
    except ManualReviewConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ManualReviewActionResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        decision=result.decision,
    )


@router.post(
    "/admin/api/tasks/{task_id}/reject",
    response_model=ManualReviewActionResponse,
    tags=["admin"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_reject_latest_generation(
    task_id: str,
    session: Session = Depends(get_db_session),
) -> ManualReviewActionResponse:
    try:
        result = ManualReviewService(session).reject_latest_generation(task_id, operator="admin-home")
    except ManualReviewConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ManualReviewActionResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        decision=result.decision,
    )


@router.post(
    "/admin/api/tasks/{task_id}/push-draft",
    response_model=WechatPushResponse,
    tags=["admin"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_push_wechat_draft(
    task_id: str,
    session: Session = Depends(get_db_session),
) -> WechatPushResponse:
    try:
        result = WechatDraftPublishService(session).push_latest_accepted_generation(task_id)
    except WechatPushBlockedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return WechatPushResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        wechat_media_id=result.wechat_media_id,
        reused_existing=result.reused_existing,
    )


@router.delete(
    "/admin/api/tasks/{task_id}",
    response_model=TaskDeleteResponse,
    tags=["admin"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_delete_task(
    task_id: str,
    session: Session = Depends(get_db_session),
) -> TaskDeleteResponse:
    try:
        result = TaskService(session).delete_task(task_id, operator="admin-home")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TaskDeleteResponse(task_id=result.task_id, task_code=result.task_code, deleted=result.deleted)


@router.get(
    "/admin/console/stream",
    tags=["admin"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def unified_console_stream(
    limit: int = Query(default=36, ge=1, le=100),
    active_only: bool = Query(default=False),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    source_type: Optional[str] = Query(default=None),
    query: Optional[str] = Query(default=None),
    created_after: Optional[datetime] = Query(default=None),
    selected_task_id: Optional[str] = Query(default=None),
    poll_seconds: int = Query(default=5, ge=3, le=60),
    once: bool = Query(default=False),
):
    session_factory = get_session_factory()

    def event_stream():
        while True:
            with session_factory() as session:
                snapshot = AdminMonitorService(session).build_snapshot(
                    AdminMonitorFilters(
                        limit=limit,
                        active_only=active_only,
                        status_filter=status_filter,
                        source_type=source_type,
                        query=query,
                        created_after=created_after,
                        selected_task_id=selected_task_id,
                    )
                )
            payload = json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False)
            yield f"event: snapshot\ndata: {payload}\n\n"
            if once:
                break
            sleep(poll_seconds)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/admin", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def unified_admin_portal(task_id: Optional[str] = Query(default=None)) -> str:
    html = dedent(
        f"""\
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>微信文章工厂</title>
          <style>
            :root {{
              --paper: rgba(255, 251, 246, 0.94);
              --paper-soft: rgba(255, 249, 242, 0.88);
              --line: rgba(65, 48, 27, 0.12);
              --text: #241b12;
              --muted: #6a5f53;
              --accent: #1f5d53;
              --accent-strong: #143d37;
              --accent-soft: rgba(31, 93, 83, 0.12);
              --gold: #b07a18;
              --danger: #a14534;
              --ok: #2f7c53;
              --shadow: 0 22px 60px rgba(58, 40, 18, 0.12);
            }}
            * {{ box-sizing: border-box; }}
            body {{
              margin: 0;
              min-height: 100vh;
              color: var(--text);
              line-height: 1.5;
              font-family: "PingFang SC", "Noto Serif SC", serif;
              background:
                radial-gradient(circle at top left, rgba(244, 210, 147, 0.58), transparent 24%),
                radial-gradient(circle at top right, rgba(168, 209, 196, 0.42), transparent 26%),
                linear-gradient(145deg, #efe5d7 0%, #f7f3ec 42%, #eadfcd 100%);
            }}
            .skip-link {{
              position: absolute;
              top: 16px;
              left: 16px;
              transform: translateY(-180%);
              padding: 10px 14px;
              border-radius: 999px;
              background: var(--accent-strong);
              color: #f7faf8;
              text-decoration: none;
              z-index: 20;
              transition: transform 120ms ease;
            }}
            .skip-link:focus-visible {{
              transform: translateY(0);
            }}
            main {{
              max-width: 1420px;
              margin: 0 auto;
              padding: 28px 20px 42px;
            }}
            .shell {{
              display: grid;
              gap: 18px;
            }}
            .hero {{
              display: grid;
              gap: 14px;
              padding: 24px;
              border: 1px solid var(--line);
              border-radius: 28px;
              background: linear-gradient(135deg, rgba(255, 248, 239, 0.92), rgba(248, 244, 237, 0.86));
              box-shadow: var(--shadow);
              backdrop-filter: blur(10px);
            }}
            .hero-grid {{
              display: grid;
              grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.95fr);
              gap: 18px;
              align-items: stretch;
            }}
            .badge {{
              display: inline-flex;
              width: fit-content;
              padding: 6px 11px;
              border-radius: 999px;
              background: var(--accent-soft);
              color: var(--accent-strong);
              font-size: 12px;
              letter-spacing: 0.08em;
            }}
            h1 {{
              margin: 0;
              font-size: 42px;
              line-height: 1;
            }}
            .hero-copy {{
              display: grid;
              align-content: start;
              gap: 10px;
            }}
            .hero-copy p {{
              margin: 0;
              max-width: 760px;
              color: var(--muted);
              line-height: 1.7;
            }}
            .hero-status-card {{
              display: grid;
              gap: 14px;
              padding: 18px;
              border-radius: 24px;
              border: 1px solid rgba(31, 93, 83, 0.12);
              background: linear-gradient(160deg, rgba(255, 252, 247, 0.95), rgba(249, 245, 237, 0.9));
            }}
            .hero-status-copy {{
              margin: 0;
              font-size: 15px;
              line-height: 1.7;
            }}
            .hero-summary {{
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: 10px;
            }}
            .hero-summary-card {{
              display: grid;
              gap: 6px;
              padding: 12px 14px;
              border-radius: 18px;
              border: 1px solid rgba(65, 48, 27, 0.1);
              background: rgba(255, 253, 249, 0.78);
            }}
            .hero-summary-card strong {{
              color: var(--muted);
              font-size: 12px;
              font-weight: 500;
            }}
            .hero-summary-card span {{
              font-size: 16px;
              line-height: 1.5;
            }}
            .hero-summary-card.wide {{
              grid-column: 1 / -1;
              background: linear-gradient(135deg, rgba(31, 93, 83, 0.1), rgba(255, 249, 242, 0.95));
            }}
            .hero-note {{
              margin: 0;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }}
            .panel {{
              background: var(--paper);
              border: 1px solid var(--line);
              border-radius: 24px;
              padding: 18px;
              box-shadow: var(--shadow);
              backdrop-filter: blur(10px);
            }}
            .layout {{
              display: grid;
              grid-template-columns: 380px minmax(0, 1fr);
              gap: 18px;
              align-items: start;
            }}
            .stack {{
              display: grid;
              gap: 18px;
            }}
            .detail-column {{
              min-width: 0;
            }}
            .panel-head {{
              display: flex;
              justify-content: space-between;
              align-items: center;
              gap: 12px;
              margin-bottom: 14px;
            }}
            .panel-tools {{
              display: flex;
              align-items: center;
              gap: 10px;
              flex-wrap: wrap;
            }}
            .panel h2 {{
              margin: 0;
              font-size: 19px;
            }}
            .panel-intro {{
              margin: 0 0 14px;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }}
            .mini {{
              color: var(--muted);
              font-size: 13px;
            }}
            .composer {{
              display: grid;
              gap: 12px;
            }}
            .field {{
              display: grid;
              gap: 6px;
            }}
            .composer-row {{
              display: grid;
              grid-template-columns: 1fr;
            }}
            .composer-actions {{
              display: grid;
              grid-template-columns: 120px minmax(0, 1fr);
              gap: 10px;
            }}
            label {{
              color: var(--muted);
              font-size: 13px;
            }}
            .field-hint {{
              margin: 0;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }}
            input, button, .button-link {{
              width: 100%;
              font: inherit;
              border-radius: 999px;
            }}
            input {{
              border: 1px solid var(--line);
              background: #fffdf9;
              padding: 18px 20px;
              color: var(--text);
            }}
            input:focus-visible,
            button:focus-visible,
            .button-link:focus-visible,
            a:focus-visible,
            summary:focus-visible {{
              outline: 2px solid rgba(31, 93, 83, 0.18);
              outline-offset: 3px;
            }}
            input:focus-visible {{
              border-color: rgba(31, 93, 83, 0.4);
            }}
            button,
            .button-link {{
              border: none;
              padding: 14px 16px;
              min-height: 48px;
              display: inline-flex;
              align-items: center;
              justify-content: center;
              cursor: pointer;
              background: var(--accent);
              color: #f7faf8;
              text-decoration: none;
              text-align: center;
              line-height: 1.35;
              transition: transform 120ms ease, background 120ms ease, opacity 120ms ease;
            }}
            button:hover,
            .button-link:hover {{
              background: var(--accent-strong);
              transform: translateY(-1px);
            }}
            button.secondary,
            .button-link.secondary {{
              background: #dfceb3;
              color: #2f261d;
            }}
            button.ghost,
            .button-link.ghost {{
              background: transparent;
              border: 1px solid rgba(31, 93, 83, 0.22);
              color: var(--accent-strong);
            }}
            button.warn,
            .button-link.warn {{
              background: var(--gold);
            }}
            button.danger,
            .button-link.danger {{
              background: var(--danger);
            }}
            button:disabled {{
              opacity: 0.48;
              cursor: not-allowed;
              transform: none;
            }}
            button[aria-busy="true"] {{
              opacity: 0.82;
              cursor: progress;
            }}
            .status-line {{
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
              align-items: center;
            }}
            .status-chip {{
              display: inline-flex;
              align-items: center;
              width: fit-content;
              padding: 7px 12px;
              border-radius: 999px;
              font-size: 13px;
              background: var(--accent-soft);
              color: var(--accent-strong);
            }}
            .status-chip.waiting {{
              background: rgba(176, 122, 24, 0.12);
              color: #875f11;
            }}
            .status-chip.done {{
              background: rgba(47, 124, 83, 0.12);
              color: var(--ok);
            }}
            .status-chip.fail {{
              background: rgba(161, 69, 52, 0.12);
              color: var(--danger);
            }}
            .overview-strip {{
              display: grid;
              grid-template-columns: repeat(4, minmax(0, 1fr));
              gap: 12px;
            }}
            .overview-card {{
              display: grid;
              gap: 8px;
              min-width: 0;
              padding: 16px;
              border-radius: 20px;
              border: 1px solid var(--line);
              background: rgba(255, 251, 246, 0.9);
              box-shadow: 0 14px 32px rgba(58, 40, 18, 0.08);
            }}
            .overview-card.highlight {{
              grid-column: span 2;
              background: linear-gradient(135deg, rgba(31, 93, 83, 0.1), rgba(255, 249, 242, 0.96));
            }}
            .overview-card strong {{
              display: block;
              color: var(--muted);
              font-size: 12px;
              font-weight: 500;
            }}
            .overview-card span {{
              display: block;
              font-size: 28px;
              line-height: 1.1;
            }}
            .overview-card p {{
              margin: 0;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }}
            .task-toolbar {{
              display: grid;
              gap: 10px;
            }}
            .filter-row, .advanced-links {{
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
            }}
            .search-row {{
              display: grid;
              grid-template-columns: minmax(0, 1fr) auto;
              gap: 8px;
              align-items: center;
            }}
            .search-row button {{
              width: auto;
            }}
            .pill {{
              padding: 9px 14px;
              border-radius: 999px;
              border: 1px solid rgba(31, 93, 83, 0.16);
              background: transparent;
              color: var(--accent-strong);
            }}
            .pill.active {{
              background: var(--accent);
              color: #f7faf8;
              border-color: transparent;
            }}
            .tiny-button {{
              width: auto;
              padding: 9px 13px;
              font-size: 13px;
              background: #efe3ce;
              color: #342a20;
            }}
            .advanced-shell {{
              border-radius: 18px;
              border: 1px dashed rgba(65, 48, 27, 0.16);
              padding: 10px 12px;
              background: rgba(255, 253, 249, 0.56);
            }}
            .advanced-shell summary {{
              cursor: pointer;
              color: var(--muted);
              font-size: 13px;
            }}
            .advanced-shell[open] {{
              background: rgba(255, 253, 249, 0.92);
            }}
            .advanced-shell[open] .advanced-links {{
              margin-top: 10px;
            }}
            .advanced-links a {{
              color: var(--accent-strong);
              text-decoration: none;
              border-bottom: 1px solid rgba(31, 93, 83, 0.22);
              font-size: 13px;
            }}
            .task-list {{
              display: grid;
              align-content: start;
              grid-auto-rows: max-content;
              gap: 10px;
            }}
            .task-card {{
              display: grid;
              align-content: start;
              gap: 8px;
              width: 100%;
              padding: 14px 15px;
              color: var(--text);
              font: inherit;
              border-radius: 20px;
              border: 1px solid var(--line);
              background: #fffdf9;
              min-width: 0;
              position: relative;
              isolation: isolate;
              cursor: pointer;
              appearance: none;
              text-align: left;
              transition: transform 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
            }}
            .task-card:hover {{
              background: #fffdf9;
              color: var(--text);
              transform: translateY(-1px);
              border-color: rgba(31, 93, 83, 0.35);
              box-shadow: 0 12px 26px rgba(58, 40, 18, 0.08);
            }}
            .task-card.selected {{
              border-color: rgba(31, 93, 83, 0.45);
              box-shadow: 0 14px 28px rgba(31, 93, 83, 0.11);
              background: linear-gradient(135deg, rgba(31, 93, 83, 0.08), #fffdf9 45%);
            }}
            .task-card.tone-waiting {{
              border-color: rgba(176, 122, 24, 0.26);
            }}
            .task-card.tone-fail {{
              border-color: rgba(161, 69, 52, 0.24);
            }}
            .task-card.tone-done {{
              border-color: rgba(47, 124, 83, 0.24);
            }}
            .task-title {{
              font-size: 16px;
              line-height: 1.45;
              overflow-wrap: anywhere;
            }}
            .task-eyebrow {{
              color: var(--muted);
              font-size: 12px;
            }}
            .task-reason {{
              color: #3a3026;
              font-size: 13px;
              line-height: 1.6;
            }}
            .task-meta {{
              color: var(--muted);
              font-size: 12px;
              line-height: 1.6;
              overflow-wrap: anywhere;
            }}
            .progress-track {{
              width: 100%;
              height: 10px;
              border-radius: 999px;
              background: rgba(31, 93, 83, 0.08);
              overflow: hidden;
            }}
            .progress-fill {{
              height: 100%;
              border-radius: 999px;
              background: linear-gradient(90deg, #2f7c53, #1f5d53);
            }}
            .empty {{
              padding: 22px 18px;
              border-radius: 20px;
              border: 1px dashed rgba(65, 48, 27, 0.18);
              color: var(--muted);
              background: rgba(255, 253, 249, 0.75);
            }}
            .task-list[aria-busy="true"],
            .detail-grid[aria-busy="true"] {{
              opacity: 0.8;
            }}
            .detail-grid {{
              display: grid;
              gap: 18px;
              align-content: start;
            }}
            .workspace-overview {{
              display: grid;
              grid-template-columns: repeat(4, minmax(0, 1fr));
              gap: 10px;
            }}
            .workspace-overview-card {{
              display: grid;
              gap: 6px;
              min-width: 0;
              padding: 14px;
              border-radius: 18px;
              border: 1px solid var(--line);
              background: #fffdf9;
            }}
            .workspace-overview-card.strong {{
              grid-column: span 2;
              background: linear-gradient(135deg, rgba(31, 93, 83, 0.12), rgba(255, 249, 242, 0.96));
            }}
            .workspace-overview-card strong {{
              color: var(--muted);
              font-size: 12px;
              font-weight: 500;
            }}
            .workspace-overview-card span {{
              font-size: 20px;
              line-height: 1.35;
              word-break: break-word;
            }}
            .workspace-overview-card p {{
              margin: 0;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.65;
            }}
            .workspace-layout {{
              display: grid;
              grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.92fr);
              gap: 14px;
              align-items: start;
            }}
            .workspace-stack {{
              display: grid;
              gap: 14px;
            }}
            .summary-block {{
              display: grid;
              gap: 12px;
            }}
            .summary-title {{
              display: grid;
              gap: 8px;
            }}
            .summary-title h3 {{
              margin: 0;
              font-size: 28px;
              line-height: 1.25;
            }}
            .summary-title a {{
              width: fit-content;
              color: var(--accent-strong);
              text-decoration: none;
              border-bottom: 1px solid rgba(31, 93, 83, 0.22);
            }}
            .kv-grid {{
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: 10px;
            }}
            .quick-facts {{
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
            }}
            .fact-pill {{
              display: inline-flex;
              align-items: center;
              padding: 8px 12px;
              border-radius: 999px;
              border: 1px solid var(--line);
              background: #fffdf9;
              color: var(--muted);
              font-size: 12px;
            }}
            .kv {{
              padding: 14px;
              border-radius: 18px;
              border: 1px solid var(--line);
              background: #fffdf9;
            }}
            .kv strong {{
              display: block;
              margin-bottom: 8px;
              font-size: 12px;
              color: var(--muted);
              font-weight: 500;
            }}
            .kv span {{
              word-break: break-word;
              line-height: 1.6;
            }}
            .big-hint {{
              padding: 18px;
              border-radius: 22px;
              border: 1px solid rgba(31, 93, 83, 0.14);
              background: linear-gradient(135deg, rgba(31, 93, 83, 0.08), rgba(255, 249, 242, 0.94));
            }}
            .big-hint strong {{
              display: block;
              margin-bottom: 8px;
              font-size: 13px;
              color: var(--muted);
              font-weight: 500;
            }}
            .big-hint span {{
              font-size: 21px;
              line-height: 1.45;
            }}
            .action-grid {{
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: 10px;
            }}
            .action-grid.single {{
              grid-template-columns: 1fr;
            }}
            .action-grid.compact {{
              grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
            .detail-sections {{
              display: grid;
              gap: 14px;
            }}
            .detail-section {{
              display: grid;
              gap: 12px;
              padding: 16px;
              border-radius: 22px;
              border: 1px solid var(--line);
              background: rgba(255, 253, 249, 0.9);
            }}
            .detail-section-head {{
              display: flex;
              justify-content: space-between;
              align-items: flex-start;
              gap: 12px;
              flex-wrap: wrap;
            }}
            .detail-section-head strong {{
              display: block;
              font-size: 16px;
            }}
            .detail-section-head span {{
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }}
            .section-actions {{
              display: flex;
              flex-wrap: wrap;
              gap: 10px;
            }}
            .section-actions .button-link,
            .section-actions button {{
              width: auto;
              min-width: 132px;
            }}
            .section-hint {{
              margin: 0;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }}
            .section-metrics {{
              display: grid;
              gap: 10px;
            }}
            .metric-item {{
              display: flex;
              justify-content: space-between;
              gap: 16px;
              align-items: flex-start;
              padding-bottom: 10px;
              border-bottom: 1px dashed rgba(65, 48, 27, 0.14);
            }}
            .metric-item:last-child {{
              padding-bottom: 0;
              border-bottom: none;
            }}
            .metric-item strong {{
              font-size: 13px;
              color: var(--muted);
              font-weight: 500;
            }}
            .metric-item span {{
              text-align: right;
              word-break: break-word;
            }}
            .action-empty {{
              padding: 14px 16px;
              border-radius: 18px;
              border: 1px dashed rgba(65, 48, 27, 0.18);
              color: var(--muted);
              background: rgba(255, 253, 249, 0.82);
            }}
            .detail-more {{
              border-radius: 20px;
              border: 1px dashed rgba(65, 48, 27, 0.18);
              padding: 12px 14px;
              background: rgba(255, 253, 249, 0.82);
            }}
            .detail-more summary {{
              cursor: pointer;
              color: var(--muted);
              font-size: 13px;
            }}
            .detail-more[open] {{
              background: #fffdf9;
            }}
            .detail-more[open] .detail-more-grid {{
              margin-top: 12px;
            }}
            .detail-more-grid {{
              display: grid;
              gap: 14px;
            }}
            .utility-grid {{
              display: flex;
              flex-wrap: wrap;
              gap: 10px;
            }}
            .utility-grid button {{
              width: auto;
              min-width: 132px;
            }}
            .latest-box {{
              display: grid;
              gap: 8px;
              padding: 16px;
              border-radius: 20px;
              border: 1px solid var(--line);
              background: #fffdf9;
            }}
            .latest-box strong {{
              font-size: 13px;
              color: var(--muted);
              font-weight: 500;
            }}
            .latest-box p {{
              margin: 0;
              line-height: 1.7;
            }}
            .error-box {{
              border-color: rgba(161, 69, 52, 0.16);
              background: linear-gradient(180deg, rgba(255, 248, 246, 0.96), rgba(255, 252, 249, 0.9));
            }}
            .danger-confirm-box {{
              display: grid;
              gap: 12px;
              padding: 14px;
              border-radius: 18px;
              border: 1px solid rgba(161, 69, 52, 0.24);
              background: rgba(255, 247, 244, 0.88);
            }}
            .danger-confirm-copy {{
              margin: 0;
              color: #6d4d45;
              font-size: 13px;
              line-height: 1.7;
            }}
            .danger-confirm-actions {{
              display: flex;
              flex-wrap: wrap;
              gap: 10px;
            }}
            .danger-inline-note {{
              margin: 0;
              color: var(--muted);
              font-size: 12px;
              line-height: 1.7;
            }}
            .danger-card {{
              border-color: rgba(161, 69, 52, 0.18);
              background: linear-gradient(180deg, rgba(255, 248, 245, 0.96), rgba(255, 252, 249, 0.92));
            }}
            .danger-card .button-link,
            .danger-card button {{
              width: auto;
            }}
            .article-preview-shell {{
              margin-top: 2px;
              padding: 16px;
              border-radius: 18px;
              border: 1px solid rgba(65, 48, 27, 0.12);
              background: linear-gradient(180deg, rgba(255, 252, 247, 0.98), rgba(247, 242, 233, 0.96));
              overflow: auto;
            }}
            .article-preview-shell img {{
              max-width: 100%;
              height: auto;
            }}
            .article-preview-shell section {{
              margin: 0 auto;
            }}
            .footer-note {{
              color: var(--muted);
              font-size: 12px;
              line-height: 1.7;
            }}
            __ADMIN_NAV_STYLES__
            @media (max-width: 1080px) {{
              .hero-grid {{ grid-template-columns: 1fr; }}
              .overview-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
              .layout {{ grid-template-columns: 1fr; }}
              .workspace-overview {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
              .workspace-overview-card.strong {{ grid-column: span 2; }}
              .workspace-layout {{ grid-template-columns: 1fr; }}
              .action-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            }}
            @media (max-width: 720px) {{
              main {{ padding: 18px 14px 32px; }}
              .hero {{ padding: 18px; }}
              .hero-note {{ font-size: 12px; line-height: 1.6; }}
              .panel {{ padding: 16px; border-radius: 20px; }}
              h1 {{ font-size: 32px; }}
              .hero-summary {{ grid-template-columns: 1fr; }}
              .filter-row {{
                flex-wrap: nowrap;
                overflow-x: auto;
                padding-bottom: 4px;
                scrollbar-width: none;
              }}
              .filter-row::-webkit-scrollbar {{ display: none; }}
              .pill {{ flex: 0 0 auto; white-space: nowrap; }}
              .composer-actions {{ grid-template-columns: 1fr; }}
              .overview-strip {{ grid-template-columns: 1fr; }}
              .overview-card.highlight {{ grid-column: span 1; }}
              .workspace-overview {{ grid-template-columns: 1fr; }}
              .workspace-overview-card.strong {{ grid-column: span 1; }}
              .kv-grid {{ grid-template-columns: 1fr; }}
              .action-grid {{ grid-template-columns: 1fr; }}
              .action-grid.compact {{ grid-template-columns: 1fr; }}
              .detail-section-head {{ flex-direction: column; }}
              .search-row {{ grid-template-columns: 1fr; }}
            }}
          </style>
        </head>
        <body>
          <a class="skip-link" href="#task-region">跳到任务主区</a>
          <main id="main-content">
            <div class="shell">
              <section class="hero">
                <div class="hero-grid">
                  <div class="hero-copy">
                    <span class="badge">PRIMARY CONTROL ROOM</span>
                    <h1>微信文章工厂</h1>
                    <p>贴链接后系统会自动往下跑。左侧只负责选任务，右侧统一处理动作、草稿和预览。</p>
                  </div>
                  <aside class="hero-status-card" aria-label="运行状态">
                    <div class="status-line">
                      <span class="status-chip" id="auto-refresh">自动刷新中</span>
                      <span class="mini">每 4 秒同步一次</span>
                    </div>
                    <p class="hero-status-copy" id="flash-message" role="status" aria-live="polite" aria-atomic="true">准备好了。</p>
                    <div class="hero-summary" aria-label="首屏提示">
                      <div class="hero-summary-card">
                        <strong>唯一主动作</strong>
                        <span>贴链接开始处理</span>
                      </div>
                      <div class="hero-summary-card">
                        <strong>人工介入</strong>
                        <span>只在任务卡住或待审核时出现</span>
                      </div>
                      <div class="hero-summary-card wide">
                        <strong>当前建议</strong>
                        <span id="hero-focus">先贴链接。需要人工判断时，再点下面这排。</span>
                      </div>
                    </div>
                  </aside>
                </div>
                <p class="hero-note">界面按“任务列表 / 当前动作 / 微信草稿 / 成稿预览 / 危险操作”组织，尽量把每一步放在固定位置。</p>
                __ADMIN_SECTION_NAV__
              </section>

              <section class="overview-strip" aria-label="任务概览">
                <article class="overview-card">
                  <strong>当前任务</strong>
                  <span id="overview-total">0</span>
                  <p>主控台里当前可见的任务总数。</p>
                </article>
                <article class="overview-card">
                  <strong>处理中</strong>
                  <span id="metric-active">0</span>
                  <p>系统正在自动推进，不需要额外点击。</p>
                </article>
                <article class="overview-card">
                  <strong>等你处理</strong>
                  <span id="metric-manual">0</span>
                  <p>需要人工审核、重写或补原文的任务。</p>
                </article>
                <article class="overview-card">
                  <strong>已进草稿</strong>
                  <span id="metric-draft">0</span>
                  <p>已经推送进公众号草稿箱的任务。</p>
                </article>
                <article class="overview-card">
                  <strong>失败</strong>
                  <span id="metric-failed">0</span>
                  <p>需要优先查看报错并决定是否重跑。</p>
                </article>
                <article class="overview-card">
                  <strong>今天提交</strong>
                  <span id="metric-today-submitted">0</span>
                  <p>当天新进来的链接量。</p>
                </article>
                <article class="overview-card">
                  <strong>今天进草稿</strong>
                  <span id="metric-today-draft">0</span>
                  <p>当天真正推进到微信草稿箱的任务。</p>
                </article>
                <article class="overview-card highlight">
                  <strong>当前优先</strong>
                  <span id="overview-focus">先贴第一条链接开始。</span>
                  <p id="overview-focus-note">有人工审核或失败任务时，这里会提醒先处理哪一类。</p>
                </article>
              </section>

              <div class="layout">
                <section class="stack" id="task-region">
                  <section class="panel">
                    <div class="panel-head">
                      <h2>开始一个任务</h2>
                      <span class="mini">唯一主动作</span>
                    </div>
                    <p class="panel-intro">只接受微信公众号文章链接。提交后默认一路跑到微信草稿箱；如果这篇文章以前跑过，会直接帮你定位到原任务。</p>
                    <div class="composer">
                      <div class="composer-row field">
                        <label for="ingest-url">微信公众号文章链接</label>
                        <input
                          id="ingest-url"
                          type="url"
                          placeholder="https://mp.weixin.qq.com/s/..."
                          autocomplete="url"
                          aria-describedby="ingest-url-hint"
                        />
                        <p class="field-hint" id="ingest-url-hint">支持直接粘贴手机分享出来的链接。点击“开始处理”后，左侧列表会自动刷新并切到当前任务。</p>
                      </div>
                      <div class="composer-actions">
                        <button id="paste-button" class="secondary" type="button">粘贴</button>
                        <button id="ingest-button" type="button">开始处理</button>
                      </div>
                      <div class="footer-note">默认会一路跑到微信草稿箱。</div>
                    </div>
                  </section>

                  <section class="panel">
                    <div class="panel-head">
                      <h2>任务列表</h2>
                      <div class="panel-tools">
                        <span class="mini" id="task-count">0 个</span>
                        <span class="mini" id="generated-at">刚刚更新</span>
                        <button id="refresh-button" class="tiny-button" type="button">刷新列表</button>
                      </div>
                    </div>
                    <p class="panel-intro">左侧只负责筛选和切换任务。所有操作、草稿入口、预览和删除都在右侧工作区完成。</p>
                    <div class="task-toolbar">
                      <div class="filter-row">
                        <button class="pill active" data-filter="all" data-label="全部" type="button">全部</button>
                        <button class="pill" data-filter="doing" data-label="处理中" type="button">处理中</button>
                        <button class="pill" data-filter="waiting" data-label="等我处理" type="button">等我处理</button>
                        <button class="pill" data-filter="ready" data-label="待推草稿" type="button">待推草稿</button>
                        <button class="pill" data-filter="done" data-label="已进草稿" type="button">已进草稿</button>
                        <button class="pill" data-filter="failed" data-label="失败" type="button">失败</button>
                      </div>
                      <div class="search-row">
                        <input id="task-search" type="search" placeholder="搜标题、链接或任务号" autocomplete="off" />
                        <button id="clear-search-button" class="tiny-button ghost" type="button">清空</button>
                      </div>
                    </div>
                    <div class="task-list" id="task-list" role="listbox" aria-label="最近任务列表" aria-busy="false">
                      <div class="empty">还没有任务。</div>
                    </div>
                  </section>
                </section>

                <section class="stack detail-column">
                  <section class="panel">
                    <div class="panel-head">
                      <h2>工作区</h2>
                      <span class="mini" id="selected-task-code">先点左边任意一条</span>
                    </div>
                    <p class="panel-intro">右侧固定按当前动作、微信草稿、成稿预览、详细信息和危险操作分区展示。</p>
                    <div class="detail-grid" id="task-detail" aria-live="polite" aria-busy="false">
                      <div class="empty">选中一条任务后，这里会告诉你现在到了哪一步，以及下一步该按哪个按钮。</div>
                    </div>
                  </section>
                </section>
              </div>
            </div>
          </main>

          <script>
            const INITIAL_TASK_ID = {json.dumps(task_id, ensure_ascii=False)};
            const ACTIVE = new Set([
              "queued",
              "deduping",
              "fetching_source",
              "source_ready",
              "analyzing_source",
              "searching_related",
              "fetching_related",
              "building_brief",
              "brief_ready",
              "generating",
              "reviewing",
              "pushing_wechat_draft",
            ]);
            const WAITING = new Set(["needs_manual_review", "needs_regenerate", "needs_manual_source"]);
            const READY_TO_PUSH = new Set(["review_passed"]);
            const FAILED = new Set([
              "fetch_failed",
              "analyze_failed",
              "search_failed",
              "brief_failed",
              "generate_failed",
              "review_failed",
              "push_failed",
              "needs_manual_source",
            ]);
            const DONE = new Set(["draft_saved"]);
            const STATUS_LABELS = {{
              queued: "排队中",
              deduping: "去重中",
              fetching_source: "抓原文",
              source_ready: "原文就绪",
              analyzing_source: "分析原文",
              searching_related: "搜同题",
              fetching_related: "抓参考",
              building_brief: "做 brief",
              brief_ready: "brief 就绪",
              generating: "写稿中",
              reviewing: "审稿中",
              review_passed: "已通过",
              pushing_wechat_draft: "推草稿",
              draft_saved: "已进草稿",
              fetch_failed: "抓取失败",
              analyze_failed: "分析失败",
              search_failed: "搜索失败",
              brief_failed: "brief 失败",
              generate_failed: "写稿失败",
              review_failed: "审稿失败",
              push_failed: "推稿失败",
              needs_manual_source: "等人工补原文",
              needs_manual_review: "等人工判断",
              needs_regenerate: "需要重写",
            }};

            const state = {{
              snapshot: null,
              selectedTaskId: INITIAL_TASK_ID,
              filter: "all",
              search: "",
              filterPinned: false,
              detailExpandedByTask: {{}},
              deleteConfirmTaskId: null,
              pendingAction: null,
              isIngesting: false,
              isRefreshing: false,
            }};

            const elements = {{
              flashMessage: document.getElementById("flash-message"),
              autoRefresh: document.getElementById("auto-refresh"),
              heroFocus: document.getElementById("hero-focus"),
              ingestUrl: document.getElementById("ingest-url"),
              ingestButton: document.getElementById("ingest-button"),
              pasteButton: document.getElementById("paste-button"),
              refreshButton: document.getElementById("refresh-button"),
              taskSearch: document.getElementById("task-search"),
              clearSearchButton: document.getElementById("clear-search-button"),
              taskCount: document.getElementById("task-count"),
              taskList: document.getElementById("task-list"),
              selectedTaskCode: document.getElementById("selected-task-code"),
              taskDetail: document.getElementById("task-detail"),
              generatedAt: document.getElementById("generated-at"),
              overviewTotal: document.getElementById("overview-total"),
              metricActive: document.getElementById("metric-active"),
              metricManual: document.getElementById("metric-manual"),
              metricDraft: document.getElementById("metric-draft"),
              metricFailed: document.getElementById("metric-failed"),
              metricTodaySubmitted: document.getElementById("metric-today-submitted"),
              metricTodayDraft: document.getElementById("metric-today-draft"),
              overviewFocus: document.getElementById("overview-focus"),
              overviewFocusNote: document.getElementById("overview-focus-note"),
              filterButtons: Array.from(document.querySelectorAll("[data-filter]")),
            }};

            const escapeHtml = (value) => (value || "")
              .replaceAll("&", "&amp;")
              .replaceAll("<", "&lt;")
              .replaceAll(">", "&gt;")
              .replaceAll('"', "&quot;")
              .replaceAll("'", "&#39;");
            const hydrateArticlePreview = (root, generations) => {{
              if (!root || !Array.isArray(generations)) return;
              root.querySelectorAll("[data-generation-html]").forEach((node) => {{
                const generationId = node.getAttribute("data-generation-html");
                const generation = generations.find((item) => item.generation_id === generationId);
                node.innerHTML = generation?.html_content || '<div class="empty">暂无 HTML 预览。</div>';
              }});
            }};

            const formatDateTime = (value) => {{
              if (!value) return "刚刚";
              const date = new Date(value);
              if (Number.isNaN(date.getTime())) return "刚刚";
              return new Intl.DateTimeFormat("zh-CN", {{
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
              }}).format(date);
            }};
            const formatPercent = (value) => {{
              if (value === null || value === undefined) return "暂无";
              return `${{Math.round(value)}}%`;
            }};

            const statusLabel = (status) => STATUS_LABELS[status] || status || "未知";

            const statusTone = (status) => {{
              if (DONE.has(status)) return "done";
              if (FAILED.has(status)) return "fail";
              if (WAITING.has(status)) return "waiting";
              if (READY_TO_PUSH.has(status)) return "waiting";
              return "";
            }};

            const shorten = (value, limit = 220) => {{
              if (!value) return "";
              return value.length > limit ? `${{value.slice(0, limit)}}…` : value;
            }};

            const compactUrl = (value, limit = 54) => {{
              if (!value) return "";
              try {{
                const parsed = new URL(value);
                const searchSuffix = parsed.search ? "…" : "";
                return shorten(`${{parsed.hostname}}${{parsed.pathname}}${{searchSuffix}}`, limit);
              }} catch (_error) {{
                return shorten(value, limit);
              }}
            }};

            const isWechatArticleUrl = (value) => {{
              try {{
                return new URL(value).hostname === "mp.weixin.qq.com";
              }} catch (_error) {{
                return false;
              }}
            }};

            const setFlashMessage = (message, tone = "") => {{
              elements.flashMessage.textContent = message;
              elements.autoRefresh.className = `status-chip ${{tone}}`.trim();
              elements.autoRefresh.textContent = tone === "fail"
                ? "同步异常"
                : (tone === "waiting" ? "正在更新" : "自动刷新中");
            }};
            const setRegionsBusy = (busy) => {{
              elements.taskList.setAttribute("aria-busy", busy ? "true" : "false");
              elements.taskDetail.setAttribute("aria-busy", busy ? "true" : "false");
            }};
            const setButtonBusy = (button, busy, pendingLabel = "处理中…") => {{
              if (!button) return;
              if (!button.dataset.defaultLabel) {{
                button.dataset.defaultLabel = button.textContent.trim();
              }}
              button.disabled = busy;
              button.setAttribute("aria-busy", busy ? "true" : "false");
              button.textContent = busy ? pendingLabel : button.dataset.defaultLabel;
            }};
            const withStaticButtonBusy = async (button, pendingLabel, work) => {{
              if (!button || button.disabled) return;
              setButtonBusy(button, true, pendingLabel);
              try {{
                await work();
              }} finally {{
                setButtonBusy(button, false);
              }}
            }};
            const actionBusyLabel = (action, fallback) => {{
              const labels = {{
                retry: "重跑中…",
                approve: "通过中…",
                reject: "退回中…",
                "push-draft": "推送中…",
                delete: "删除中…",
              }};
              return labels[action] || `${{fallback}}中…`;
            }};
            const setPendingAction = (action, taskId) => {{
              state.pendingAction = {{ action, taskId }};
              renderTaskDetail();
            }};
            const clearPendingAction = () => {{
              state.pendingAction = null;
              renderTaskDetail();
            }};
            const armDeleteConfirm = (taskId) => {{
              state.deleteConfirmTaskId = taskId;
              renderTaskDetail();
            }};
            const clearDeleteConfirm = (taskId = null, rerender = true) => {{
              if (taskId && state.deleteConfirmTaskId !== taskId) return;
              state.deleteConfirmTaskId = null;
              if (rerender) {{
                renderTaskDetail();
              }}
            }};
            const setDetailExpanded = (taskId, expanded) => {{
              if (!taskId) return;
              if (expanded) {{
                state.detailExpandedByTask[taskId] = true;
                return;
              }}
              delete state.detailExpandedByTask[taskId];
            }};
            const isDetailExpanded = (taskId) => Boolean(taskId && state.detailExpandedByTask[taskId]);
            const scrollTaskDetailIntoView = () => {{
              if (!window.matchMedia("(max-width: 1080px)").matches) return;
              const panel = elements.taskDetail.closest(".panel");
              if (!panel) return;
              window.requestAnimationFrame(() => {{
                panel.scrollIntoView({{ behavior: "smooth", block: "start" }});
              }});
            }};
            const scrollPreviewIntoView = () => {{
              const preview = document.getElementById("preview-section");
              if (!preview) return;
              window.requestAnimationFrame(() => {{
                preview.scrollIntoView({{ behavior: "smooth", block: "start" }});
              }});
            }};

            const copyText = async (label, value) => {{
              try {{
                await navigator.clipboard.writeText(value);
                setFlashMessage(`${{label}}已复制。`);
              }} catch (_error) {{
                setFlashMessage(`复制${{label}}失败，请手动复制。`, "waiting");
              }}
            }};

            const nextStepText = (task) => {{
              if (!task) return "先在左边点一条任务。";
              if (task.error) return `先处理这个报错：${{task.error}}`;
              switch (task.status) {{
                case "queued":
                case "deduping":
                case "fetching_source":
                case "analyzing_source":
                case "searching_related":
                case "fetching_related":
                case "building_brief":
                case "generating":
                case "reviewing":
                case "pushing_wechat_draft":
                  return "系统在跑，你先等一下。";
                case "brief_ready":
                case "source_ready":
                  return "刚到中间态，系统会继续往下走。";
                case "needs_manual_review":
                  return "现在轮到你。点“通过”或“驳回重写”。";
                case "needs_regenerate":
                  return "点“重新跑一版”，再来一稿。";
                case "review_passed":
                  return "已经合格。点“推草稿”就会进公众号后台。";
                case "draft_saved":
                  return "已经进草稿箱，去公众号后台发布。";
                case "needs_manual_source":
                  return "原文没抓到，先看高级页面补原文。";
                default:
                  if (FAILED.has(task.status)) return "先点“重新跑一版”。还不行再看高级页面。";
                  return "看左边状态，系统会继续更新。";
              }}
            }};

            const currentTasks = () => state.snapshot?.tasks || [];

            const findSelectedTask = () => {{
              if (!state.selectedTaskId) return null;
              const workspace = state.snapshot?.workspace;
              if (workspace && workspace.task_id === state.selectedTaskId) return workspace;
              return currentTasks().find((item) => item.task_id === state.selectedTaskId) || null;
            }};

            const matchesSearch = (task) => {{
              if (!state.search) return true;
              const needle = state.search.toLowerCase();
              return [
                task.title || "",
                task.source_url || "",
                task.task_code || "",
              ].some((value) => value.toLowerCase().includes(needle));
            }};

            const matchesFilter = (task, filter = state.filter) => {{
              if (filter === "doing" && !ACTIVE.has(task.status)) return false;
              if (filter === "waiting" && !WAITING.has(task.status)) return false;
              if (filter === "ready" && !READY_TO_PUSH.has(task.status)) return false;
              if (filter === "done" && !DONE.has(task.status)) return false;
              if (filter === "failed" && !FAILED.has(task.status)) return false;
              return matchesSearch(task);
            }};

            const filteredTasks = () => currentTasks().filter((task) => matchesFilter(task));
            const filterCountsFromVisibleTasks = () => {{
              const searchableTasks = currentTasks().filter(matchesSearch);
              return {{
                all: searchableTasks.length,
                doing: searchableTasks.filter((task) => ACTIVE.has(task.status)).length,
                waiting: searchableTasks.filter((task) => WAITING.has(task.status)).length,
                ready: searchableTasks.filter((task) => READY_TO_PUSH.has(task.status)).length,
                done: searchableTasks.filter((task) => DONE.has(task.status)).length,
                failed: searchableTasks.filter((task) => FAILED.has(task.status)).length,
              }};
            }};

            const alignSelectedTaskToVisibleTasks = () => {{
              const visibleTasks = filteredTasks();
              if (!visibleTasks.length) {{
                if (!state.selectedTaskId) {{
                  return {{ changed: false, needsReload: false }};
                }}
                state.selectedTaskId = null;
                syncUrl();
                return {{ changed: true, needsReload: false }};
              }}
              if (visibleTasks.some((item) => item.task_id === state.selectedTaskId)) {{
                return {{ changed: false, needsReload: false }};
              }}
              const previousSelectedTaskId = state.selectedTaskId;
              state.selectedTaskId = visibleTasks[0].task_id;
              syncUrl();
              return {{
                changed: true,
                needsReload: state.selectedTaskId !== previousSelectedTaskId,
              }};
            }};

            const suggestFilter = (summary) => {{
              const visibleCounts = filterCountsFromVisibleTasks();
              if (visibleCounts.waiting > 0) return "waiting";
              if (visibleCounts.ready > 0) return "ready";
              if (visibleCounts.doing > 0) return "doing";
              if (visibleCounts.failed > 0) return "failed";
              if (visibleCounts.done > 0) return "done";
              if (!summary) return "all";
              if (summary.filtered_manual > 0) return "waiting";
              if (summary.filtered_review_passed > 0) return "ready";
              if (summary.filtered_active > 0) return "doing";
              if (summary.filtered_failed > 0) return "failed";
              if (summary.filtered_draft_saved > 0) return "done";
              return "all";
            }};
            const focusSummary = (summary) => {{
              if (!summary) {{
                return {{
                  headline: "先贴第一条链接开始。",
                  note: "新任务会自动排队，主控台会把当前任务切到右侧详情。",
                }};
              }}
              if (summary.filtered_manual > 0) {{
                return {{
                  headline: `先处理 ${{summary.filtered_manual}} 条等你判断的任务`,
                  note: "优先看“等我处理”，避免已写完的任务卡在人工审核或重写环节。",
                }};
              }}
              if (summary.filtered_review_passed > 0) {{
                return {{
                  headline: `有 ${{summary.filtered_review_passed}} 条待推草稿任务`,
                  note: "这些任务已经审稿通过，下一步是推到微信草稿箱，不再算进“等我处理”。",
                }};
              }}
              if (summary.filtered_failed > 0) {{
                return {{
                  headline: `有 ${{summary.filtered_failed}} 条失败任务待处理`,
                  note: "先打开失败任务看报错，再决定重跑还是去高级页面补数据。",
                }};
              }}
              if (summary.filtered_active > 0) {{
                return {{
                  headline: `系统正在自动推进 ${{summary.filtered_active}} 条任务`,
                  note: "当前以观察为主，右侧详情会持续更新到最新状态。",
                }};
              }}
              if (summary.filtered_draft_saved > 0) {{
                return {{
                  headline: `已有 ${{summary.filtered_draft_saved}} 条任务进草稿`,
                  note: "可以去公众号后台检查排版、补图和正式发布。",
                }};
              }}
              return {{
                headline: summary.today_submitted > 0 ? "今天已经有任务进来，可以从列表继续看。" : "先贴第一条链接开始。",
                note: "提交新链接后，系统会按既定流程自动往下跑到草稿箱。",
              }};
            }};

            const appUrl = (path, params = null) => {{
              const url = new URL(path, window.location.origin);
              if (params) {{
                Object.entries(params).forEach(([key, value]) => {{
                  if (value !== null && value !== undefined && value !== "") {{
                    url.searchParams.set(key, String(value));
                  }}
                }});
              }}
              return url.toString();
            }};

            const syncUrl = () => {{
              try {{
                const url = new URL(window.location.pathname + window.location.search, window.location.origin);
                if (state.selectedTaskId) {{
                  url.searchParams.set("task_id", state.selectedTaskId);
                }} else {{
                  url.searchParams.delete("task_id");
                }}
                window.history.replaceState({{}}, "", url);
              }} catch (_error) {{
                // Browsers may block replaceState when the current URL includes Basic Auth credentials.
              }}
            }};

            const renderSummary = () => {{
              const summary = state.snapshot?.summary;
              if (!summary) return;
              const focus = focusSummary(summary);
              elements.overviewTotal.textContent = summary.filtered_total;
              elements.metricActive.textContent = summary.filtered_active;
              elements.metricManual.textContent = summary.filtered_manual;
              elements.metricDraft.textContent = summary.filtered_draft_saved;
              elements.metricFailed.textContent = summary.filtered_failed;
              elements.metricTodaySubmitted.textContent = summary.today_submitted;
              elements.metricTodayDraft.textContent = summary.today_draft_saved;
              elements.generatedAt.textContent = `${{formatDateTime(summary.generated_at)}} 更新`;
              elements.heroFocus.textContent = focus.headline;
              elements.overviewFocus.textContent = focus.headline;
              elements.overviewFocusNote.textContent = `${{focus.note}} 审稿通过率 ${{formatPercent(summary.today_review_success_rate)}}，推稿成功率 ${{formatPercent(summary.today_auto_push_success_rate)}}。`;
              const counts = filterCountsFromVisibleTasks();
              elements.filterButtons.forEach((button) => {{
                const label = button.dataset.label || button.textContent || "";
                const count = counts[button.dataset.filter] ?? 0;
                button.textContent = `${{label}} ${{count}}`;
              }});
            }};

            const renderTaskList = () => {{
              const tasks = filteredTasks();
              elements.taskCount.textContent = `${{tasks.length}} 个`;
              if (!tasks.length) {{
                const emptyText = state.search
                  ? "没有找到。点“清空”试试。"
                  : (state.filter === "all" ? "这里还没有任务。" : "当前筛选下没有任务。可以点“全部”看看。");
                elements.taskList.innerHTML = `<div class="empty">${{emptyText}}</div>`;
                return;
              }}
              elements.taskList.innerHTML = tasks.map((task) => {{
                const selected = task.task_id === state.selectedTaskId ? "selected" : "";
                const tone = statusTone(task.status);
                const toneClass = tone ? `tone-${{tone}}` : "";
                const title = escapeHtml(task.title || task.source_url || "未命名任务");
                const meta = escapeHtml(compactUrl(task.source_url || "", 60) || task.task_code);
                const nextStep = escapeHtml(shorten(nextStepText(task), 54));
                const created = formatDateTime(task.created_at);
                const updated = formatDateTime(task.updated_at);
                const selectedAttr = task.task_id === state.selectedTaskId ? "true" : "false";
                const summaryTone = WAITING.has(task.status)
                  ? "需要你处理"
                  : (READY_TO_PUSH.has(task.status) ? "待推草稿" : (FAILED.has(task.status) ? "需要修复" : (DONE.has(task.status) ? "已完成" : "自动处理中")));
                return `
                  <button
                    type="button"
                    class="task-card ${{selected}} ${{toneClass}}"
                    data-task-id="${{task.task_id}}"
                    role="option"
                    aria-selected="${{selectedAttr}}"
                    aria-controls="task-detail"
                  >
                    <div class="status-line">
                      <span class="status-chip ${{statusTone(task.status)}}">${{statusLabel(task.status)}}</span>
                      <span class="task-eyebrow">${{summaryTone}}</span>
                    </div>
                    <div class="task-title">${{title}}</div>
                    <div class="task-reason">${{nextStep}}</div>
                    <div class="progress-track"><div class="progress-fill" style="width:${{Math.max(task.progress || 0, 4)}}%"></div></div>
                    <div class="task-meta">${{meta}}</div>
                    <div class="task-meta">进度 ${{task.progress}}% · 创建：${{created}} · 更新：${{updated}}</div>
                    <div class="task-meta">任务号：${{escapeHtml(task.task_code)}}</div>
                  </button>
                `;
              }}).join("");
            }};

            const renderTaskDetail = () => {{
              const task = findSelectedTask();
              if (!task) {{
                elements.selectedTaskCode.textContent = "先点左边任意一条";
                const emptyDetail = filteredTasks().length
                  ? "选中一条任务后，这里会告诉你现在到了哪一步，以及下一步该按哪个按钮。"
                  : (state.search ? "当前搜索没有找到任务。换个关键词，或者点“全部”再看。" : "当前筛选下没有任务。换个筛选看看。");
                elements.taskDetail.innerHTML = `<div class="empty">${{emptyDetail}}</div>`;
                return;
              }}
              elements.selectedTaskCode.textContent = task.task_code || task.task_id;
              const workspace = state.snapshot?.workspace && state.snapshot.workspace.task_id === task.task_id
                ? state.snapshot.workspace
                : null;
              const latestGeneration = workspace?.generations?.[0] || null;
              const latestDecision = latestGeneration?.review?.final_decision || latestGeneration?.status || "暂无";
              const rawSourceUrl = task.source_url || "";
              const sourceUrl = escapeHtml(rawSourceUrl);
              const sourceLabel = escapeHtml(compactUrl(rawSourceUrl, 80));
              const title = escapeHtml(task.title || workspace?.source_article?.title || "未命名任务");
              const hint = escapeHtml(nextStepText(task));
              const digest = escapeHtml(latestGeneration?.digest || "这里会显示最新一稿的摘要。");
              const rawMediaId = task.wechat_media_id || workspace?.wechat_media_id || "";
              const rawDraftUrl = workspace?.wechat_draft_url || task.wechat_draft_url || "";
              const rawDraftHint = workspace?.wechat_draft_url_hint || task.wechat_draft_url_hint || "";
              const rawDraftDirect = Boolean(workspace?.wechat_draft_url_direct || task.wechat_draft_url_direct);
              const mediaId = escapeHtml(rawMediaId || "还没有");
              const draftUrl = escapeHtml(rawDraftUrl);
              const draftHint = escapeHtml(rawDraftHint || "还没有微信草稿记录。");
              const draftLinkLabel = rawDraftDirect ? "打开微信草稿" : "打开公众号后台";
              const deleteArmed = state.deleteConfirmTaskId === task.task_id;
              const previewAvailable = Boolean(latestGeneration?.generation_id);
              const canRetry = !ACTIVE.has(task.status);
              const canApprove = task.status === "needs_manual_review";
              const canReject = ["needs_manual_review", "review_passed"].includes(task.status);
              const canPush = task.status === "review_passed";
              const actionButtons = [];
              if (canRetry) {{
                actionButtons.push({{
                  id: "retry-button",
                  action: "retry",
                  klass: "secondary",
                  label: task.status === "draft_saved" ? "再来一版" : "重新跑一版",
                }});
              }}
              if (canApprove) {{
                actionButtons.push({{
                  id: "approve-button",
                  action: "approve",
                  klass: "",
                  label: "通过",
                }});
              }}
              if (canReject) {{
                actionButtons.push({{
                  id: "reject-button",
                  action: "reject",
                  klass: "warn",
                  label: "驳回重写",
                }});
              }}
              if (canPush) {{
                actionButtons.push({{
                  id: "push-button",
                  action: "push-draft",
                  klass: "ghost",
                  label: "推草稿",
                }});
              }}
              const actionGridClass = actionButtons.length === 1
                ? " single"
                : (actionButtons.length === 2 ? " compact" : "");
              const actionHtml = actionButtons.length
                ? `<div class="action-grid${{actionGridClass}}">${{actionButtons.map((button) => `
                    <button
                      type="button"
                      id="${{button.id}}"
                      class="${{button.klass}}"
                      ${{state.pendingAction?.taskId === task.task_id ? "disabled" : ""}}
                      aria-busy="${{state.pendingAction?.taskId === task.task_id && state.pendingAction?.action === button.action ? "true" : "false"}}"
                    >${{state.pendingAction?.taskId === task.task_id && state.pendingAction?.action === button.action ? actionBusyLabel(button.action, button.label) : button.label}}</button>
                  `).join("")}}</div>`
                : '<div class="action-empty">现在先不用点按钮，等系统自己跑完就行。</div>';
              const visibleError = escapeHtml(shorten(task.error || "", 280));
              const sourceLink = rawSourceUrl
                ? `<a href="${{sourceUrl}}" title="${{sourceUrl}}" target="_blank" rel="noreferrer">${{sourceLabel}}</a>`
                : "";
              const taskCode = escapeHtml(task.task_code || task.task_id);
              const latestTitle = escapeHtml(latestGeneration?.title || "还没有生成稿件");
              const latestPromptVersion = escapeHtml(latestGeneration?.prompt_version || "未记录 Prompt 版本");
              const draftState = rawMediaId
                ? (rawDraftDirect ? "已有直达草稿" : "已记录后台入口")
                : "还没进草稿";
              const utilityButtons = [
                `<button type="button" id="copy-task-id" class="tiny-button">复制任务号</button>`,
                rawSourceUrl ? `<button type="button" id="copy-source-url" class="tiny-button">复制原文链接</button>` : "",
                previewAvailable ? `<button type="button" id="jump-preview" class="tiny-button">定位预览</button>` : "",
              ].filter(Boolean).join("");
              elements.taskDetail.innerHTML = `
                <div class="summary-block">
                  <div class="summary-title">
                    <div class="status-line">
                      <span class="status-chip ${{statusTone(task.status)}}">${{statusLabel(task.status)}}</span>
                      <span class="mini">进度 ${{task.progress}}%</span>
                    </div>
                    <h3>${{title}}</h3>
                    ${{sourceLink}}
                  </div>
                  <div class="big-hint">
                    <strong>现在该做什么</strong>
                    <span>${{hint}}</span>
                  </div>
                </div>

                <div class="workspace-overview">
                  <article class="workspace-overview-card strong">
                    <strong>当前动作</strong>
                    <span>${{hint}}</span>
                    <p>${{WAITING.has(task.status)
                      ? "这条任务已经等你处理，右侧动作区只保留当前最相关的按钮。"
                      : (READY_TO_PUSH.has(task.status)
                        ? "这条任务已经审稿通过，下一步是推到微信草稿箱。"
                        : "系统还会继续往下推进，先关注状态变化和成稿内容。")}}</p>
                  </article>
                  <article class="workspace-overview-card">
                    <strong>任务状态</strong>
                    <span>${{statusLabel(task.status)}}</span>
                    <p>进度 ${{task.progress}}%${{WAITING.has(task.status) ? "，当前需要人工介入。" : (READY_TO_PUSH.has(task.status) ? "，当前可以推草稿。" : "，当前不用额外操作。")}}</p>
                  </article>
                  <article class="workspace-overview-card">
                    <strong>最近更新</strong>
                    <span>${{formatDateTime(task.updated_at)}}</span>
                    <p>创建时间 ${{formatDateTime(task.created_at)}}，任务号 ${{taskCode}}</p>
                  </article>
                  <article class="workspace-overview-card">
                    <strong>草稿状态</strong>
                    <span>${{escapeHtml(rawMediaId ? "已生成" : "未生成")}}</span>
                    <p>${{escapeHtml(draftState)}}${{rawDraftUrl ? ` · ${{compactUrl(rawDraftUrl, 42)}}` : ""}}</p>
                  </article>
                </div>

                <div class="workspace-layout">
                  <section class="detail-section" id="preview-section">
                    <div class="detail-section-head">
                      <div>
                        <strong>成稿预览</strong>
                        <span>主工作区只放最近一版 HTML 成稿，先在这里看排版，再去公众号后台补细节。</span>
                      </div>
                    </div>
                    ${{previewAvailable
                      ? `<div class="article-preview-shell" data-generation-html="${{escapeHtml(latestGeneration.generation_id)}}"></div>`
                      : '<div class="empty">还没有生成稿件，所以这里暂时没有预览。</div>'}}
                    ${{previewAvailable ? `<div class="latest-box"><strong>最新一稿</strong><p>${{latestTitle}}</p><p class="mini">${{latestPromptVersion}} · ${{escapeHtml(latestDecision)}}</p><p>${{digest}}</p></div>` : ""}}
                  </section>

                  <div class="workspace-stack">
                    <section class="detail-section">
                      <div class="detail-section-head">
                        <div>
                          <strong>当前动作</strong>
                          <span>这里只放当前最相关的操作，避免把按钮散在各个区域。</span>
                        </div>
                      </div>
                      ${{actionHtml}}
                      <div class="utility-grid">
                        ${{utilityButtons}}
                      </div>
                      <div class="section-metrics">
                        <div class="metric-item"><strong>版本结论</strong><span>${{escapeHtml(latestDecision)}}</span></div>
                        <div class="metric-item"><strong>最新版本</strong><span>${{latestTitle}}</span></div>
                        <div class="metric-item"><strong>参考文章</strong><span>${{task.related_article_count || 0}} 篇</span></div>
                      </div>
                    </section>

                    <section class="detail-section">
                      <div class="detail-section-head">
                        <div>
                          <strong>微信草稿</strong>
                          <span>入口、media_id 和说明都收在这里，避免在预览区重复出现。</span>
                        </div>
                        <div class="section-actions">
                          ${{rawDraftUrl ? `<a href="${{draftUrl}}" target="_blank" rel="noreferrer" class="button-link ghost">${{escapeHtml(draftLinkLabel)}}</a>` : ""}}
                          ${{rawDraftUrl ? `<button type="button" id="copy-draft-url" class="secondary">复制草稿入口</button>` : ""}}
                          ${{rawMediaId ? `<button type="button" id="copy-media-id" class="secondary">复制 media_id</button>` : ""}}
                        </div>
                      </div>
                      <div class="section-metrics">
                        <div class="metric-item"><strong>草稿状态</strong><span>${{escapeHtml(draftState)}}</span></div>
                        <div class="metric-item"><strong>草稿 media_id</strong><span>${{mediaId}}</span></div>
                        <div class="metric-item"><strong>草稿入口</strong><span>${{escapeHtml(rawDraftUrl || "还没有")}}</span></div>
                      </div>
                      <p class="section-hint">${{draftHint}}</p>
                    </section>

                    ${{task.error ? `<section class="detail-section error-box"><div class="detail-section-head"><div><strong>报错</strong><span>先看这条报错，再决定是重跑还是去高级页面补数据。</span></div></div><p class="section-hint">${{visibleError}}</p></section>` : ""}}
                  </div>
                </div>

                <details class="detail-more" ${{isDetailExpanded(task.task_id) ? "open" : ""}}>
                  <summary>详细信息</summary>
                  <div class="detail-more-grid">
                    <div class="kv-grid">
                      <div class="kv"><strong>任务号</strong><span>${{taskCode}}</span></div>
                      <div class="kv"><strong>原文链接</strong><span>${{escapeHtml(rawSourceUrl || "还没有")}}</span></div>
                      <div class="kv"><strong>作者</strong><span>${{escapeHtml(workspace?.source_article?.author || "未知")}}</span></div>
                      <div class="kv"><strong>源文摘要</strong><span>${{escapeHtml(workspace?.source_article?.summary || "暂无")}}</span></div>
                      <div class="kv"><strong>新角度</strong><span>${{escapeHtml(workspace?.brief?.new_angle || "暂无")}}</span></div>
                      <div class="kv"><strong>定位</strong><span>${{escapeHtml(workspace?.brief?.positioning || "暂无")}}</span></div>
                    </div>
                  </div>
                </details>

                <section class="detail-section danger-card">
                  <div class="detail-section-head">
                    <div>
                      <strong>危险操作</strong>
                      <span>如果这条任务已经不需要了，可以彻底删除。删除后任务、生成稿、草稿记录和审计关联都会一起清理。</span>
                    </div>
                    <div class="section-actions">
                      <button
                        type="button"
                        id="delete-task-button"
                        class="danger"
                        ${{state.pendingAction?.taskId === task.task_id || deleteArmed ? "disabled" : ""}}
                        aria-busy="${{state.pendingAction?.taskId === task.task_id && state.pendingAction?.action === "delete" ? "true" : "false"}}"
                      >${{state.pendingAction?.taskId === task.task_id && state.pendingAction?.action === "delete" ? actionBusyLabel("delete", "彻底删除") : (deleteArmed ? "删除确认中" : "彻底删除")}}</button>
                    </div>
                  </div>
                  ${{deleteArmed ? `
                    <div class="danger-confirm-box">
                      <p class="danger-confirm-copy">将删除任务 <strong>${{title}}</strong>（${{taskCode}}）以及关联的生成稿、草稿记录和审计索引。这个操作无法恢复。</p>
                      <div class="danger-confirm-actions">
                        <button
                          type="button"
                          id="confirm-delete-task-button"
                          class="danger"
                          ${{state.pendingAction?.taskId === task.task_id ? "disabled" : ""}}
                          aria-busy="${{state.pendingAction?.taskId === task.task_id && state.pendingAction?.action === "delete" ? "true" : "false"}}"
                        >${{state.pendingAction?.taskId === task.task_id && state.pendingAction?.action === "delete" ? actionBusyLabel("delete", "确认彻底删除") : "确认彻底删除"}}</button>
                        <button type="button" id="cancel-delete-task-button" class="ghost" ${{state.pendingAction?.taskId === task.task_id ? "disabled" : ""}}>取消</button>
                      </div>
                    </div>
                  ` : '<p class="danger-inline-note">先点“彻底删除”，页面内会再确认一次，避免误删。</p>'}}
                </section>
              `;

              hydrateArticlePreview(elements.taskDetail, workspace?.generations || []);
              actionButtons.forEach((button) => {{
                elements.taskDetail.querySelector(`#${{button.id}}`)?.addEventListener("click", () => runAction(button.action, task.task_id));
              }});
              elements.taskDetail.querySelector(".detail-more")?.addEventListener("toggle", (event) => {{
                setDetailExpanded(task.task_id, event.currentTarget.open);
              }});
              elements.taskDetail.querySelector("#copy-task-id")?.addEventListener("click", () => copyText("任务号", task.task_code || task.task_id));
              if (rawMediaId) {{
                elements.taskDetail.querySelector("#copy-media-id")?.addEventListener("click", () => copyText("草稿号", rawMediaId));
              }}
              if (rawDraftUrl) {{
                elements.taskDetail.querySelector("#copy-draft-url")?.addEventListener("click", () => copyText("草稿入口", rawDraftUrl));
              }}
              if (rawSourceUrl) {{
                elements.taskDetail.querySelector("#copy-source-url")?.addEventListener("click", () => copyText("原文链接", rawSourceUrl));
              }}
              if (previewAvailable) {{
                elements.taskDetail.querySelector("#jump-preview")?.addEventListener("click", scrollPreviewIntoView);
              }}
              elements.taskDetail.querySelector("#delete-task-button")?.addEventListener("click", () => {{
                armDeleteConfirm(task.task_id);
                setFlashMessage("请再确认一次是否彻底删除当前任务。", "waiting");
              }});
              elements.taskDetail.querySelector("#cancel-delete-task-button")?.addEventListener("click", () => {{
                clearDeleteConfirm(task.task_id);
                setFlashMessage("已取消删除。");
              }});
              elements.taskDetail.querySelector("#confirm-delete-task-button")?.addEventListener("click", () => runAction("delete", task.task_id));
            }};

            const render = () => {{
              renderSummary();
              renderTaskList();
              renderTaskDetail();
              elements.clearSearchButton.disabled = !state.search;
              elements.filterButtons.forEach((button) => {{
                button.classList.toggle("active", button.dataset.filter === state.filter);
              }});
            }};

            const loadSnapshot = async (options = {{}}) => {{
              const {{ showBusy = true }} = options;
              if (showBusy) {{
                setRegionsBusy(true);
              }}
              try {{
                const requestedTaskId = state.selectedTaskId;
                const response = await fetch(appUrl("/admin/api/home-snapshot", {{
                  limit: 18,
                  selected_task_id: state.selectedTaskId,
                }}), {{
                  headers: {{ Accept: "application/json" }},
                }});
                if (!response.ok) {{
                  throw new Error("加载任务列表失败。");
                }}
                state.snapshot = await response.json();
                if (!state.filterPinned) {{
                  state.filter = suggestFilter(state.snapshot.summary);
                }}
                if (!state.selectedTaskId && state.snapshot.tasks.length) {{
                  state.selectedTaskId = state.snapshot.tasks[0].task_id;
                }}
                if (!requestedTaskId && state.selectedTaskId && !state.snapshot.workspace) {{
                  await loadSnapshot(options);
                  return;
                }}
                if (
                  state.selectedTaskId &&
                  !state.snapshot.workspace &&
                  !state.snapshot.tasks.some((item) => item.task_id === state.selectedTaskId)
                ) {{
                  state.selectedTaskId = state.snapshot.tasks[0]?.task_id || null;
                }}
                if (
                  state.deleteConfirmTaskId &&
                  !state.snapshot.tasks.some((item) => item.task_id === state.deleteConfirmTaskId)
                ) {{
                  state.deleteConfirmTaskId = null;
                }}
                const selectionAlignment = alignSelectedTaskToVisibleTasks();
                if (selectionAlignment.needsReload && state.selectedTaskId) {{
                  await loadSnapshot(options);
                  return;
                }}
                syncUrl();
                render();
              }} finally {{
                if (showBusy) {{
                  setRegionsBusy(false);
                }}
              }}
            }};

            const apiRequest = async (url, {{ method = "POST", payload = undefined }} = {{}}) => {{
              const response = await fetch(url, {{
                method,
                headers: {{
                  "Content-Type": "application/json",
                  Accept: "application/json",
                }},
                body: method === "DELETE"
                  ? undefined
                  : (payload ? JSON.stringify(payload) : JSON.stringify({{}})),
              }});
              const text = await response.text();
              let data = {{}};
              if (text) {{
                try {{
                  data = JSON.parse(text);
                }} catch (_error) {{
                  data = {{ detail: text }};
                }}
              }}
              if (!response.ok) {{
                throw new Error(data.detail || "操作失败。");
              }}
              return data;
            }};
            const apiPost = async (url, payload) => apiRequest(url, {{ method: "POST", payload }});
            const apiDelete = async (url) => apiRequest(url, {{ method: "DELETE" }});

            const runAction = async (action, taskId) => {{
              const labels = {{
                retry: "已重新入队。",
                approve: "已通过。",
                reject: "已改成重写。",
                "push-draft": "已推送到微信草稿箱。",
                delete: "任务已彻底删除。",
              }};
              const pendingMessages = {{
                retry: "正在重新跑一版…",
                approve: "正在人工通过…",
                reject: "正在退回重写…",
                "push-draft": "正在推送到微信草稿箱…",
                delete: "正在删除任务…",
              }};
              if (state.pendingAction) return;
              try {{
                if (action === "delete") {{
                  clearDeleteConfirm(taskId, false);
                }}
                setPendingAction(action, taskId);
                setFlashMessage(pendingMessages[action] || "正在处理…", "waiting");
                if (action === "delete") {{
                  await apiDelete(appUrl(`/admin/api/tasks/${{taskId}}`));
                  if (state.selectedTaskId === taskId) {{
                    state.selectedTaskId = null;
                  }}
                }} else {{
                  await apiPost(appUrl(`/admin/api/tasks/${{taskId}}/${{action}}`));
                  state.selectedTaskId = taskId;
                }}
                await loadSnapshot();
                if (action !== "delete") {{
                  scrollTaskDetailIntoView();
                }}
                setFlashMessage(labels[action] || "完成了。", action === "push-draft" || action === "delete" ? "done" : "");
              }} catch (error) {{
                setFlashMessage(error.message || "操作失败。", "fail");
              }} finally {{
                clearPendingAction();
              }}
            }};

            const ingestTask = async () => {{
              const url = elements.ingestUrl.value.trim();
              if (!url) {{
                setFlashMessage("先贴一个微信文章链接。", "waiting");
                elements.ingestUrl.focus();
                return;
              }}
              if (!isWechatArticleUrl(url)) {{
                setFlashMessage("这里只收微信公众号文章链接。", "waiting");
                elements.ingestUrl.focus();
                return;
              }}
              if (state.isIngesting) return;
              try {{
                state.isIngesting = true;
                setButtonBusy(elements.ingestButton, true, "提交中…");
                setButtonBusy(elements.pasteButton, true, "处理中…");
                setFlashMessage("任务已提交，开始排队。", "waiting");
                const data = await apiPost(appUrl("/admin/api/ingest"), {{ url }});
                state.selectedTaskId = data.task_id;
                elements.ingestUrl.value = "";
                await loadSnapshot();
                scrollTaskDetailIntoView();
                if (data.deduped) {{
                  setFlashMessage("这篇文章之前跑过，已经帮你打开原来的任务。", "waiting");
                  return;
                }}
                setFlashMessage("任务已收到，左边会自己刷新。");
              }} catch (error) {{
                setFlashMessage(error.message || "提交失败。", "fail");
              }} finally {{
                state.isIngesting = false;
                setButtonBusy(elements.ingestButton, false);
                setButtonBusy(elements.pasteButton, false);
              }}
            }};

            const refreshVisibleSelection = async () => {{
              clearDeleteConfirm(null, false);
              const selectionAlignment = alignSelectedTaskToVisibleTasks();
              if (selectionAlignment.needsReload && state.selectedTaskId) {{
                await loadSnapshot();
                return;
              }}
              render();
            }};

            elements.filterButtons.forEach((button) => {{
              button.addEventListener("click", () => {{
                state.filterPinned = true;
                state.filter = button.dataset.filter;
                refreshVisibleSelection().catch((error) => setFlashMessage(error.message || "加载任务失败。", "fail"));
              }});
            }});

            elements.taskSearch.addEventListener("input", (event) => {{
              state.search = event.target.value.trim();
              refreshVisibleSelection().catch((error) => setFlashMessage(error.message || "加载任务失败。", "fail"));
            }});

            elements.clearSearchButton.addEventListener("click", () => {{
              state.search = "";
              elements.taskSearch.value = "";
              refreshVisibleSelection().catch((error) => setFlashMessage(error.message || "加载任务失败。", "fail"));
            }});

            elements.taskList.addEventListener("click", (event) => {{
              const card = event.target.closest("[data-task-id]");
              if (!card) return;
              clearDeleteConfirm(null, false);
              state.selectedTaskId = card.dataset.taskId;
              syncUrl();
              loadSnapshot()
                .then(() => scrollTaskDetailIntoView())
                .catch((error) => setFlashMessage(error.message || "加载任务失败。", "fail"));
            }});

            elements.ingestButton.addEventListener("click", ingestTask);
            elements.ingestUrl.addEventListener("keydown", (event) => {{
              if (event.key === "Enter") {{
                event.preventDefault();
                ingestTask();
              }}
            }});

            elements.pasteButton.addEventListener("click", async () => {{
              try {{
                const text = await navigator.clipboard.readText();
                if (text) {{
                  elements.ingestUrl.value = text.trim();
                  elements.ingestUrl.focus();
                  setFlashMessage("已粘贴。");
                }}
              }} catch (_error) {{
                setFlashMessage("请手动粘贴链接。", "waiting");
              }}
            }});

            elements.refreshButton.addEventListener("click", () => {{
              if (state.isRefreshing) return;
              withStaticButtonBusy(elements.refreshButton, "刷新中…", async () => {{
                state.isRefreshing = true;
                setFlashMessage("正在刷新…", "waiting");
                try {{
                  await loadSnapshot();
                  setFlashMessage("已经刷新。");
                }} finally {{
                  state.isRefreshing = false;
                }}
              }}).catch((error) => setFlashMessage(error.message || "刷新失败。", "fail"));
            }});

            const boot = async () => {{
              try {{
                await loadSnapshot();
                setFlashMessage("自动刷新中。");
              }} catch (error) {{
                setFlashMessage(error.message || "页面初始化失败。", "fail");
              }}
              window.setInterval(() => {{
                if (state.pendingAction || state.isIngesting || state.isRefreshing) return;
                loadSnapshot({{ showBusy: false }}).catch(() => setFlashMessage("刷新失败，稍后会再试。", "fail"));
              }}, 4000);
            }};

            boot();
          </script>
        </body>
        </html>
        """
    )
    return (
        html.replace("__ADMIN_NAV_STYLES__", admin_section_nav_styles()).replace(
            "__ADMIN_SECTION_NAV__", admin_section_nav("portal")
        )
    )


@router.get("/admin/console", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def unified_console() -> str:
    html = dedent(
        """\
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>统一控制台</title>
          <style>
            :root {
              --bg: #efe8dd;
              --panel: rgba(255, 251, 246, 0.94);
              --line: #d4c2ad;
              --text: #221a11;
              --muted: #6d6256;
              --accent: #255d52;
              --accent-dark: #173f38;
              --danger: #9e4032;
              --warn: #b07a18;
              --ok: #2f7c53;
              --shadow: 0 18px 48px rgba(55, 40, 21, 0.1);
            }
            * { box-sizing: border-box; }
            body {
              margin: 0;
              line-height: 1.5;
              color: var(--text);
              font-family: "PingFang SC", "Noto Serif SC", serif;
              min-height: 100vh;
              background:
                radial-gradient(circle at top left, rgba(255, 229, 175, 0.5), transparent 26%),
                radial-gradient(circle at bottom right, rgba(178, 222, 208, 0.42), transparent 28%),
                linear-gradient(140deg, #efe8dd 0%, #f6f2ea 44%, #ebe1d2 100%);
            }
            .skip-link {
              position: absolute;
              top: 16px;
              left: 16px;
              transform: translateY(-180%);
              padding: 10px 14px;
              border-radius: 999px;
              background: var(--accent-dark);
              color: #f7faf8;
              text-decoration: none;
              z-index: 20;
              transition: transform 120ms ease;
            }
            .skip-link:focus-visible {
              transform: translateY(0);
            }
            main {
              max-width: 1440px;
              margin: 0 auto;
              padding: 28px 20px 54px;
            }
            .hero {
              display: grid;
              gap: 14px;
              padding: 24px;
              border: 1px solid var(--line);
              border-radius: 28px;
              background: linear-gradient(135deg, rgba(255, 248, 239, 0.94), rgba(249, 244, 236, 0.9));
              box-shadow: var(--shadow);
              backdrop-filter: blur(10px);
              margin-bottom: 20px;
            }
            .hero-grid {
              display: grid;
              grid-template-columns: minmax(0, 1.28fr) minmax(320px, 0.92fr);
              gap: 18px;
              align-items: stretch;
            }
            .hero-copy {
              display: grid;
              gap: 10px;
              align-content: start;
            }
            .eyebrow {
              display: inline-flex;
              width: fit-content;
              padding: 6px 10px;
              border-radius: 999px;
              font-size: 12px;
              letter-spacing: 0.08em;
              background: rgba(37, 93, 82, 0.12);
              color: var(--accent-dark);
            }
            .hero h1 {
              margin: 0;
              font-size: 40px;
              line-height: 1.05;
            }
            .hero p {
              margin: 0;
              max-width: 900px;
              line-height: 1.75;
              color: var(--muted);
            }
            .hero-links {
              display: flex;
              flex-wrap: wrap;
              gap: 10px;
            }
            .hero-links a {
              text-decoration: none;
              color: var(--accent-dark);
              border-bottom: 1px solid rgba(23, 63, 56, 0.25);
            }
            .hero-status-card {
              display: grid;
              gap: 14px;
              padding: 18px;
              border-radius: 24px;
              border: 1px solid rgba(37, 93, 82, 0.12);
              background: linear-gradient(160deg, rgba(255, 252, 247, 0.95), rgba(249, 245, 237, 0.9));
            }
            .hero-status-copy {
              margin: 0;
              font-size: 15px;
              line-height: 1.7;
            }
            .hero-summary {
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: 10px;
            }
            .hero-summary-card {
              display: grid;
              gap: 6px;
              padding: 12px 14px;
              border-radius: 18px;
              border: 1px solid rgba(65, 48, 27, 0.1);
              background: rgba(255, 253, 249, 0.78);
            }
            .hero-summary-card strong {
              color: var(--muted);
              font-size: 12px;
              font-weight: 500;
            }
            .hero-summary-card span {
              font-size: 16px;
              line-height: 1.55;
            }
            .hero-summary-card.wide {
              grid-column: 1 / -1;
              background: linear-gradient(135deg, rgba(37, 93, 82, 0.1), rgba(255, 249, 242, 0.95));
            }
            .overview-strip {
              display: grid;
              grid-template-columns: repeat(4, minmax(0, 1fr));
              gap: 12px;
              margin-bottom: 20px;
            }
            .overview-card {
              display: grid;
              gap: 8px;
              min-width: 0;
              padding: 16px;
              border-radius: 20px;
              border: 1px solid var(--line);
              background: rgba(255, 251, 246, 0.9);
              box-shadow: 0 14px 32px rgba(58, 40, 18, 0.08);
            }
            .overview-card.highlight {
              grid-column: span 2;
              background: linear-gradient(135deg, rgba(37, 93, 82, 0.1), rgba(255, 249, 242, 0.96));
            }
            .overview-card strong {
              color: var(--muted);
              font-size: 12px;
              font-weight: 500;
            }
            .overview-card span {
              display: block;
              font-size: 28px;
              line-height: 1.1;
            }
            .overview-card p {
              margin: 0;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }
            .layout {
              display: grid;
              grid-template-columns: 360px minmax(0, 1fr);
              gap: 18px;
              align-items: start;
            }
            .stack {
              display: grid;
              gap: 16px;
            }
            .panel {
              background: var(--panel);
              border: 1px solid var(--line);
              border-radius: 22px;
              padding: 20px;
              box-shadow: var(--shadow);
              backdrop-filter: blur(8px);
            }
            .panel h2 {
              margin: 0 0 14px;
              font-size: 18px;
            }
            .panel-intro {
              margin: 0 0 14px;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }
            .status {
              display: inline-flex;
              padding: 7px 12px;
              border-radius: 999px;
              background: rgba(37, 93, 82, 0.12);
              color: var(--accent-dark);
              font-size: 12px;
              margin-bottom: 12px;
            }
            .status.warn {
              background: rgba(176, 122, 24, 0.16);
              color: #8a5c12;
            }
            .grid {
              display: grid;
              gap: 10px;
            }
            .grid.two {
              grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .field {
              display: grid;
              gap: 6px;
            }
            .field-hint {
              margin: 0;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }
            label {
              display: block;
              margin-bottom: 6px;
              color: var(--muted);
              font-size: 13px;
            }
            input, select, button {
              width: 100%;
              font: inherit;
              border-radius: 14px;
            }
            input, select {
              padding: 12px 14px;
              background: #fffdf9;
              color: var(--text);
              border: 1px solid var(--line);
            }
            input:focus-visible,
            select:focus-visible,
            button:focus-visible,
            a:focus-visible,
            summary:focus-visible {
              outline: 2px solid rgba(37, 93, 82, 0.18);
              outline-offset: 3px;
            }
            button {
              border: none;
              padding: 12px 16px;
              cursor: pointer;
              background: var(--accent);
              color: #f8fbf7;
              transition: transform 0.12s ease, background 0.12s ease;
            }
            button:hover {
              background: var(--accent-dark);
              transform: translateY(-1px);
            }
            button.secondary {
              background: #d8c8aa;
              color: #2c241a;
            }
            button[aria-busy="true"] {
              opacity: 0.82;
              cursor: progress;
            }
            .check-row {
              display: flex;
              align-items: center;
              gap: 10px;
              min-height: 48px;
              padding: 0 12px;
              border: 1px solid var(--line);
              border-radius: 14px;
              background: #fffdf9;
            }
            .check-row input {
              width: auto;
              margin: 0;
            }
            .actions {
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: 10px;
              margin-top: 14px;
            }
            .hint, .meta {
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }
            .task-note {
              padding: 10px 12px;
              border-radius: 14px;
              background: rgba(37, 93, 82, 0.06);
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }
            .metrics {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
              gap: 10px;
            }
            .metrics[aria-busy="true"],
            .ops-grid[aria-busy="true"],
            .board[aria-busy="true"],
            .workspace[aria-busy="true"] {
              opacity: 0.8;
            }
            .metric-card, .task-card, .detail-card, .audit-card {
              background: #fffdf9;
              border: 1px solid var(--line);
              border-radius: 18px;
              padding: 14px;
            }
            .metric-card strong {
              display: block;
              color: var(--muted);
              font-size: 12px;
              margin-bottom: 6px;
              font-weight: 500;
            }
            .metric-card span {
              font-size: 28px;
              line-height: 1;
            }
            .ops-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
              gap: 12px;
            }
            .ops-card {
              background: #fffdf9;
              border: 1px solid var(--line);
              border-radius: 18px;
              padding: 14px;
              display: grid;
              gap: 8px;
            }
            .ops-top {
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 10px;
            }
            .ops-top h3 {
              margin: 0;
              font-size: 15px;
            }
            .ops-badge {
              display: inline-flex;
              align-items: center;
              border-radius: 999px;
              padding: 4px 8px;
              font-size: 12px;
              background: rgba(37, 93, 82, 0.12);
              color: var(--accent-dark);
            }
            .ops-badge.warn {
              background: rgba(176, 122, 24, 0.16);
              color: #8a5c12;
            }
            .ops-badge.danger {
              background: rgba(158, 64, 50, 0.12);
              color: var(--danger);
            }
            .ops-metrics {
              display: grid;
              grid-template-columns: repeat(3, minmax(0, 1fr));
              gap: 8px;
            }
            .ops-metrics div {
              border-radius: 12px;
              background: rgba(37, 93, 82, 0.06);
              padding: 8px;
              display: grid;
              gap: 4px;
            }
            .ops-metrics strong {
              font-size: 12px;
              color: var(--muted);
              font-weight: 500;
            }
            .ops-metrics span {
              font-size: 22px;
              line-height: 1;
            }
            .board {
              display: grid;
              gap: 12px;
            }
            .group-block {
              display: grid;
              gap: 10px;
            }
            .group-title {
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 12px;
            }
            .group-title h3 {
              margin: 0;
              font-size: 15px;
            }
            .group-title span {
              font-size: 12px;
              color: var(--muted);
            }
            .task-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
              gap: 10px;
            }
            .task-card {
              display: grid;
              gap: 10px;
            }
            .task-card.selected {
              border-color: rgba(37, 93, 82, 0.55);
              box-shadow: 0 0 0 2px rgba(37, 93, 82, 0.14);
            }
            .task-card h3, .detail-card h3 {
              margin: 0;
              font-size: 16px;
              line-height: 1.45;
            }
            .task-meta {
              display: grid;
              gap: 4px;
              font-size: 13px;
              color: var(--muted);
            }
            .progress {
              overflow: hidden;
              border-radius: 999px;
              background: rgba(36, 29, 20, 0.08);
              height: 8px;
            }
            .progress > span {
              display: block;
              height: 100%;
              background: linear-gradient(90deg, #2e7a59, #c7922c);
            }
            .task-actions {
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
            }
            .task-actions button, .task-actions a {
              width: auto;
              min-width: 100px;
            }
            .task-actions a {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              padding: 12px 16px;
              border-radius: 14px;
              background: #d8c8aa;
              color: #2c241a;
              text-decoration: none;
            }
            .summary-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
              gap: 10px;
            }
            .summary-item {
              background: #fffdf8;
              border: 1px solid var(--line);
              border-radius: 16px;
              padding: 12px;
            }
            .summary-item strong {
              display: block;
              font-size: 12px;
              color: var(--muted);
              margin-bottom: 6px;
              font-weight: 500;
            }
            .summary-item span {
              display: block;
              font-size: 15px;
              line-height: 1.55;
            }
            .detail-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
              gap: 10px;
            }
            .pill-row {
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
            }
            .pill {
              display: inline-flex;
              padding: 5px 9px;
              border-radius: 999px;
              font-size: 12px;
              background: #efe3ca;
              color: #684d22;
            }
            .pill.ok {
              background: rgba(47, 124, 83, 0.12);
              color: var(--ok);
            }
            .pill.warn {
              background: rgba(176, 122, 24, 0.12);
              color: #8a5c10;
            }
            .pill.danger {
              background: rgba(158, 64, 50, 0.12);
              color: var(--danger);
            }
            .audit-list {
              display: grid;
              gap: 10px;
            }
            pre {
              margin: 10px 0 0;
              padding: 14px;
              border-radius: 14px;
              background: #2c261d;
              color: #f7f1df;
              white-space: pre-wrap;
              word-break: break-word;
              overflow: auto;
              line-height: 1.65;
            }
            .article-preview-shell {
              margin-top: 12px;
              padding: 16px;
              border-radius: 18px;
              border: 1px solid rgba(65, 48, 27, 0.12);
              background: linear-gradient(180deg, rgba(255, 252, 247, 0.98), rgba(247, 242, 233, 0.96));
              overflow: auto;
            }
            .article-preview-shell img {
              max-width: 100%;
              height: auto;
            }
            .article-preview-shell section {
              margin: 0 auto;
            }
            __ADMIN_NAV_STYLES__
            @media (max-width: 1040px) {
              .hero-grid {
                grid-template-columns: 1fr;
              }
              .overview-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
              }
              .overview-card.highlight {
                grid-column: span 2;
              }
              .layout {
                grid-template-columns: 1fr;
              }
            }
            @media (max-width: 720px) {
              .hero h1 { font-size: 30px; }
              .hero-summary,
              .overview-strip,
              .actions,
              .grid.two,
              .detail-grid,
              .task-grid {
                grid-template-columns: 1fr;
              }
              .overview-card.highlight {
                grid-column: span 1;
              }
            }
          </style>
        </head>
        <body>
          <a class="skip-link" href="#monitor-region">跳到监控主区</a>
          <main>
            <section class="hero">
              <div class="hero-grid">
                <div class="hero-copy">
                  <span class="eyebrow">UNIFIED OPERATIONS CONSOLE</span>
                  <h1>统一任务监控首页</h1>
                  <p>这一页只负责监控、筛选和定位问题，不替代 Phase 5 审核台或 Phase 6 反馈台。先看概览，再缩小筛选范围，最后点任务详情决定下一步去哪里处理。</p>
                  <div class="hero-links">
                    <a href="/admin/phase5" target="_blank" rel="noreferrer">打开 Phase 5 审核台</a>
                    <a href="/admin/phase6" target="_blank" rel="noreferrer">打开 Phase 6 反馈台</a>
                  </div>
                </div>
                <aside class="hero-status-card" aria-label="监控页状态">
                  <span class="status" id="status">等待连接</span>
                  <p class="hero-status-copy" id="flash-message" role="status" aria-live="polite" aria-atomic="true">先填 Bearer Token，再决定是否开启自动实时更新。</p>
                  <div class="hero-summary" aria-label="首屏提示">
                    <div class="hero-summary-card">
                      <strong>这页负责什么</strong>
                      <span>看任务流、队列与 worker 健康，快速定位哪一批任务最需要你介入。</span>
                    </div>
                    <div class="hero-summary-card">
                      <strong>不在这里做什么</strong>
                      <span>不直接审核、不直接补反馈；具体动作分别去 Phase 5 和 Phase 6 完成。</span>
                    </div>
                    <div class="hero-summary-card wide">
                      <strong>当前建议</strong>
                      <span id="hero-focus">先填 Bearer Token，再拉一次总览，确认今天有哪些任务需要人工介入。</span>
                    </div>
                  </div>
                </aside>
              </div>
              __ADMIN_SECTION_NAV__
            </section>

            <section class="overview-strip" aria-label="监控概览">
              <article class="overview-card">
                <strong>当前筛选</strong>
                <span id="overview-filtered-count">0</span>
                <p>当前筛选条件下能看到的任务总量。</p>
              </article>
              <article class="overview-card">
                <strong>待人工处理</strong>
                <span id="overview-manual-count">0</span>
                <p>优先关注需要人工审核或重写的任务。</p>
              </article>
              <article class="overview-card">
                <strong>队列健康</strong>
                <span id="overview-ops-state">等待快照</span>
                <p>基于 worker 心跳、堆积和处理深度判断。</p>
              </article>
              <article class="overview-card highlight">
                <strong>当前优先</strong>
                <span id="overview-focus">先填 Bearer Token，再拉一次总览，确认今天有哪些任务需要人工介入。</span>
                <p id="overview-focus-note">这页先判断“哪里有问题”，真正的审核和反馈动作仍然分别去 Phase 5 与 Phase 6 完成。</p>
              </article>
            </section>

            <section class="layout" id="monitor-region">
              <div class="stack">
                <section class="panel">
                  <h2>先准备监控</h2>
                  <p class="panel-intro">这里控制鉴权、刷新策略和当前选中任务。SSE 优先，断开时自动回退轮询；如果只是临时排查，可以关掉自动更新，手动刷新即可。</p>
                  <div class="grid">
                    <div class="field">
                      <label for="token">Bearer Token</label>
                      <input id="token" type="password" placeholder="输入 API_BEARER_TOKEN" aria-describedby="token-hint" />
                    </div>
                    <p class="field-hint" id="token-hint">第一次打开时填一次就行，页面会先记住。没有 Token 时无法拉监控快照。</p>
                    <div class="grid two">
                      <div class="field">
                        <label for="poll-seconds">轮询秒数</label>
                        <input id="poll-seconds" type="number" min="3" max="60" value="5" />
                      </div>
                      <div class="field">
                        <label for="limit">拉取数量</label>
                        <input id="limit" type="number" min="10" max="100" value="36" />
                      </div>
                    </div>
                    <div class="check-row">
                      <input id="auto-refresh" type="checkbox" checked />
                      <span>自动实时更新（优先 SSE，失败时回退轮询）</span>
                    </div>
                  </div>
                  <div class="hint" id="live-hint" style="margin-top: 12px;">当前模式：等待连接</div>
                  <div class="actions">
                    <button id="refresh-now">立即刷新</button>
                    <button id="clear-selection" class="secondary">清空当前任务</button>
                  </div>
                </section>

                <section class="panel">
                  <h2>筛选条件</h2>
                  <p class="panel-intro">先按状态和来源收缩范围，再决定要不要按关键词或起始时间继续压缩。看板按状态分组后，优先处理待人工、失败和待推草稿任务。</p>
                  <div class="grid">
                    <div class="field">
                      <label for="status-filter">状态</label>
                      <select id="status-filter">
                        <option value="">全部状态</option>
                        <option value="queued">queued</option>
                        <option value="building_brief">building_brief</option>
                        <option value="generating">generating</option>
                        <option value="reviewing">reviewing</option>
                        <option value="review_passed">review_passed</option>
                        <option value="needs_regenerate">needs_regenerate</option>
                        <option value="needs_manual_review">needs_manual_review</option>
                        <option value="draft_saved">draft_saved</option>
                        <option value="review_failed">review_failed</option>
                        <option value="push_failed">push_failed</option>
                      </select>
                    </div>
                    <div class="field">
                      <label for="source-filter">来源</label>
                      <select id="source-filter">
                        <option value="">全部来源</option>
                        <option value="wechat">wechat</option>
                        <option value="http">http</option>
                        <option value="other">other</option>
                      </select>
                    </div>
                    <div class="field">
                      <label for="query-filter">搜索</label>
                      <input id="query-filter" type="text" placeholder="task_code / URL 关键词" />
                    </div>
                    <div class="field">
                      <label for="created-after">起始时间</label>
                      <input id="created-after" type="datetime-local" />
                    </div>
                    <div class="check-row">
                      <input id="active-only" type="checkbox" checked />
                      <span>只看待处理任务</span>
                    </div>
                  </div>
                </section>

                <section class="panel">
                  <h2>最近响应</h2>
                  <p class="panel-intro">这里保留最近一次完整响应，方便复制排障、核对筛选是否生效，或确认某次实时更新到底推了什么。</p>
                  <pre id="output">等待刷新...</pre>
                </section>
              </div>

              <div class="stack">
                <section class="panel">
                  <h2>任务总览</h2>
                  <p class="panel-intro">先看今天的总体趋势，再判断是问题集中在人工审核、失败恢复，还是队列堆积。</p>
                  <div class="metrics" id="metrics" aria-busy="false">
                    <div class="metric-card"><strong>当前筛选</strong><span>0</span></div>
                  </div>
                </section>

                <section class="panel">
                  <h2>队列与 Worker 观测</h2>
                  <p class="panel-intro">实时显示四条队列的 backlog、处理中任务和 worker 心跳。worker 超过阈值未上报时，会标为 stale 或 offline。</p>
                  <div class="ops-grid" id="operations" aria-busy="false">
                    <div class="hint">等待监控快照。</div>
                  </div>
                </section>

                <section class="panel">
                  <h2>状态分组看板</h2>
                  <p class="panel-intro">看板按状态分组，卡片里会给出“下一步”提示。这里只负责定位任务，不直接执行审核或反馈动作。</p>
                  <div class="board" id="board" aria-busy="false">
                    <div class="hint">先输入 Bearer Token，再点“立即刷新”。</div>
                  </div>
                </section>

                <section class="panel">
                  <h2>任务详情</h2>
                  <p class="panel-intro">点开任务后，这里显示聚合信息、最新 generation 和审计轨迹，帮助你判断接下来该去 Phase 5 还是 Phase 6。</p>
                  <div id="workspace" class="workspace" aria-busy="false">
                    <div class="hint">从看板点“查看详情”后，这里会显示聚合任务信息。</div>
                  </div>
                </section>
              </div>
            </section>
          </main>

          <script>
            const tokenEl = document.getElementById("token");
            const pollSecondsEl = document.getElementById("poll-seconds");
            const limitEl = document.getElementById("limit");
            const autoRefreshEl = document.getElementById("auto-refresh");
            const statusFilterEl = document.getElementById("status-filter");
            const sourceFilterEl = document.getElementById("source-filter");
            const queryFilterEl = document.getElementById("query-filter");
            const createdAfterEl = document.getElementById("created-after");
            const activeOnlyEl = document.getElementById("active-only");
            const boardEl = document.getElementById("board");
            const metricsEl = document.getElementById("metrics");
            const operationsEl = document.getElementById("operations");
            const workspaceEl = document.getElementById("workspace");
            const statusEl = document.getElementById("status");
            const flashMessageEl = document.getElementById("flash-message");
            const heroFocusEl = document.getElementById("hero-focus");
            const outputEl = document.getElementById("output");
            const liveHintEl = document.getElementById("live-hint");
            const overviewFilteredCountEl = document.getElementById("overview-filtered-count");
            const overviewManualCountEl = document.getElementById("overview-manual-count");
            const overviewOpsStateEl = document.getElementById("overview-ops-state");
            const overviewFocusEl = document.getElementById("overview-focus");
            const overviewFocusNoteEl = document.getElementById("overview-focus-note");

            const STATUS_LABELS = {
              queued: "待执行",
              deduping: "去重中",
              fetching_source: "抓原文",
              source_ready: "原文就绪",
              analyzing_source: "分析原文",
              searching_related: "搜索同题",
              fetching_related: "抓同题素材",
              building_brief: "构建 Brief",
              brief_ready: "Brief 就绪",
              generating: "写稿中",
              reviewing: "审稿中",
              review_passed: "待推草稿",
              pushing_wechat_draft: "推草稿中",
              draft_saved: "已入草稿",
              fetch_failed: "抓取失败",
              analyze_failed: "分析失败",
              search_failed: "搜索失败",
              brief_failed: "Brief 失败",
              generate_failed: "生成失败",
              review_failed: "审稿失败",
              push_failed: "推草稿失败",
              needs_manual_source: "待人工抓源",
              needs_manual_review: "待人工审核",
              needs_regenerate: "待重写",
            };
            const STATUS_ORDER = [
              "needs_regenerate",
              "needs_manual_review",
              "review_passed",
              "push_failed",
              "review_failed",
              "generate_failed",
              "queued",
              "fetching_source",
              "analyzing_source",
              "searching_related",
              "fetching_related",
              "building_brief",
              "generating",
              "reviewing",
              "pushing_wechat_draft",
              "draft_saved",
            ];
            let selectedTaskId = "";
            let refreshTimer = null;
            let monitorStream = null;
            let lastSnapshot = null;

            const escapeHtml = (value) => {
              return String(value ?? "")
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#39;");
            };
            const hydrateArticlePreview = (root, generations) => {
              if (!root || !Array.isArray(generations)) return;
              root.querySelectorAll("[data-generation-html]").forEach((node) => {
                const generationId = node.getAttribute("data-generation-html");
                const generation = generations.find((item) => item.generation_id === generationId);
                node.innerHTML = generation?.html_content || '<div class="hint">暂无 HTML 预览。</div>';
              });
            };

            const setStatus = (text, tone = "", message = text) => {
              statusEl.textContent = text;
              statusEl.className = `status ${tone}`.trim();
              if (flashMessageEl) {
                flashMessageEl.textContent = message;
              }
            };

            const setLiveHint = (text) => {
              liveHintEl.textContent = text;
            };

            const renderOutput = (value) => {
              outputEl.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
            };

            const formatDate = (value) => {
              if (!value) return "暂无";
              const date = new Date(value);
              if (Number.isNaN(date.getTime())) return String(value);
              return date.toLocaleString("zh-CN", { hour12: false });
            };

            const truncate = (value, length = 72) => {
              if (!value || value.length <= length) return value || "";
              return `${value.slice(0, length)}...`;
            };

            const statusLabel = (status) => STATUS_LABELS[status] || status || "未知";

            const pillClass = (status) => {
              if (status === "draft_saved" || status === "review_passed") return "pill ok";
              if (status === "needs_manual_review" || status === "needs_regenerate" || status === "pushing_wechat_draft") return "pill warn";
              if (String(status || "").endsWith("_failed")) return "pill danger";
              return "pill";
            };
            const setDataBusy = (busy) => {
              const value = busy ? "true" : "false";
              metricsEl.setAttribute("aria-busy", value);
              operationsEl.setAttribute("aria-busy", value);
              boardEl.setAttribute("aria-busy", value);
              workspaceEl.setAttribute("aria-busy", value);
            };
            const setButtonBusy = (button, busy, pendingLabel = "处理中...") => {
              if (!button) return;
              if (!button.dataset.defaultLabel) {
                button.dataset.defaultLabel = button.textContent.trim();
              }
              button.disabled = busy;
              button.setAttribute("aria-busy", busy ? "true" : "false");
              button.textContent = busy ? pendingLabel : button.dataset.defaultLabel;
            };
            const withButtonBusy = async (button, pendingLabel, work) => {
              if (!button || button.disabled) return;
              setButtonBusy(button, true, pendingLabel);
              try {
                await work();
              } catch (error) {
                setStatus("失败", "danger", "最近一次操作失败，详见输出区域。");
                renderOutput(error.message || String(error));
              } finally {
                setButtonBusy(button, false);
              }
            };
            const nextActionText = (task) => {
              if (!task) return "先从看板里选一个任务。";
              if (task.status === "needs_manual_review") return "去 Phase 5 做人工审核。";
              if (task.status === "needs_regenerate") return "去 Phase 5 看驳回原因，再决定是否重写。";
              if (task.status === "review_passed") return "关注推草稿阶段，必要时去 Phase 5 复核。";
              if (task.status === "draft_saved") return "如需回收表现，去 Phase 6 补录反馈或做同步。";
              if (String(task.status || "").endsWith("_failed")) return "先看错误和审计轨迹，再决定是否重试。";
              return "继续观察状态推进，必要时点开详情确认卡点。";
            };
            const summarizeOpsHealth = (operations) => {
              if (!operations || !operations.available) {
                return {
                  label: "暂无监控",
                  note: operations?.note || "当前拿不到队列与 worker 观测信息。",
                };
              }
              const workers = Array.isArray(operations.workers) ? operations.workers : [];
              if (!workers.length) {
                return {
                  label: "暂无 worker",
                  note: "当前没有 worker 观测数据。",
                };
              }
              const abnormalCount = workers.filter((item) => item.status === "offline" || item.status === "stale").length;
              const busyCount = workers.filter((item) => item.status === "busy").length;
              if (abnormalCount > 0) {
                return {
                  label: `${abnormalCount} 个异常`,
                  note: "优先排查离线或堆积 worker，确认是不是队列卡住。",
                };
              }
              if (busyCount > 0) {
                return {
                  label: `${busyCount} 个处理中`,
                  note: "当前有 worker 正在消化队列，先结合 backlog 判断是否需要介入。",
                };
              }
              return {
                label: "队列稳定",
                note: "暂无离线或堆积 worker，可以把注意力放在任务状态本身。",
              };
            };
            const renderOverview = (snapshot = lastSnapshot) => {
              const summary = snapshot?.summary || null;
              const opsHealth = summarizeOpsHealth(snapshot?.operations);
              overviewFilteredCountEl.textContent = summary ? String(summary.filtered_total) : "0";
              overviewManualCountEl.textContent = summary ? String(summary.filtered_manual) : "0";
              overviewOpsStateEl.textContent = opsHealth.label;
              let focus = "先填 Bearer Token，再拉一次总览，确认今天有哪些任务需要人工介入。";
              let note = "这页先判断哪里有问题，真正的审核和反馈动作仍然分别去 Phase 5 与 Phase 6 完成。";
              if (!tokenEl.value.trim()) {
                focus = "先填 Bearer Token，再决定是否开启自动实时更新。";
                note = "没有 Token 时无法拉快照，也没法判断队列健康和待人工任务。";
              } else if (selectedTaskId) {
                focus = "当前已经锁定一个任务，优先看详情、最新 generation 和审计轨迹。";
                note = "判断问题归属后，再去 Phase 5 做审核，或去 Phase 6 做反馈补录与复盘。";
              } else if (summary) {
                if (summary.filtered_manual > 0) {
                  focus = `当前有 ${summary.filtered_manual} 个任务待人工处理，优先从这些状态组开始。`;
                  note = "待人工和待重写通常最需要立刻介入，看板卡片会提示下一步去哪一页处理。";
                } else if (summary.filtered_failed > 0) {
                  focus = `当前有 ${summary.filtered_failed} 个失败任务，先看错误和审计轨迹。`;
                  note = "失败任务通常先看详情页里的错误、审计和最新 generation，再决定是否重试。";
                } else if (summary.filtered_total === 0) {
                  focus = "当前筛选下没有任务。换个筛选看看。";
                  note = "可以放宽状态、来源或起始时间，先把需要关注的任务重新找出来。";
                } else {
                  focus = "当前任务流可用，先看待推草稿、失败和异常堆积是否有新变化。";
                  note = opsHealth.note;
                }
              }
              overviewFocusEl.textContent = focus;
              overviewFocusNoteEl.textContent = note;
              if (heroFocusEl) {
                heroFocusEl.textContent = focus;
              }
            };

            const saveDraft = () => {
              localStorage.setItem("phase7_console_token", tokenEl.value.trim());
              localStorage.setItem("phase7_console_poll_seconds", pollSecondsEl.value);
              localStorage.setItem("phase7_console_limit", limitEl.value);
              localStorage.setItem("phase7_console_auto_refresh", autoRefreshEl.checked ? "true" : "false");
              localStorage.setItem("phase7_console_status", statusFilterEl.value);
              localStorage.setItem("phase7_console_source", sourceFilterEl.value);
              localStorage.setItem("phase7_console_query", queryFilterEl.value.trim());
              localStorage.setItem("phase7_console_created_after", createdAfterEl.value);
              localStorage.setItem("phase7_console_active_only", activeOnlyEl.checked ? "true" : "false");
              localStorage.setItem("phase7_console_task", selectedTaskId);
            };

            const loadDraft = () => {
              tokenEl.value = localStorage.getItem("phase7_console_token") || "";
              pollSecondsEl.value = localStorage.getItem("phase7_console_poll_seconds") || "5";
              limitEl.value = localStorage.getItem("phase7_console_limit") || "36";
              autoRefreshEl.checked = (localStorage.getItem("phase7_console_auto_refresh") || "true") !== "false";
              statusFilterEl.value = localStorage.getItem("phase7_console_status") || "";
              sourceFilterEl.value = localStorage.getItem("phase7_console_source") || "";
              queryFilterEl.value = localStorage.getItem("phase7_console_query") || "";
              createdAfterEl.value = localStorage.getItem("phase7_console_created_after") || "";
              activeOnlyEl.checked = (localStorage.getItem("phase7_console_active_only") || "true") !== "false";
              selectedTaskId = localStorage.getItem("phase7_console_task") || "";
            };
            const apiUrl = (path) => new URL(path, window.location.origin).toString();

            const request = async (path) => {
              const token = tokenEl.value.trim();
              if (!token) throw new Error("请先输入 Bearer Token");
              const response = await fetch(apiUrl(path), {
                headers: {
                  Authorization: `Bearer ${token}`,
                },
              });
              const text = await response.text();
              let body = null;
              try {
                body = text ? JSON.parse(text) : null;
              } catch (_error) {
                body = text;
              }
              if (!response.ok) {
                throw new Error(typeof body === "string" ? body : JSON.stringify(body, null, 2));
              }
              return body;
            };

            const buildSnapshotQuery = ({ includeSelectedTask = true, includePollSeconds = false } = {}) => {
              const params = new URLSearchParams();
              params.set("limit", String(Math.min(Math.max(Number(limitEl.value) || 36, 1), 100)));
              if (activeOnlyEl.checked) {
                params.set("active_only", "true");
              }
              if (statusFilterEl.value) {
                params.set("status", statusFilterEl.value);
              }
              if (sourceFilterEl.value) {
                params.set("source_type", sourceFilterEl.value);
              }
              if (queryFilterEl.value.trim()) {
                params.set("query", queryFilterEl.value.trim());
              }
              if (createdAfterEl.value) {
                params.set("created_after", new Date(createdAfterEl.value).toISOString());
              }
              if (includeSelectedTask && selectedTaskId) {
                params.set("selected_task_id", selectedTaskId);
              }
              if (includePollSeconds) {
                params.set("poll_seconds", String(Math.min(Math.max(Number(pollSecondsEl.value) || 5, 3), 60)));
              }
              return params.toString();
            };

            const renderMetrics = (summary) => {
              const formatRate = (value) => value === null || value === undefined ? "暂无" : `${value}%`;
              metricsEl.innerHTML = `
                <div class="metric-card"><strong>当前筛选</strong><span>${escapeHtml(summary.filtered_total)}</span></div>
                <div class="metric-card"><strong>运行中</strong><span>${escapeHtml(summary.filtered_active)}</span></div>
                <div class="metric-card"><strong>待人工</strong><span>${escapeHtml(summary.filtered_manual)}</span></div>
                <div class="metric-card"><strong>待推草稿</strong><span>${escapeHtml(summary.filtered_review_passed)}</span></div>
                <div class="metric-card"><strong>已入草稿</strong><span>${escapeHtml(summary.filtered_draft_saved)}</span></div>
                <div class="metric-card"><strong>失败任务</strong><span>${escapeHtml(summary.filtered_failed)}</span></div>
                <div class="metric-card"><strong>异常堆积</strong><span>${escapeHtml(summary.filtered_stuck)}</span></div>
                <div class="metric-card"><strong>今日提交</strong><span>${escapeHtml(summary.today_submitted)}</span></div>
                <div class="metric-card"><strong>今日入草稿</strong><span>${escapeHtml(summary.today_draft_saved)}</span></div>
                <div class="metric-card"><strong>今日失败</strong><span>${escapeHtml(summary.today_failed)}</span></div>
                <div class="metric-card"><strong>今日审稿通过率</strong><span>${escapeHtml(formatRate(summary.today_review_success_rate))}</span></div>
                <div class="metric-card"><strong>今日自动推稿成功率</strong><span>${escapeHtml(formatRate(summary.today_auto_push_success_rate))}</span></div>
                <div class="metric-card"><strong>快照时间</strong><span style="font-size:16px; line-height:1.35;">${escapeHtml(formatDate(summary.generated_at))}</span></div>
              `;
            };

            const renderBoard = (tasks) => {
              if (!Array.isArray(tasks) || tasks.length === 0) {
                boardEl.innerHTML = '<div class="hint">当前筛选下没有任务。换个筛选看看。</div>';
                return;
              }
              const counts = tasks.reduce((map, item) => {
                map[item.status] = (map[item.status] || 0) + 1;
                return map;
              }, {});
              const orderedStatuses = [
                ...STATUS_ORDER.filter((item) => counts[item]),
                ...Object.keys(counts).filter((item) => !STATUS_ORDER.includes(item)).sort(),
              ];
              boardEl.innerHTML = orderedStatuses.map((groupStatus) => `
                <section class="group-block">
                  <div class="group-title">
                    <h3>${escapeHtml(statusLabel(groupStatus))}</h3>
                    <span>${escapeHtml(counts[groupStatus])} 个任务</span>
                  </div>
                  <div class="task-grid">
                    ${tasks.filter((item) => item.status === groupStatus).map((task) => `
                      <article class="task-card ${selectedTaskId === task.task_id ? "selected" : ""}">
                        <h3>${escapeHtml(task.title || "未命名任务")}</h3>
                        <div class="pill-row">
                          <span class="${pillClass(task.status)}">${escapeHtml(task.status)}</span>
                          <span class="pill">${escapeHtml(task.progress)}%</span>
                          <span class="pill">${escapeHtml(task.source_type || "unknown")}</span>
                        </div>
                        <div class="progress"><span style="width:${Math.max(0, Math.min(100, Number(task.progress) || 0))}%"></span></div>
                        <div class="task-meta">
                          <div><strong>task_code</strong> ${escapeHtml(task.task_code)}</div>
                          <div><strong>task_id</strong> ${escapeHtml(task.task_id)}</div>
                          <div><strong>更新时间</strong> ${escapeHtml(formatDate(task.updated_at))}</div>
                          <div><strong>草稿</strong> ${escapeHtml(task.wechat_media_id || "暂无")}</div>
                          <div><strong>链接</strong> ${escapeHtml(truncate(task.source_url, 88))}</div>
                          <div><strong>错误</strong> ${escapeHtml(task.error || "无")}</div>
                        </div>
                        <div class="task-note"><strong>下一步</strong> ${escapeHtml(nextActionText(task))}</div>
                        <div class="task-actions">
                          <button data-action="inspect" data-task-id="${escapeHtml(task.task_id)}">查看详情</button>
                          <a href="/admin/phase5" target="_blank" rel="noreferrer">去 Phase5</a>
                          <a href="/admin/phase6" target="_blank" rel="noreferrer">去 Phase6</a>
                        </div>
                      </article>
                    `).join("")}
                  </div>
                </section>
              `).join("");
            };

            const renderOperations = (operations) => {
              if (!operations || !operations.available) {
                operationsEl.innerHTML = `<div class="hint">${escapeHtml(operations?.note || "当前无法获取队列与 worker 观测信息。")}</div>`;
                return;
              }
              if (!Array.isArray(operations.workers) || operations.workers.length === 0) {
                operationsEl.innerHTML = '<div class="hint">当前没有 worker 观测数据。</div>';
                return;
              }
              const statusLabels = {
                idle: "运行中",
                busy: "处理中",
                stale: "堆积 / 超时",
                offline: "离线",
                unknown: "未上报",
              };
              operationsEl.innerHTML = operations.workers.map((item) => {
                const badgeClass = item.status === "busy"
                  ? ""
                  : item.status === "idle"
                    ? ""
                    : item.status === "unknown"
                      ? "warn"
                      : "danger";
                return `
                  <article class="ops-card">
                    <div class="ops-top">
                      <h3>${escapeHtml(item.label)}</h3>
                      <span class="ops-badge ${badgeClass}">${escapeHtml(statusLabels[item.status] || item.status)}</span>
                    </div>
                    <div class="ops-metrics">
                      <div><strong>队列</strong><span>${escapeHtml(item.queue_depth)}</span></div>
                      <div><strong>处理中</strong><span>${escapeHtml(item.processing_depth)}</span></div>
                      <div><strong>待确认</strong><span>${escapeHtml(item.pending_count)}</span></div>
                    </div>
                    <div class="hint">最近心跳：${escapeHtml(item.last_seen_at ? formatDate(item.last_seen_at) : "暂无")}</div>
                    <div class="hint">当前任务：${escapeHtml(item.current_task_id || "无")}</div>
                    <div class="hint">超时阈值：${escapeHtml(item.stale_after_seconds)} 秒</div>
                  </article>
                `;
              }).join("");
            };

            const renderWorkspace = (workspace) => {
              const latestGeneration = workspace.generations[0] || null;
              const latestReview = latestGeneration?.review || null;
              workspaceEl.innerHTML = `
                <div class="summary-grid">
                  <div class="summary-item"><strong>状态</strong><span>${escapeHtml(workspace.status)} · ${escapeHtml(workspace.progress)}%</span></div>
                  <div class="summary-item"><strong>标题</strong><span>${escapeHtml(workspace.title || "暂无")}</span></div>
                  <div class="summary-item"><strong>task_code</strong><span>${escapeHtml(workspace.task_code)}</span></div>
                  <div class="summary-item"><strong>已推草稿</strong><span>${escapeHtml(workspace.wechat_media_id || "暂无")}</span></div>
                  <div class="summary-item"><strong>同题素材</strong><span>${escapeHtml(workspace.related_article_count)}</span></div>
                  <div class="summary-item"><strong>最后更新</strong><span>${escapeHtml(formatDate(workspace.updated_at))}</span></div>
                </div>

                <div class="detail-grid" style="margin-top: 14px;">
                  <div class="detail-card">
                    <h3>源文与 Brief</h3>
                    <div class="meta">
                      <div><strong>source_url</strong> ${escapeHtml(workspace.source_url)}</div>
                      <div><strong>作者</strong> ${escapeHtml(workspace.source_article?.author || "未知")}</div>
                      <div><strong>摘要</strong> ${escapeHtml(workspace.source_article?.summary || "暂无")}</div>
                      <div><strong>新角度</strong> ${escapeHtml(workspace.brief?.new_angle || "暂无")}</div>
                      <div><strong>定位</strong> ${escapeHtml(workspace.brief?.positioning || "暂无")}</div>
                    </div>
                  </div>

                  <div class="detail-card">
                    <h3>最新 generation</h3>
                    <div class="pill-row">
                      <span class="pill">${escapeHtml(`v${latestGeneration?.version_no || "-"}`)}</span>
                      <span class="${pillClass(latestReview?.final_decision || latestGeneration?.status)}">${escapeHtml(latestReview?.final_decision || latestGeneration?.status || "暂无")}</span>
                      <span class="pill">${escapeHtml(latestGeneration?.model_name || "暂无")}</span>
                    </div>
                    <div class="meta" style="margin-top: 8px;">
                      <div><strong>标题</strong> ${escapeHtml(latestGeneration?.title || "暂无")}</div>
                      <div><strong>摘要</strong> ${escapeHtml(latestGeneration?.digest || "暂无")}</div>
                      <div><strong>Prompt</strong> ${escapeHtml(latestGeneration?.prompt_version || "未记录")}</div>
                    </div>
                    <details open>
                      <summary>展开 HTML 预览</summary>
                      <div class="article-preview-shell" data-generation-html="${escapeHtml(latestGeneration?.generation_id || "")}"></div>
                    </details>
                    <details>
                      <summary>展开原始 Markdown</summary>
                      <pre>${escapeHtml(latestGeneration?.markdown_content || "暂无")}</pre>
                    </details>
                  </div>
                </div>

                <div class="detail-card" style="margin-top: 14px;">
                  <h3>审计轨迹</h3>
                  <div class="audit-list">
                    ${workspace.audits.length ? workspace.audits.map((item) => `
                      <div class="audit-card">
                        <div><strong>${escapeHtml(item.action)}</strong></div>
                        <div class="meta">${escapeHtml(formatDate(item.created_at))} · ${escapeHtml(item.operator)}</div>
                        <pre>${escapeHtml(JSON.stringify(item.payload || {}, null, 2))}</pre>
                      </div>
                    `).join("") : '<div class="hint">暂无审计日志。</div>'}
                  </div>
                </div>
              `;
              hydrateArticlePreview(workspaceEl, workspace.generations || []);
            };

            const renderMonitorSnapshot = (snapshot, { updateOutput = true, source = "manual" } = {}) => {
              lastSnapshot = snapshot;
              renderMetrics(snapshot.summary);
              renderOperations(snapshot.operations);
              renderBoard(snapshot.tasks || []);
              if (snapshot.workspace) {
                renderWorkspace(snapshot.workspace);
              } else if (!selectedTaskId) {
                workspaceEl.innerHTML = '<div class="hint">从看板点“查看详情”后，这里会显示聚合任务信息。</div>';
              } else {
                workspaceEl.innerHTML = '<div class="hint">当前选中任务不存在或已被清理。</div>';
              }
              if (updateOutput) {
                renderOutput(snapshot);
              }
              if (source === "stream") {
                setStatus(`实时中 · ${snapshot.tasks.length} 个任务`, "", "SSE 正在持续推送最新快照。");
              } else {
                setStatus(`已刷新 · ${snapshot.tasks.length} 个任务`, "", "监控快照已刷新，可以继续收窄筛选或点开任务详情。");
              }
              renderOverview(snapshot);
            };

            const refreshAll = async () => {
              saveDraft();
              setStatus("刷新中", "", "正在拉取最新监控快照。");
              setDataBusy(true);
              try {
                const snapshot = await request(`/api/v1/admin/monitor/snapshot?${buildSnapshotQuery()}`);
                renderMonitorSnapshot(snapshot, { updateOutput: true, source: "manual" });
              } finally {
                setDataBusy(false);
              }
            };

            const refreshWorkspace = async (taskId) => {
              selectedTaskId = taskId;
              saveDraft();
              await refreshAll();
              restartRealtime();
            };

            const closeStream = () => {
              if (monitorStream) {
                monitorStream.close();
                monitorStream = null;
              }
            };

            const restartTimer = () => {
              if (refreshTimer) {
                clearInterval(refreshTimer);
                refreshTimer = null;
              }
              if (!autoRefreshEl.checked) return;
              const seconds = Math.min(Math.max(Number(pollSecondsEl.value) || 5, 3), 60);
              refreshTimer = window.setInterval(() => {
                refreshAll().catch((error) => {
                  setStatus("轮询失败", "warn", "轮询刷新失败，详见输出区域。");
                  renderOutput(error.message || String(error));
                });
              }, seconds * 1000);
              setLiveHint(`当前模式：轮询 · 每 ${seconds} 秒`);
            };

            const restartRealtime = () => {
              closeStream();
              if (refreshTimer) {
                clearInterval(refreshTimer);
                refreshTimer = null;
              }
              if (!tokenEl.value.trim()) {
                setLiveHint("当前模式：等待 Bearer Token");
                renderOverview();
                return;
              }
              if (!autoRefreshEl.checked) {
                setLiveHint("当前模式：自动更新已关闭");
                renderOverview();
                return;
              }
              if (!window.EventSource) {
                setLiveHint("当前模式：浏览器不支持 SSE，已回退轮询");
                restartTimer();
                return;
              }
              const streamUrl = `/admin/console/stream?${buildSnapshotQuery({ includePollSeconds: true })}`;
              monitorStream = new EventSource(streamUrl);
              setLiveHint("当前模式：实时流连接中");
              monitorStream.addEventListener("snapshot", (event) => {
                try {
                  const snapshot = JSON.parse(event.data);
                  renderMonitorSnapshot(snapshot, { updateOutput: true, source: "stream" });
                  setLiveHint(`当前模式：SSE 实时推送 · ${formatDate(snapshot.summary.generated_at)}`);
                } catch (error) {
                  setStatus("实时流解析失败", "warn", "实时流返回了无法解析的数据，详见输出区域。");
                  renderOutput(error.message || String(error));
                }
              });
              monitorStream.onerror = () => {
                closeStream();
                setLiveHint("当前模式：SSE 中断，已回退轮询");
                restartTimer();
              };
            };

            document.getElementById("refresh-now").addEventListener("click", async (event) => {
              await withButtonBusy(event.currentTarget, "刷新中...", async () => {
                await refreshAll();
              });
            });

            document.getElementById("clear-selection").addEventListener("click", () => {
              selectedTaskId = "";
              saveDraft();
              workspaceEl.innerHTML = '<div class="hint">当前任务已清空。</div>';
              renderOverview();
              setStatus("已清空", "", "当前任务已清空，可以继续从看板里挑一个任务。");
              restartRealtime();
            });

            [tokenEl, pollSecondsEl, limitEl, autoRefreshEl, statusFilterEl, sourceFilterEl, queryFilterEl, createdAfterEl, activeOnlyEl].forEach((element) => {
              const eventName = element === queryFilterEl ? "input" : "change";
              element.addEventListener(eventName, () => {
                saveDraft();
                renderOverview();
                restartRealtime();
              });
            });

            boardEl.addEventListener("click", async (event) => {
              const button = event.target.closest("button[data-action='inspect']");
              if (!button) return;
              const taskId = button.getAttribute("data-task-id");
              if (!taskId) return;
              try {
                await refreshWorkspace(taskId);
              } catch (error) {
                setStatus("失败", "danger", "加载任务详情失败，详见输出区域。");
                renderOutput(error.message || String(error));
              }
            });

            loadDraft();
            renderOverview();
            restartRealtime();
            if (tokenEl.value.trim()) {
              refreshAll().catch((error) => {
                setStatus("失败", "danger", "首次加载监控快照失败，详见输出区域。");
                renderOutput(error.message || String(error));
              });
            }
          </script>
        </body>
        </html>
        """
    )
    return (
        html.replace("__ADMIN_NAV_STYLES__", admin_section_nav_styles()).replace(
            "__ADMIN_SECTION_NAV__", admin_section_nav("portal")
        )
    )


@router.get("/admin/settings", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def settings_console() -> str:
    html = dedent(
        """\
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>Phase 7B 设置台</title>
          <style>
            :root {
              --bg: #efe8dd;
              --panel: rgba(255, 251, 246, 0.94);
              --line: #d4c2ad;
              --text: #221a11;
              --muted: #6d6256;
              --accent: #255d52;
              --accent-dark: #173f38;
              --danger: #9e4032;
              --warn: #b07a18;
              --shadow: 0 18px 48px rgba(55, 40, 21, 0.1);
            }
            * { box-sizing: border-box; }
            body {
              margin: 0;
              color: var(--text);
              line-height: 1.5;
              font-family: "PingFang SC", "Noto Serif SC", serif;
              min-height: 100vh;
              background:
                radial-gradient(circle at top left, rgba(255, 229, 175, 0.5), transparent 26%),
                radial-gradient(circle at bottom right, rgba(178, 222, 208, 0.42), transparent 28%),
                linear-gradient(140deg, #efe8dd 0%, #f6f2ea 44%, #ebe1d2 100%);
            }
            .skip-link {
              position: absolute;
              top: 16px;
              left: 16px;
              transform: translateY(-180%);
              padding: 10px 14px;
              border-radius: 999px;
              background: var(--accent-dark);
              color: #f7faf8;
              text-decoration: none;
              z-index: 20;
              transition: transform 120ms ease;
            }
            .skip-link:focus-visible {
              transform: translateY(0);
            }
            main {
              max-width: 1440px;
              margin: 0 auto;
              padding: 28px 20px 48px;
              display: grid;
              gap: 18px;
            }
            .hero {
              display: grid;
              gap: 14px;
              padding: 24px;
              border: 1px solid var(--line);
              border-radius: 28px;
              background: linear-gradient(135deg, rgba(255, 248, 239, 0.92), rgba(248, 244, 237, 0.86));
              box-shadow: var(--shadow);
              backdrop-filter: blur(10px);
            }
            .hero-grid {
              display: grid;
              grid-template-columns: minmax(0, 1.28fr) minmax(320px, 0.92fr);
              gap: 18px;
              align-items: stretch;
            }
            .hero-copy {
              display: grid;
              gap: 10px;
              align-content: start;
            }
            .eyebrow {
              display: inline-flex;
              width: fit-content;
              padding: 6px 10px;
              border-radius: 999px;
              font-size: 12px;
              letter-spacing: 0.08em;
              background: rgba(37, 93, 82, 0.12);
              color: var(--accent-dark);
            }
            .hero h1 {
              margin: 0;
              font-size: 40px;
              line-height: 1.05;
            }
            .hero p {
              margin: 0;
              max-width: 920px;
              line-height: 1.75;
              color: var(--muted);
            }
            .hero-status-card {
              display: grid;
              gap: 14px;
              padding: 18px;
              border-radius: 24px;
              border: 1px solid rgba(37, 93, 82, 0.12);
              background: linear-gradient(160deg, rgba(255, 252, 247, 0.95), rgba(249, 245, 237, 0.9));
            }
            .hero-status-copy {
              margin: 0;
              font-size: 15px;
              line-height: 1.7;
            }
            .hero-summary {
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: 10px;
            }
            .hero-summary-card {
              display: grid;
              gap: 6px;
              padding: 12px 14px;
              border-radius: 18px;
              border: 1px solid rgba(65, 48, 27, 0.1);
              background: rgba(255, 253, 249, 0.78);
            }
            .hero-summary-card strong {
              color: var(--muted);
              font-size: 12px;
              font-weight: 500;
            }
            .hero-summary-card span {
              font-size: 16px;
              line-height: 1.55;
            }
            .hero-summary-card.wide {
              grid-column: 1 / -1;
              background: linear-gradient(135deg, rgba(37, 93, 82, 0.1), rgba(255, 249, 242, 0.95));
            }
            .overview-strip {
              display: grid;
              grid-template-columns: repeat(4, minmax(0, 1fr));
              gap: 12px;
            }
            .overview-card {
              display: grid;
              gap: 8px;
              min-width: 0;
              padding: 16px;
              border-radius: 20px;
              border: 1px solid var(--line);
              background: rgba(255, 251, 246, 0.9);
              box-shadow: 0 14px 32px rgba(58, 40, 18, 0.08);
            }
            .overview-card.highlight {
              grid-column: span 2;
              background: linear-gradient(135deg, rgba(37, 93, 82, 0.1), rgba(255, 249, 242, 0.96));
            }
            .overview-card strong {
              color: var(--muted);
              font-size: 12px;
              font-weight: 500;
            }
            .overview-card span {
              display: block;
              font-size: 28px;
              line-height: 1.1;
            }
            .overview-card p {
              margin: 0;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }
            .layout {
              display: grid;
              grid-template-columns: 340px minmax(0, 1fr);
              gap: 18px;
              align-items: start;
            }
            .stack {
              display: grid;
              gap: 16px;
            }
            .panel {
              background: var(--panel);
              border: 1px solid var(--line);
              border-radius: 22px;
              padding: 20px;
              box-shadow: var(--shadow);
              backdrop-filter: blur(8px);
            }
            .panel h2 {
              margin: 0 0 14px;
              font-size: 18px;
            }
            .panel-intro {
              margin: 0 0 14px;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }
            .status {
              display: inline-flex;
              padding: 7px 12px;
              border-radius: 999px;
              background: rgba(37, 93, 82, 0.12);
              color: var(--accent-dark);
              font-size: 12px;
              margin-bottom: 12px;
            }
            label {
              display: block;
              font-size: 13px;
              color: var(--muted);
              margin-bottom: 6px;
            }
            .field {
              display: grid;
              gap: 6px;
            }
            .field-hint {
              margin: 0;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }
            input, textarea, select, button {
              width: 100%;
              border-radius: 12px;
              border: 1px solid var(--line);
              font: inherit;
            }
            input, textarea, select {
              padding: 11px 13px;
              background: #fffdf8;
              color: var(--text);
            }
            input:focus-visible,
            textarea:focus-visible,
            select:focus-visible,
            button:focus-visible,
            a:focus-visible,
            summary:focus-visible {
              outline: 2px solid rgba(37, 93, 82, 0.18);
              outline-offset: 3px;
            }
            textarea {
              min-height: 100px;
              resize: vertical;
            }
            .checkbox {
              display: flex;
              align-items: center;
              gap: 10px;
              padding: 12px 13px;
              border: 1px solid var(--line);
              border-radius: 12px;
              background: #fffdf8;
            }
            .checkbox input {
              width: 18px;
              height: 18px;
              margin: 0;
            }
            button {
              width: auto;
              min-width: 128px;
              padding: 10px 16px;
              cursor: pointer;
              background: var(--accent);
              color: #f8fbf7;
              border: none;
              transition: transform 0.12s ease, background 0.12s ease;
            }
            button:hover { background: var(--accent-dark); transform: translateY(-1px); }
            button.secondary { background: #dcccb5; color: #2c241a; }
            button.ghost {
              background: #fffdf8;
              color: var(--accent-dark);
              border: 1px solid var(--line);
            }
            button[aria-busy="true"] {
              opacity: 0.82;
              cursor: progress;
            }
            .actions {
              display: flex;
              flex-wrap: wrap;
              gap: 10px;
              margin-top: 14px;
            }
            .hint, .list {
              color: var(--muted);
              line-height: 1.72;
              font-size: 14px;
            }
            .list {
              padding-left: 18px;
              margin: 0;
            }
            .categories {
              display: grid;
              gap: 18px;
            }
            .category {
              display: grid;
              gap: 12px;
            }
            .category h3 {
              margin: 0;
              font-size: 20px;
            }
            .setting-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
              gap: 14px;
            }
            .setting-card {
              border: 1px solid var(--line);
              border-radius: 18px;
              padding: 16px;
              background: #fffdf8;
              display: grid;
              gap: 12px;
            }
            .setting-card > div:first-child {
              display: grid;
              gap: 6px;
            }
            .env-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
              gap: 14px;
            }
            .fold {
              border: 1px dashed var(--line);
              border-radius: 16px;
              padding: 12px 14px;
              background: rgba(255, 253, 248, 0.7);
            }
            .fold summary {
              cursor: pointer;
              color: var(--muted);
              font-size: 13px;
            }
            .fold .list {
              margin-top: 10px;
            }
            .env-card {
              border: 1px solid var(--line);
              border-radius: 18px;
              padding: 14px;
              background: #fffdf8;
              display: grid;
              gap: 8px;
            }
            .env-top {
              display: flex;
              justify-content: space-between;
              gap: 10px;
              align-items: center;
            }
            .env-top strong {
              font-size: 14px;
            }
            .env-badge {
              display: inline-flex;
              align-items: center;
              border-radius: 999px;
              padding: 4px 8px;
              font-size: 12px;
              background: rgba(37, 93, 82, 0.12);
              color: var(--accent-dark);
            }
            .env-badge.warn {
              background: rgba(171, 92, 47, 0.14);
              color: #8a4a21;
            }
            .env-card code {
              font-size: 12px;
              color: var(--accent-dark);
            }
            .setting-card h4 {
              margin: 0;
              font-size: 16px;
            }
            .setting-card p {
              margin: 0;
              color: var(--muted);
              line-height: 1.66;
            }
            .setting-meta {
              display: grid;
              gap: 6px;
              font-size: 12px;
              color: var(--muted);
            }
            .setting-meta strong {
              color: var(--text);
              font-weight: 600;
            }
            .setting-actions {
              display: flex;
              flex-wrap: wrap;
              gap: 10px;
            }
            .card-note {
              margin: 0;
              font-size: 12px;
              color: var(--muted);
              line-height: 1.6;
            }
            pre {
              margin: 0;
              white-space: pre-wrap;
              word-break: break-word;
              background: #2f261a;
              color: #f9f2de;
              padding: 16px;
              border-radius: 14px;
              min-height: 220px;
              line-height: 1.6;
              overflow: auto;
            }
            .empty {
              border: 1px dashed var(--line);
              border-radius: 18px;
              padding: 24px;
              color: var(--muted);
              background: rgba(255, 255, 255, 0.4);
            }
            .categories[aria-busy="true"] {
              opacity: 0.8;
            }
            __ADMIN_NAV_STYLES__
            @media (max-width: 960px) {
              .hero-grid { grid-template-columns: 1fr; }
              .overview-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
              .layout { grid-template-columns: 1fr; }
            }
            @media (max-width: 720px) {
              main { padding: 20px 14px 36px; }
              .hero { padding: 18px; }
              .panel { padding: 16px; border-radius: 20px; }
              .hero h1 { font-size: 30px; }
              .hero-summary { grid-template-columns: 1fr; }
              .overview-strip { grid-template-columns: 1fr; }
              .overview-card.highlight { grid-column: span 1; }
              .setting-actions, .actions { flex-direction: column; }
              button { width: 100%; }
            }
          </style>
        </head>
        <body>
          <a class="skip-link" href="#settings-region">跳到设置主区</a>
          <main>
            <section class="hero">
              <div class="hero-grid">
                <div class="hero-copy">
                  <span class="eyebrow">RUNTIME SETTINGS & STATUS</span>
                  <h1>运行参数设置</h1>
                  <p>这里只改少量运行开关，不碰密钥和基础设施。</p>
                </div>
                <aside class="hero-status-card" aria-label="设置页状态">
                  <span class="status" id="status">等待加载</span>
                  <p class="hero-status-copy" id="flash-message" role="status" aria-live="polite" aria-atomic="true">默认复用后台登录态。先刷新设置和环境状态。</p>
                  <div class="hero-summary" aria-label="首屏提示">
                    <div class="hero-summary-card">
                      <strong>会影响什么</strong>
                      <span>只影响新任务，不回写基础设施。</span>
                    </div>
                    <div class="hero-summary-card">
                      <strong>需要准备什么</strong>
                      <span>操作人标识和变更备注；默认复用后台登录态。</span>
                    </div>
                    <div class="hero-summary-card wide">
                      <strong>当前建议</strong>
                      <span id="hero-focus">先刷新，把可改设置和只读环境状态都拉下来。</span>
                    </div>
                  </div>
                </aside>
              </div>
              __ADMIN_SECTION_NAV__
            </section>

            <section class="overview-strip" aria-label="设置概览">
              <article class="overview-card">
                <strong>可改设置</strong>
                <span id="overview-settings-count">0</span>
                <p>当前支持通过网页覆盖的运行参数数量。</p>
              </article>
              <article class="overview-card">
                <strong>已覆盖</strong>
                <span id="overview-overrides-count">0</span>
                <p>数据库里已经覆盖、不会再走环境默认的设置项。</p>
              </article>
              <article class="overview-card">
                <strong>必填环境缺失</strong>
                <span id="overview-missing-count">0</span>
                <p>这些配置不在页面里修改，需要回服务器补齐。</p>
              </article>
              <article class="overview-card highlight">
                <strong>当前优先</strong>
                <span id="overview-focus">先刷新，把可改设置和只读环境状态都拉下来。</span>
                <p id="overview-focus-note">页面先判断哪些能改、哪些只能看，再决定是否保存覆盖值。</p>
              </article>
            </section>

            <section class="layout" id="settings-region">
              <div class="stack">
                <section class="panel">
                  <h2>先准备</h2>
                  <p class="panel-intro">先准备操作元数据。页面默认复用后台登录态；保存设置、恢复默认、发送测试告警都会复用这里的信息。</p>
                  <details class="fold">
                    <summary>高级鉴权兜底</summary>
                    <div class="field" style="margin-top: 12px;">
                      <label for="fallback-token">Bearer Token（仅兜底）</label>
                      <input id="fallback-token" type="password" placeholder="仅在未启用后台登录态时填写" aria-describedby="fallback-token-hint" />
                    </div>
                    <p class="field-hint" id="fallback-token-hint">页面会先复用当前后台登录态。只有请求返回 401 且当前环境没有启用后台 Basic Auth 时，才需要在这里临时填入 `API_BEARER_TOKEN`。</p>
                  </details>
                  <div class="field" style="margin-top: 14px;">
                    <label for="operator">operator</label>
                    <input id="operator" type="text" value="admin-console" aria-describedby="operator-hint" />
                  </div>
                  <p class="field-hint" id="operator-hint">用于审计日志，建议填当前值班人或操作来源。</p>
                  <div class="field" style="margin-top: 14px;">
                    <label for="note">变更备注</label>
                    <textarea id="note" placeholder="例如：将写稿模型切到新版本做小流量验证" aria-describedby="note-hint"></textarea>
                  </div>
                  <p class="field-hint" id="note-hint">备注会跟随变更和测试告警一起发送，尽量写清楚目的和影响范围。</p>
                  <div class="actions">
                    <button id="refresh">刷新</button>
                    <button id="clear-output" class="secondary">清空</button>
                  </div>
                </section>

                <section class="panel">
                  <h2>不能改什么</h2>
                  <p class="panel-intro">为了安全和部署稳定，下面这些仍然保留在服务器配置里，不开放网页编辑。</p>
                  <details class="fold">
                    <summary>展开说明</summary>
                    <ul class="list">
                      <li>这里只覆盖少量运行参数，不改数据库、Redis、域名或容器配置。</li>
                      <li>密钥类值仍然只保留在服务器 `.env`，页面不显示也不支持改写。</li>
                      <li>Phase 4 仍然受 `WECHAT_ENABLE_DRAFT_PUSH` 总开关约束。</li>
                      <li>自动反馈切到 `http` 前，仍需在 `.env` 里配置 `FEEDBACK_SYNC_HTTP_URL` 与可选 `FEEDBACK_SYNC_API_KEY`。</li>
                    </ul>
                  </details>
                </section>

                <section class="panel">
                  <h2>辅助工具</h2>
                  <p class="panel-intro">这里放的是低频辅助操作，不应该干扰主流程。先刷新确认状态，再决定是否发测试告警或看调试输出。</p>
                  <details class="fold">
                    <summary>测试告警</summary>
                    <div class="hint" id="alert-hint" style="margin-top: 10px;">先点“刷新”。若 `ALERT_WEBHOOK_URL` 未配置，这里会显示为不可用。</div>
                    <div class="actions">
                      <button id="send-alert">发送</button>
                    </div>
                  </details>
                  <details class="fold">
                    <summary>调试输出</summary>
                    <pre id="output">等待请求。</pre>
                  </details>
                </section>
              </div>

              <div class="stack">
                <section class="panel">
                  <h2>当前设置</h2>
                  <p class="panel-intro">改完只影响新任务；恢复默认会回退到环境变量。优先处理确实需要热修改的项，不要把这里当作 `.env` 编辑器。</p>
                  <div id="categories" class="categories" aria-busy="false">
                    <div class="empty">点击“刷新”拉取当前设置。</div>
                  </div>
                </section>

                <section class="panel">
                  <h2>环境状态</h2>
                  <p class="panel-intro">这里只读显示，密钥不会明文展示。它的作用是帮助你判断“能不能改”和“改了以后会不会真正生效”。</p>
                  <div id="runtime-status" class="categories" aria-busy="false">
                    <div class="empty">点击“刷新”拉取环境状态。</div>
                  </div>
                </section>
              </div>
            </section>
          </main>

          <script>
            const statusEl = document.getElementById("status");
            const flashMessageEl = document.getElementById("flash-message");
            const heroFocusEl = document.getElementById("hero-focus");
            const outputEl = document.getElementById("output");
            const alertHintEl = document.getElementById("alert-hint");
            const fallbackTokenEl = document.getElementById("fallback-token");
            const operatorEl = document.getElementById("operator");
            const noteEl = document.getElementById("note");
            const categoriesEl = document.getElementById("categories");
            const runtimeStatusEl = document.getElementById("runtime-status");
            const overviewSettingsCountEl = document.getElementById("overview-settings-count");
            const overviewOverridesCountEl = document.getElementById("overview-overrides-count");
            const overviewMissingCountEl = document.getElementById("overview-missing-count");
            const overviewFocusEl = document.getElementById("overview-focus");
            const overviewFocusNoteEl = document.getElementById("overview-focus-note");
            const CATEGORY_LABELS = {
              phase4: "Phase 4 生成与审稿",
              feedback: "Phase 6 自动反馈",
            };
            const RUNTIME_CATEGORY_LABELS = {
              app: "应用基础配置",
              infra: "基础设施连接",
              security: "访问控制与密钥",
              integrations: "外部集成",
              observability: "观测与告警",
            };
            let currentSettings = [];
            let currentRuntimeStatus = null;

            const setStatus = (text, tone = "") => {
              statusEl.textContent = text;
              statusEl.className = `status ${tone}`.trim();
              if (flashMessageEl) {
                flashMessageEl.textContent = text;
              }
            };
            const setDataBusy = (busy) => {
              categoriesEl.setAttribute("aria-busy", busy ? "true" : "false");
              runtimeStatusEl.setAttribute("aria-busy", busy ? "true" : "false");
            };

            const renderOutput = (value) => {
              outputEl.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
            };
            const apiUrl = (path) => new URL(path, window.location.origin).toString();
            const authErrorMessage = (usedFallbackToken) => usedFallbackToken
              ? "高级鉴权兜底里的 Bearer Token 未通过校验，请确认填写的是当前环境的 API_BEARER_TOKEN。"
              : "当前页面默认复用后台登录态。若这个环境没有配置后台登录，请展开“高级鉴权兜底”后填入 Bearer Token。";

            const escapeHtml = (value) =>
              String(value)
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;");

            const formatValue = (value, valueType) => {
              if (value === null || value === undefined) return "未设置";
              if (valueType === "boolean") return value ? "true" : "false";
              if (valueType === "integer_list" && Array.isArray(value)) return value.join(", ");
              if (typeof value === "object") return JSON.stringify(value);
              return String(value);
            };
            const renderOverview = (settings = [], runtimeStatus = null) => {
              const overrideCount = settings.filter((item) => item.has_override).length;
              const environment = runtimeStatus?.environment || [];
              const missingRequired = environment.filter((item) => item.required && !item.configured).length;
              let focus = "先刷新，把可改设置和只读环境状态都拉下来。";
              let note = "页面先判断哪些能改、哪些只能看，再决定是否保存覆盖值。";
              if (missingRequired > 0) {
                focus = `先补齐 ${missingRequired} 项必填环境配置`;
                note = "这些项不在页面里修改，需要回服务器环境变量或部署配置中补齐。";
              } else if (overrideCount > 0) {
                focus = `当前已有 ${overrideCount} 项数据库覆盖`;
                note = "保存前先确认是否真的需要覆盖环境默认，避免历史覆盖长期遗留。";
              } else if (settings.length > 0) {
                focus = "设置已加载，可以按卡片逐项修改";
                note = "优先改确实需要热更新的运行参数，改完再看只读环境状态是否匹配。";
              }
              overviewSettingsCountEl.textContent = String(settings.length);
              overviewOverridesCountEl.textContent = String(overrideCount);
              overviewMissingCountEl.textContent = String(missingRequired);
              overviewFocusEl.textContent = focus;
              overviewFocusNoteEl.textContent = note;
              if (heroFocusEl) {
                heroFocusEl.textContent = focus;
              }
            };

            const readDraft = () => {
              fallbackTokenEl.value = localStorage.getItem("phase7_settings_fallback_token") || "";
              operatorEl.value = localStorage.getItem("phase7_settings_operator") || "admin-console";
              noteEl.value = localStorage.getItem("phase7_settings_note") || "";
            };

            const saveDraft = () => {
              localStorage.setItem("phase7_settings_fallback_token", fallbackTokenEl.value.trim());
              localStorage.setItem("phase7_settings_operator", operatorEl.value.trim());
              localStorage.setItem("phase7_settings_note", noteEl.value);
            };

            const request = async (path, options = {}) => {
              saveDraft();
              const fallbackToken = fallbackTokenEl.value.trim();
              const execute = async (useFallbackToken = false) => {
                const headers = { ...(options.headers || {}) };
                if (useFallbackToken && fallbackToken) {
                  headers.Authorization = `Bearer ${fallbackToken}`;
                }
                const response = await fetch(apiUrl(path), {
                  ...options,
                  headers,
                  credentials: "same-origin",
                });
                const text = await response.text();
                let body = null;
                try {
                  body = text ? JSON.parse(text) : null;
                } catch (_error) {
                  body = text;
                }
                return { response, body, text };
              };

              let usedFallbackToken = false;
              let { response, body, text } = await execute(false);
              if (response.status === 401 && fallbackToken) {
                usedFallbackToken = true;
                ({ response, body, text } = await execute(true));
              }
              if (!response.ok) {
                if (response.status === 401) {
                  throw new Error(authErrorMessage(usedFallbackToken));
                }
                const detail = body && typeof body === "object" && body.detail ? body.detail : text || response.statusText;
                throw new Error(detail);
              }
              return body;
            };
            const setButtonBusy = (button, busy, pendingLabel = "处理中...") => {
              if (!button) return;
              if (!button.dataset.defaultLabel) {
                button.dataset.defaultLabel = button.textContent.trim();
              }
              button.disabled = busy;
              button.setAttribute("aria-busy", busy ? "true" : "false");
              button.textContent = busy ? pendingLabel : button.dataset.defaultLabel;
            };
            const withButtonBusy = async (button, pendingLabel, work) => {
              if (!button || button.disabled) return;
              setButtonBusy(button, true, pendingLabel);
              try {
                await work();
              } catch (error) {
                setStatus("操作失败", "warn");
                renderOutput(error.message || String(error));
              } finally {
                setButtonBusy(button, false);
              }
            };

            const buildInput = (setting) => {
              const inputId = `setting-${setting.key}`;
              if (setting.value_type === "boolean") {
                const checked = setting.effective_value ? "checked" : "";
                return `
                  <label for="${inputId}">当前值</label>
                  <label class="checkbox" for="${inputId}">
                    <input id="${inputId}" type="checkbox" ${checked} />
                    <span>启用</span>
                  </label>
                `;
              }
              if (setting.value_type === "enum") {
                const options = (setting.options || [])
                  .map((item) => {
                    const selected = item.value === setting.effective_value ? "selected" : "";
                    return `<option value="${escapeHtml(item.value)}" ${selected}>${escapeHtml(item.label)} (${escapeHtml(item.value)})</option>`;
                  })
                  .join("");
                return `
                  <label for="${inputId}">当前值</label>
                  <select id="${inputId}">${options}</select>
                `;
              }
              const value = setting.value_type === "integer_list"
                ? formatValue(setting.effective_value, setting.value_type)
                : escapeHtml(formatValue(setting.effective_value, setting.value_type));
              return `
                <label for="${inputId}">${setting.value_type === "integer_list" ? "当前值（逗号分隔）" : "当前值"}</label>
                <input id="${inputId}" type="text" value="${value}" />
              `;
            };

            const renderCategories = (settings) => {
              if (!settings.length) {
                categoriesEl.innerHTML = '<div class="empty">没有可配置的运行参数。</div>';
                return;
              }
              const groups = new Map();
              settings.forEach((setting) => {
                const category = setting.category || "other";
                if (!groups.has(category)) groups.set(category, []);
                groups.get(category).push(setting);
              });
              categoriesEl.innerHTML = Array.from(groups.entries()).map(([category, items]) => `
                <section class="category">
                  <h3>${escapeHtml(CATEGORY_LABELS[category] || category)}</h3>
                  <div class="setting-grid">
                    ${items.map((setting) => `
                      <article class="setting-card" data-key="${escapeHtml(setting.key)}" data-value-type="${escapeHtml(setting.value_type)}">
                        <div>
                          <h4>${escapeHtml(setting.label)}</h4>
                          <p>${escapeHtml(setting.description)}</p>
                        </div>
                        <div>
                          ${buildInput(setting)}
                        </div>
                        <p class="card-note">当前看到的是实际生效值。想看来源和覆盖关系，再展开下面这块。</p>
                        <details class="fold">
                          <summary>查看来源与生效值</summary>
                          <div class="setting-meta">
                            <div><strong>环境默认：</strong> ${escapeHtml(formatValue(setting.default_value, setting.value_type))}</div>
                            <div><strong>数据库覆盖：</strong> ${setting.has_override ? escapeHtml(formatValue(setting.stored_value, setting.value_type)) : "无"}</div>
                            <div><strong>实际生效：</strong> ${escapeHtml(formatValue(setting.effective_value, setting.value_type))}</div>
                            <div><strong>最后更新时间：</strong> ${setting.updated_at || "无"}</div>
                          </div>
                        </details>
                        <div class="setting-actions">
                          <button data-action="save">保存</button>
                          <button data-action="reset" class="ghost">恢复默认</button>
                        </div>
                      </article>
                    `).join("")}
                  </div>
                </section>
              `).join("");
            };

            const renderRuntimeStatus = (payload) => {
              currentRuntimeStatus = payload;
              const envItems = payload.environment || [];
              if (!envItems.length) {
                runtimeStatusEl.innerHTML = '<div class="empty">没有环境状态可展示。</div>';
              } else {
                const groups = new Map();
                envItems.forEach((item) => {
                  const category = item.category || "other";
                  if (!groups.has(category)) groups.set(category, []);
                  groups.get(category).push(item);
                });
                runtimeStatusEl.innerHTML = Array.from(groups.entries()).map(([category, items]) => `
                  <section class="category">
                    <h3>${escapeHtml(RUNTIME_CATEGORY_LABELS[category] || category)}</h3>
                    <div class="env-grid">
                      ${items.map((item) => `
                        <article class="env-card">
                          <div class="env-top">
                            <strong>${escapeHtml(item.label)}</strong>
                            <span class="env-badge ${item.required && !item.configured ? "warn" : ""}">
                              ${item.configured ? "已配置" : (item.required ? "缺失" : "未配置")}
                            </span>
                          </div>
                          <code>${escapeHtml(item.key)}</code>
                          <div class="hint">${item.secret ? "密钥类配置不展示明文。" : escapeHtml(item.preview || "无预览")}</div>
                          <div class="hint">${item.note ? escapeHtml(item.note) : (item.required ? "当前阶段要求存在。" : "当前为可选项。")}</div>
                        </article>
                      `).join("")}
                    </div>
                  </section>
                `).join("");
              }

              const alerts = payload.alerts || {};
              if (alerts.enabled) {
                alertHintEl.textContent = `告警已启用 · ${alerts.destination_preview || "Webhook 已配置"}。可以发一条测试消息。`;
              } else {
                alertHintEl.textContent = alerts.note || "当前未配置 ALERT_WEBHOOK_URL，测试告警按钮会返回错误。";
              }
            };

            const parseValueFromCard = (setting, card) => {
              const input = card.querySelector(`#setting-${CSS.escape(setting.key)}`);
              if (!input) throw new Error("设置输入框不存在。");
              if (setting.value_type === "boolean") return Boolean(input.checked);
              if (setting.value_type === "integer_list") return input.value.trim();
              return input.value.trim();
            };

            const loadSettings = async () => {
              const settings = await request("/api/v1/admin/settings");
              currentSettings = settings;
              renderCategories(settings);
              return settings;
            };

            const loadRuntimeStatus = async () => {
              const payload = await request("/api/v1/admin/runtime-status");
              renderRuntimeStatus(payload);
              return payload;
            };

            const loadAll = async () => {
              saveDraft();
              setStatus("加载中");
              setDataBusy(true);
              try {
                const [settings, runtimeStatus] = await Promise.all([loadSettings(), loadRuntimeStatus()]);
                renderOverview(settings, runtimeStatus);
                renderOutput({ settings, runtime_status: runtimeStatus });
                setStatus(`已加载 · ${settings.length} 项设置 / ${runtimeStatus.environment.length} 项环境状态`);
              } finally {
                setDataBusy(false);
              }
            };

            const updateSetting = async (setting, card, resetToDefault = false) => {
              saveDraft();
              setStatus(resetToDefault ? "恢复默认中" : "保存中");
              const payload = {
                operator: operatorEl.value.trim() || "admin-console",
                note: noteEl.value.trim() || null,
                reset_to_default: resetToDefault,
              };
              if (!resetToDefault) payload.value = parseValueFromCard(setting, card);
              const result = await request(`/api/v1/admin/settings/${encodeURIComponent(setting.key)}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
              });
              renderOutput(result);
              await loadAll();
              setStatus(resetToDefault ? "已恢复默认" : "已保存");
            };

            document.getElementById("refresh").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "刷新中...", async () => {
                await loadAll();
              });
            });

            document.getElementById("send-alert").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "发送中...", async () => {
                saveDraft();
                setStatus("发送测试");
                const result = await request("/api/v1/admin/alerts/test", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    operator: operatorEl.value.trim() || "admin-console",
                    note: noteEl.value.trim() || null,
                  }),
                });
                renderOutput(result);
                setStatus("测试告警已发送");
              });
            });

            document.getElementById("clear-output").addEventListener("click", () => {
              renderOutput("等待请求。");
              setStatus("空闲");
            });

            [fallbackTokenEl, operatorEl, noteEl].forEach((element) => {
              element.addEventListener("input", saveDraft);
            });

            categoriesEl.addEventListener("click", (event) => {
              const button = event.target.closest("button[data-action]");
              if (!button) return;
              const card = button.closest(".setting-card");
              if (!card) return;
              const settingKey = card.dataset.key;
              const setting = currentSettings.find((item) => item.key === settingKey);
              if (!setting) return;
              withButtonBusy(button, button.dataset.action === "reset" ? "恢复中..." : "保存中...", async () => {
                await updateSetting(setting, card, button.dataset.action === "reset");
              });
            });

            readDraft();
            renderOverview([], null);
            loadAll().catch((error) => {
              setStatus("加载失败", "warn");
              renderOutput(error.message || String(error));
            });
          </script>
        </body>
        </html>
        """
    )
    return (
        html.replace("__ADMIN_NAV_STYLES__", admin_section_nav_styles()).replace(
            "__ADMIN_SECTION_NAV__", admin_section_nav("settings")
        )
    )
