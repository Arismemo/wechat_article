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
from app.schemas.admin_monitor import AdminMonitorSnapshotResponse
from app.schemas.ingest import IngestLinkRequest, IngestLinkResponse
from app.schemas.internal import ManualReviewActionResponse, Phase4EnqueueResponse, WechatPushResponse
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
    return dedent(
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
              color: var(--text);
              font-family: "PingFang SC", "Noto Serif SC", serif;
              background:
                radial-gradient(circle at top left, rgba(244, 210, 147, 0.58), transparent 24%),
                radial-gradient(circle at top right, rgba(168, 209, 196, 0.42), transparent 26%),
                linear-gradient(145deg, #efe5d7 0%, #f7f3ec 42%, #eadfcd 100%);
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
            .hero-top {{
              display: flex;
              justify-content: space-between;
              gap: 16px;
              align-items: flex-start;
              flex-wrap: wrap;
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
              gap: 8px;
            }}
            .hero-copy p {{
              margin: 0;
              max-width: 760px;
              color: var(--muted);
              line-height: 1.7;
            }}
            .steps {{
              display: grid;
              grid-template-columns: repeat(3, minmax(0, 1fr));
              gap: 12px;
            }}
            .step {{
              display: grid;
              gap: 8px;
              padding: 14px 16px;
              border-radius: 20px;
              background: var(--paper-soft);
              border: 1px solid var(--line);
            }}
            .step strong {{
              font-size: 14px;
            }}
            .step span {{
              color: var(--muted);
              font-size: 13px;
              line-height: 1.6;
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
            .panel-head {{
              display: flex;
              justify-content: space-between;
              align-items: center;
              gap: 12px;
              margin-bottom: 14px;
            }}
            .panel h2 {{
              margin: 0;
              font-size: 19px;
            }}
            .mini {{
              color: var(--muted);
              font-size: 13px;
            }}
            .composer {{
              display: grid;
              gap: 12px;
            }}
            .composer-row {{
              display: grid;
              grid-template-columns: minmax(0, 1fr) 110px 130px;
              gap: 10px;
            }}
            input, button {{
              width: 100%;
              font: inherit;
              border-radius: 999px;
            }}
            input {{
              border: 1px solid var(--line);
              background: #fffdf9;
              padding: 14px 18px;
              color: var(--text);
            }}
            input:focus {{
              outline: 2px solid rgba(31, 93, 83, 0.18);
              border-color: rgba(31, 93, 83, 0.4);
            }}
            button {{
              border: none;
              padding: 14px 16px;
              cursor: pointer;
              background: var(--accent);
              color: #f7faf8;
              transition: transform 120ms ease, background 120ms ease, opacity 120ms ease;
            }}
            button:hover {{
              background: var(--accent-strong);
              transform: translateY(-1px);
            }}
            button.secondary {{
              background: #dfceb3;
              color: #2f261d;
            }}
            button.ghost {{
              background: transparent;
              border: 1px solid rgba(31, 93, 83, 0.22);
              color: var(--accent-strong);
            }}
            button.warn {{
              background: var(--gold);
            }}
            button.danger {{
              background: var(--danger);
            }}
            button:disabled {{
              opacity: 0.48;
              cursor: not-allowed;
              transform: none;
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
            .metrics {{
              display: grid;
              grid-template-columns: repeat(4, minmax(0, 1fr));
              gap: 10px;
            }}
            .metric {{
              padding: 14px;
              border-radius: 20px;
              border: 1px solid var(--line);
              background: #fffdf9;
            }}
            .metric strong {{
              display: block;
              color: var(--muted);
              font-size: 12px;
              font-weight: 500;
              margin-bottom: 8px;
            }}
            .metric span {{
              display: block;
              font-size: 30px;
              line-height: 1;
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
            .advanced-links a {{
              color: var(--accent-strong);
              text-decoration: none;
              border-bottom: 1px solid rgba(31, 93, 83, 0.22);
              font-size: 13px;
            }}
            .task-list {{
              display: grid;
              gap: 10px;
              max-height: 780px;
              overflow: auto;
              padding-right: 4px;
            }}
            .task-card {{
              display: grid;
              gap: 8px;
              padding: 14px 15px;
              border-radius: 20px;
              border: 1px solid var(--line);
              background: #fffdf9;
              cursor: pointer;
              transition: transform 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
            }}
            .task-card:hover {{
              transform: translateY(-1px);
              border-color: rgba(31, 93, 83, 0.35);
              box-shadow: 0 12px 26px rgba(58, 40, 18, 0.08);
            }}
            .task-card.selected {{
              border-color: rgba(31, 93, 83, 0.45);
              box-shadow: 0 14px 28px rgba(31, 93, 83, 0.11);
            }}
            .task-title {{
              font-size: 16px;
              line-height: 1.45;
            }}
            .task-meta {{
              color: var(--muted);
              font-size: 12px;
              line-height: 1.6;
              word-break: break-all;
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
            .detail-grid {{
              display: grid;
              gap: 18px;
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
              grid-template-columns: repeat(4, minmax(0, 1fr));
              gap: 10px;
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
            .footer-note {{
              color: var(--muted);
              font-size: 12px;
            }}
            @media (max-width: 1080px) {{
              .layout {{ grid-template-columns: 1fr; }}
              .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
              .action-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
              .composer-row {{ grid-template-columns: 1fr; }}
            }}
            @media (max-width: 720px) {{
              main {{ padding: 18px 14px 32px; }}
              h1 {{ font-size: 32px; }}
              .steps {{ grid-template-columns: 1fr; }}
              .metrics {{ grid-template-columns: 1fr; }}
              .kv-grid {{ grid-template-columns: 1fr; }}
              .action-grid {{ grid-template-columns: 1fr; }}
            }}
          </style>
        </head>
        <body>
          <main>
            <div class="shell">
              <section class="hero">
                <div class="hero-top">
                  <div class="hero-copy">
                    <span class="badge">PRIMARY CONTROL ROOM</span>
                    <h1>微信文章工厂</h1>
                    <p>贴链接，等一下，看结果。</p>
                  </div>
                  <div class="status-line">
                    <span class="status-chip" id="auto-refresh">自动刷新中</span>
                    <span class="mini" id="flash-message">准备好了。</span>
                  </div>
                </div>
                <div class="steps">
                  <div class="step">
                    <strong>1. 贴链接</strong>
                    <span>把微信文章链接贴进来，点一次“开始处理”。</span>
                  </div>
                  <div class="step">
                    <strong>2. 看进度</strong>
                    <span>左边会自动刷新。处理中、卡住、完成，一眼就能看见。</span>
                  </div>
                  <div class="step">
                    <strong>3. 做动作</strong>
                    <span>需要你决定时，只会剩下几个按钮：重写、通过、推草稿。</span>
                  </div>
                </div>
              </section>

              <div class="layout">
                <section class="stack">
                  <section class="panel">
                    <div class="panel-head">
                      <h2>开始一个任务</h2>
                      <span class="mini">手机快捷指令只是附加入口</span>
                    </div>
                    <div class="composer">
                      <div class="composer-row">
                        <input id="ingest-url" type="url" placeholder="把微信文章链接贴在这里" autocomplete="off" />
                        <button id="paste-button" class="secondary" type="button">粘贴</button>
                        <button id="ingest-button" type="button">开始处理</button>
                      </div>
                      <div class="footer-note">默认直接走完整流程。处理通过后会自动进入微信草稿箱。</div>
                    </div>
                  </section>

                  <section class="panel">
                    <div class="panel-head">
                      <h2>最近任务</h2>
                      <span class="mini" id="task-count">0 个</span>
                    </div>
                    <div class="task-toolbar">
                      <div class="filter-row">
                        <button class="pill active" data-filter="all" type="button">全部</button>
                        <button class="pill" data-filter="doing" type="button">处理中</button>
                        <button class="pill" data-filter="waiting" type="button">等我处理</button>
                        <button class="pill" data-filter="done" type="button">已进草稿</button>
                        <button class="pill" data-filter="failed" type="button">失败</button>
                      </div>
                      <input id="task-search" type="search" placeholder="搜标题、链接或任务号" autocomplete="off" />
                      <div class="advanced-links">
                        <a href="/admin/settings" target="_blank" rel="noreferrer">设置</a>
                        <a href="/admin/console" target="_blank" rel="noreferrer">监控详情</a>
                        <a href="/admin/phase5" target="_blank" rel="noreferrer">审核台</a>
                        <a href="/admin/phase6" target="_blank" rel="noreferrer">反馈台</a>
                      </div>
                    </div>
                    <div class="task-list" id="task-list">
                      <div class="empty">还没有任务。</div>
                    </div>
                  </section>
                </section>

                <section class="stack">
                  <section class="panel">
                    <div class="panel-head">
                      <h2>今天怎么样</h2>
                      <span class="mini" id="generated-at">刚刚更新</span>
                    </div>
                    <div class="metrics">
                      <div class="metric"><strong>处理中</strong><span id="metric-active">0</span></div>
                      <div class="metric"><strong>等你处理</strong><span id="metric-manual">0</span></div>
                      <div class="metric"><strong>已进草稿</strong><span id="metric-draft">0</span></div>
                      <div class="metric"><strong>失败</strong><span id="metric-failed">0</span></div>
                    </div>
                  </section>

                  <section class="panel">
                    <div class="panel-head">
                      <h2>任务详情</h2>
                      <span class="mini" id="selected-task-code">先点左边任意一条</span>
                    </div>
                    <div class="detail-grid" id="task-detail">
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
            const WAITING = new Set(["needs_manual_review", "needs_regenerate", "review_passed"]);
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
            }};

            const elements = {{
              flashMessage: document.getElementById("flash-message"),
              autoRefresh: document.getElementById("auto-refresh"),
              ingestUrl: document.getElementById("ingest-url"),
              ingestButton: document.getElementById("ingest-button"),
              pasteButton: document.getElementById("paste-button"),
              taskSearch: document.getElementById("task-search"),
              taskCount: document.getElementById("task-count"),
              taskList: document.getElementById("task-list"),
              selectedTaskCode: document.getElementById("selected-task-code"),
              taskDetail: document.getElementById("task-detail"),
              generatedAt: document.getElementById("generated-at"),
              metricActive: document.getElementById("metric-active"),
              metricManual: document.getElementById("metric-manual"),
              metricDraft: document.getElementById("metric-draft"),
              metricFailed: document.getElementById("metric-failed"),
              filterButtons: Array.from(document.querySelectorAll("[data-filter]")),
            }};

            const escapeHtml = (value) => (value || "")
              .replaceAll("&", "&amp;")
              .replaceAll("<", "&lt;")
              .replaceAll(">", "&gt;")
              .replaceAll('"', "&quot;")
              .replaceAll("'", "&#39;");

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

            const statusLabel = (status) => STATUS_LABELS[status] || status || "未知";

            const statusTone = (status) => {{
              if (DONE.has(status)) return "done";
              if (FAILED.has(status)) return "fail";
              if (WAITING.has(status)) return "waiting";
              return "";
            }};

            const setFlashMessage = (message, tone = "") => {{
              elements.flashMessage.textContent = message;
              elements.autoRefresh.className = `status-chip ${{tone}}`.trim();
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
              const workspace = state.snapshot?.workspace;
              if (workspace && workspace.task_id === state.selectedTaskId) return workspace;
              return currentTasks().find((item) => item.task_id === state.selectedTaskId) || workspace || null;
            }};

            const matchesFilter = (task) => {{
              if (state.filter === "doing" && !ACTIVE.has(task.status)) return false;
              if (state.filter === "waiting" && !WAITING.has(task.status)) return false;
              if (state.filter === "done" && !DONE.has(task.status)) return false;
              if (state.filter === "failed" && !FAILED.has(task.status)) return false;
              if (!state.search) return true;
              const needle = state.search.toLowerCase();
              return [
                task.title || "",
                task.source_url || "",
                task.task_code || "",
              ].some((value) => value.toLowerCase().includes(needle));
            }};

            const filteredTasks = () => currentTasks().filter(matchesFilter);

            const syncUrl = () => {{
              const url = new URL(window.location.href);
              if (state.selectedTaskId) {{
                url.searchParams.set("task_id", state.selectedTaskId);
              }} else {{
                url.searchParams.delete("task_id");
              }}
              window.history.replaceState({{}}, "", url);
            }};

            const renderSummary = () => {{
              const summary = state.snapshot?.summary;
              if (!summary) return;
              elements.metricActive.textContent = summary.filtered_active;
              elements.metricManual.textContent = summary.filtered_manual;
              elements.metricDraft.textContent = summary.filtered_draft_saved;
              elements.metricFailed.textContent = summary.filtered_failed;
              elements.generatedAt.textContent = `${{formatDateTime(summary.generated_at)}} 更新`;
            }};

            const renderTaskList = () => {{
              const tasks = filteredTasks();
              elements.taskCount.textContent = `${{tasks.length}} 个`;
              if (!tasks.length) {{
                elements.taskList.innerHTML = '<div class="empty">这里还没有符合筛选的任务。</div>';
                return;
              }}
              elements.taskList.innerHTML = tasks.map((task) => {{
                const selected = task.task_id === state.selectedTaskId ? "selected" : "";
                const title = escapeHtml(task.title || task.source_url || "未命名任务");
                const meta = escapeHtml(task.source_url || task.task_code);
                return `
                  <article class="task-card ${{selected}}" data-task-id="${{task.task_id}}">
                    <div class="status-line">
                      <span class="status-chip ${{statusTone(task.status)}}">${{statusLabel(task.status)}}</span>
                      <span class="mini">${{task.progress}}%</span>
                    </div>
                    <div class="task-title">${{title}}</div>
                    <div class="progress-track"><div class="progress-fill" style="width:${{Math.max(task.progress || 0, 4)}}%"></div></div>
                    <div class="task-meta">${{meta}}</div>
                    <div class="task-meta">任务号：${{escapeHtml(task.task_code)}} · 更新：${{formatDateTime(task.updated_at)}}</div>
                  </article>
                `;
              }}).join("");
            }};

            const renderTaskDetail = () => {{
              const task = findSelectedTask();
              if (!task) {{
                elements.selectedTaskCode.textContent = "先点左边任意一条";
                elements.taskDetail.innerHTML = '<div class="empty">选中一条任务后，这里会告诉你现在到了哪一步，以及下一步该按哪个按钮。</div>';
                return;
              }}
              elements.selectedTaskCode.textContent = task.task_code || task.task_id;
              const workspace = state.snapshot?.workspace && state.snapshot.workspace.task_id === task.task_id
                ? state.snapshot.workspace
                : null;
              const latestGeneration = workspace?.generations?.[0] || null;
              const sourceUrl = escapeHtml(task.source_url || "");
              const title = escapeHtml(task.title || workspace?.source_article?.title || "未命名任务");
              const hint = escapeHtml(nextStepText(task));
              const digest = escapeHtml(latestGeneration?.digest || "");
              const mediaId = escapeHtml(task.wechat_media_id || workspace?.wechat_media_id || "还没有");
              const canRetry = !DONE.has(task.status);
              const canApprove = task.status === "needs_manual_review";
              const canReject = ["needs_manual_review", "review_passed"].includes(task.status);
              const canPush = task.status === "review_passed";
              elements.taskDetail.innerHTML = `
                <div class="summary-block">
                  <div class="summary-title">
                    <div class="status-line">
                      <span class="status-chip ${{statusTone(task.status)}}">${{statusLabel(task.status)}}</span>
                      <span class="mini">进度 ${{task.progress}}%</span>
                    </div>
                    <h3>${{title}}</h3>
                    <a href="${{sourceUrl}}" target="_blank" rel="noreferrer">${{sourceUrl}}</a>
                  </div>
                  <div class="big-hint">
                    <strong>现在该做什么</strong>
                    <span>${{hint}}</span>
                  </div>
                </div>

                <div class="kv-grid">
                  <div class="kv"><strong>任务状态</strong><span>${{statusLabel(task.status)}}</span></div>
                  <div class="kv"><strong>更新时间</strong><span>${{formatDateTime(task.updated_at)}}</span></div>
                  <div class="kv"><strong>参考文章</strong><span>${{task.related_article_count || 0}} 篇</span></div>
                  <div class="kv"><strong>微信草稿</strong><span>${{mediaId}}</span></div>
                </div>

                <div class="action-grid">
                  <button type="button" id="retry-button" class="secondary" ${{canRetry ? "" : "disabled"}}>重新跑一版</button>
                  <button type="button" id="approve-button" ${{canApprove ? "" : "disabled"}}>通过</button>
                  <button type="button" id="reject-button" class="warn" ${{canReject ? "" : "disabled"}}>驳回重写</button>
                  <button type="button" id="push-button" class="ghost" ${{canPush ? "" : "disabled"}}>推草稿</button>
                </div>

                <div class="latest-box">
                  <strong>最新一稿</strong>
                  <p>${{escapeHtml(latestGeneration?.title || "还没有生成稿件")}}</p>
                  <p class="mini">${{escapeHtml(latestGeneration?.prompt_version || "")}}</p>
                  <p>${{digest || "这里会显示最新一稿的摘要。"}}</p>
                </div>

                ${{task.error ? `<div class="latest-box"><strong>报错</strong><p>${{escapeHtml(task.error)}}</p></div>` : ""}}
              `;

              document.getElementById("retry-button")?.addEventListener("click", () => runAction("retry", task.task_id));
              document.getElementById("approve-button")?.addEventListener("click", () => runAction("approve", task.task_id));
              document.getElementById("reject-button")?.addEventListener("click", () => runAction("reject", task.task_id));
              document.getElementById("push-button")?.addEventListener("click", () => runAction("push-draft", task.task_id));
            }};

            const render = () => {{
              renderSummary();
              renderTaskList();
              renderTaskDetail();
              elements.filterButtons.forEach((button) => {{
                button.classList.toggle("active", button.dataset.filter === state.filter);
              }});
            }};

            const loadSnapshot = async () => {{
              const params = new URLSearchParams({{ limit: "18" }});
              if (state.selectedTaskId) params.set("selected_task_id", state.selectedTaskId);
              const response = await fetch(`/admin/api/home-snapshot?${{params.toString()}}`, {{
                headers: {{ Accept: "application/json" }},
              }});
              if (!response.ok) {{
                throw new Error("加载任务列表失败。");
              }}
              state.snapshot = await response.json();
              if (!state.selectedTaskId && state.snapshot.tasks.length) {{
                state.selectedTaskId = state.snapshot.tasks[0].task_id;
              }}
              if (
                state.selectedTaskId &&
                !state.snapshot.workspace &&
                !state.snapshot.tasks.some((item) => item.task_id === state.selectedTaskId)
              ) {{
                state.selectedTaskId = state.snapshot.tasks[0]?.task_id || null;
              }}
              syncUrl();
              render();
            }};

            const apiPost = async (url, payload) => {{
              const response = await fetch(url, {{
                method: "POST",
                headers: {{
                  "Content-Type": "application/json",
                  Accept: "application/json",
                }},
                body: payload ? JSON.stringify(payload) : JSON.stringify({{}}),
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

            const runAction = async (action, taskId) => {{
              const labels = {{
                retry: "已重新入队。",
                approve: "已通过。",
                reject: "已改成重写。",
                "push-draft": "已推送到微信草稿箱。",
              }};
              try {{
                setFlashMessage("正在处理…");
                await apiPost(`/admin/api/tasks/${{taskId}}/${{action}}`);
                state.selectedTaskId = taskId;
                await loadSnapshot();
                setFlashMessage(labels[action] || "完成了。", action === "push-draft" ? "done" : "");
              }} catch (error) {{
                setFlashMessage(error.message || "操作失败。", "fail");
              }}
            }};

            const ingestTask = async () => {{
              const url = elements.ingestUrl.value.trim();
              if (!url) {{
                setFlashMessage("先贴一个微信文章链接。", "waiting");
                elements.ingestUrl.focus();
                return;
              }}
              try {{
                elements.ingestButton.disabled = true;
                setFlashMessage("任务已提交，开始排队。");
                const data = await apiPost("/admin/api/ingest", {{ url }});
                state.selectedTaskId = data.task_id;
                elements.ingestUrl.value = "";
                await loadSnapshot();
                setFlashMessage("任务已收到，左边会自己刷新。");
              }} catch (error) {{
                setFlashMessage(error.message || "提交失败。", "fail");
              }} finally {{
                elements.ingestButton.disabled = false;
              }}
            }};

            elements.filterButtons.forEach((button) => {{
              button.addEventListener("click", () => {{
                state.filter = button.dataset.filter;
                render();
              }});
            }});

            elements.taskSearch.addEventListener("input", (event) => {{
              state.search = event.target.value.trim();
              render();
            }});

            elements.taskList.addEventListener("click", (event) => {{
              const card = event.target.closest("[data-task-id]");
              if (!card) return;
              state.selectedTaskId = card.dataset.taskId;
              syncUrl();
              loadSnapshot().catch((error) => setFlashMessage(error.message || "加载任务失败。", "fail"));
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
                  setFlashMessage("已粘贴。");
                }}
              }} catch (_error) {{
                setFlashMessage("请手动粘贴链接。", "waiting");
              }}
            }});

            const boot = async () => {{
              try {{
                await loadSnapshot();
                setFlashMessage("自动刷新中。");
              }} catch (error) {{
                setFlashMessage(error.message || "页面初始化失败。", "fail");
              }}
              window.setInterval(() => {{
                loadSnapshot().catch(() => setFlashMessage("刷新失败，稍后会再试。", "fail"));
              }}, 4000);
            }};

            boot();
          </script>
        </body>
        </html>
        """
    )


@router.get("/admin/console", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def unified_console() -> str:
    return dedent(
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
              color: var(--text);
              font-family: "PingFang SC", "Noto Serif SC", serif;
              min-height: 100vh;
              background:
                radial-gradient(circle at top left, rgba(255, 229, 175, 0.5), transparent 26%),
                radial-gradient(circle at bottom right, rgba(178, 222, 208, 0.42), transparent 28%),
                linear-gradient(140deg, #efe8dd 0%, #f6f2ea 44%, #ebe1d2 100%);
            }
            main {
              max-width: 1440px;
              margin: 0 auto;
              padding: 28px 20px 54px;
            }
            .hero {
              display: grid;
              gap: 10px;
              margin-bottom: 18px;
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
            .status {
              display: inline-flex;
              padding: 7px 12px;
              border-radius: 999px;
              background: rgba(37, 93, 82, 0.12);
              color: var(--accent-dark);
              font-size: 12px;
              margin-bottom: 12px;
            }
            .grid {
              display: grid;
              gap: 10px;
            }
            .grid.two {
              grid-template-columns: repeat(2, minmax(0, 1fr));
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
            button {
              border: none;
              padding: 12px 16px;
              cursor: pointer;
              background: var(--accent);
              color: #f8fbf7;
            }
            button:hover {
              background: var(--accent-dark);
            }
            button.secondary {
              background: #d8c8aa;
              color: #2c241a;
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
            .metrics {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
              gap: 10px;
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
            @media (max-width: 1040px) {
              .layout {
                grid-template-columns: 1fr;
              }
            }
            @media (max-width: 720px) {
              .hero h1 { font-size: 30px; }
              .actions { grid-template-columns: 1fr; }
              .grid.two, .detail-grid, .task-grid { grid-template-columns: 1fr; }
            }
          </style>
        </head>
        <body>
          <main>
            <section class="hero">
              <span class="eyebrow">UNIFIED OPERATIONS CONSOLE</span>
              <h1>统一任务监控首页</h1>
              <p>这一页只负责监控和检索，不替代 Phase 5 审核台或 Phase 6 反馈台。当前已接入 Phase 7C 的实时任务流和统计卡片，以及 Phase 7E 的队列与 worker 观测；优先通过 SSE 持续推送最新状态，掉线时再回退到手动刷新或轮询。</p>
              <div class="hero-links">
                <a href="/admin/phase5" target="_blank" rel="noreferrer">打开 Phase 5 审核台</a>
                <a href="/admin/phase6" target="_blank" rel="noreferrer">打开 Phase 6 反馈台</a>
              </div>
            </section>

            <section class="layout">
              <div class="stack">
                <section class="panel">
                  <h2>认证与刷新</h2>
                  <div class="grid">
                    <div>
                      <label for="token">Bearer Token</label>
                      <input id="token" type="password" placeholder="输入 API_BEARER_TOKEN" />
                    </div>
                    <div class="grid two">
                      <div>
                        <label for="poll-seconds">轮询秒数</label>
                        <input id="poll-seconds" type="number" min="3" max="60" value="5" />
                      </div>
                      <div>
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
                  <div class="grid">
                    <div>
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
                    <div>
                      <label for="source-filter">来源</label>
                      <select id="source-filter">
                        <option value="">全部来源</option>
                        <option value="wechat">wechat</option>
                        <option value="http">http</option>
                        <option value="other">other</option>
                      </select>
                    </div>
                    <div>
                      <label for="query-filter">搜索</label>
                      <input id="query-filter" type="text" placeholder="task_code / URL 关键词" />
                    </div>
                    <div>
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
                  <span class="status" id="status">空闲</span>
                  <h2>输出</h2>
                  <pre id="output">等待刷新...</pre>
                </section>
              </div>

              <div class="stack">
                <section class="panel">
                  <h2>任务总览</h2>
                  <div class="metrics" id="metrics">
                    <div class="metric-card"><strong>当前筛选</strong><span>0</span></div>
                  </div>
                </section>

                <section class="panel">
                  <h2>队列与 Worker 观测</h2>
                  <div class="hint" style="margin-bottom: 14px;">实时显示四条队列的 backlog、处理中任务和 worker 心跳。worker 超过阈值未上报时，会标为 stale 或 offline。</div>
                  <div class="ops-grid" id="operations">
                    <div class="hint">等待监控快照。</div>
                  </div>
                </section>

                <section class="panel">
                  <h2>状态分组看板</h2>
                  <div class="board" id="board">
                    <div class="hint">先输入 Bearer Token，再点“立即刷新”。</div>
                  </div>
                </section>

                <section class="panel">
                  <h2>任务详情</h2>
                  <div id="workspace">
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
            const outputEl = document.getElementById("output");
            const liveHintEl = document.getElementById("live-hint");

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

            const escapeHtml = (value) => {
              return String(value ?? "")
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#39;");
            };

            const setStatus = (text) => {
              statusEl.textContent = text;
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

            const request = async (path) => {
              const token = tokenEl.value.trim();
              if (!token) throw new Error("请先输入 Bearer Token");
              const response = await fetch(path, {
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
                boardEl.innerHTML = '<div class="hint">当前筛选条件下没有任务。</div>';
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
                      <article class="task-card">
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
                    <details>
                      <summary>展开最新正文</summary>
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
            };

            const renderMonitorSnapshot = (snapshot, { updateOutput = true, source = "manual" } = {}) => {
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
                setStatus(`实时中 · ${snapshot.tasks.length} 个任务`);
              } else {
                setStatus(`已刷新 · ${snapshot.tasks.length} 个任务`);
              }
            };

            const refreshAll = async () => {
              saveDraft();
              setStatus("刷新中");
              const snapshot = await request(`/api/v1/admin/monitor/snapshot?${buildSnapshotQuery()}`);
              renderMonitorSnapshot(snapshot, { updateOutput: true, source: "manual" });
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
                  setStatus("轮询失败");
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
                return;
              }
              if (!autoRefreshEl.checked) {
                setLiveHint("当前模式：自动更新已关闭");
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
                  setStatus("实时流解析失败");
                  renderOutput(error.message || String(error));
                }
              });
              monitorStream.onerror = () => {
                closeStream();
                setLiveHint("当前模式：SSE 中断，已回退轮询");
                restartTimer();
              };
            };

            document.getElementById("refresh-now").addEventListener("click", async () => {
              try {
                await refreshAll();
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("clear-selection").addEventListener("click", () => {
              selectedTaskId = "";
              saveDraft();
              workspaceEl.innerHTML = '<div class="hint">当前任务已清空。</div>';
              setStatus("空闲");
              restartRealtime();
            });

            [tokenEl, pollSecondsEl, limitEl, autoRefreshEl, statusFilterEl, sourceFilterEl, queryFilterEl, createdAfterEl, activeOnlyEl].forEach((element) => {
              const eventName = element === queryFilterEl ? "input" : "change";
              element.addEventListener(eventName, () => {
                saveDraft();
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
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            loadDraft();
            restartRealtime();
            if (tokenEl.value.trim()) {
              refreshAll().catch((error) => {
                setStatus("失败");
                renderOutput(error.message || String(error));
              });
            }
          </script>
        </body>
        </html>
        """
    )


@router.get("/admin/settings", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def settings_console() -> str:
    return dedent(
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
              font-family: "PingFang SC", "Noto Serif SC", serif;
              min-height: 100vh;
              background:
                radial-gradient(circle at top left, rgba(255, 229, 175, 0.5), transparent 26%),
                radial-gradient(circle at bottom right, rgba(178, 222, 208, 0.42), transparent 28%),
                linear-gradient(140deg, #efe8dd 0%, #f6f2ea 44%, #ebe1d2 100%);
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
              gap: 10px;
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
            .env-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
              gap: 14px;
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
            @media (max-width: 960px) {
              .layout { grid-template-columns: 1fr; }
            }
            @media (max-width: 720px) {
              .hero h1 { font-size: 30px; }
              .setting-actions, .actions { flex-direction: column; }
              button { width: 100%; }
            }
          </style>
        </head>
        <body>
          <main>
            <section class="hero">
              <span class="eyebrow">RUNTIME SETTINGS & STATUS</span>
              <h1>运行参数设置</h1>
              <p>这里只允许修改可以热覆盖的运行参数，例如写稿模型、审稿模型和自动反馈开关。数据库地址、第三方密钥、Bearer Token、微信 Secret 这类基础设施和敏感配置仍然留在 `.env`；Phase 7D 会在这里额外显示只读环境状态，并提供测试告警入口。</p>
            </section>

            <section class="layout">
              <div class="stack">
                <section class="panel">
                  <span class="status" id="status">等待加载</span>
                  <h2>认证与操作</h2>
                  <div>
                    <label for="token">Bearer Token</label>
                    <input id="token" type="password" placeholder="输入 API_BEARER_TOKEN" />
                  </div>
                  <div style="margin-top: 14px;">
                    <label for="operator">operator</label>
                    <input id="operator" type="text" value="admin-console" />
                  </div>
                  <div style="margin-top: 14px;">
                    <label for="note">变更备注</label>
                    <textarea id="note" placeholder="例如：将写稿模型切到新版本做小流量验证"></textarea>
                  </div>
                  <div class="actions">
                    <button id="refresh">刷新设置</button>
                    <button id="clear-output" class="secondary">清空输出</button>
                  </div>
                </section>

                <section class="panel">
                  <h2>边界说明</h2>
                  <ul class="list">
                    <li>这里的值会优先覆盖环境变量，但仅限少量运行参数。</li>
                    <li>密钥类值仍然只保留在服务器 `.env`，页面不显示也不支持改写。</li>
                    <li>Phase 4 仍然受 `WECHAT_ENABLE_DRAFT_PUSH` 总开关约束。</li>
                    <li>自动反馈切到 `http` 前，仍需在 `.env` 里配置 `FEEDBACK_SYNC_HTTP_URL` 与可选 `FEEDBACK_SYNC_API_KEY`。</li>
                  </ul>
                </section>

                <section class="panel">
                  <h2>告警测试</h2>
                  <div class="hint" id="alert-hint">请输入 Bearer Token 后刷新状态。若 `ALERT_WEBHOOK_URL` 未配置，这里会显示为不可用。</div>
                  <div class="actions">
                    <button id="send-alert">发送测试告警</button>
                  </div>
                </section>

                <section class="panel">
                  <h2>调试输出</h2>
                  <pre id="output">等待请求。</pre>
                </section>
              </div>

              <div class="stack">
                <section class="panel">
                  <h2>当前设置</h2>
                  <div class="hint" style="margin-bottom: 14px;">保存后新任务会读取最新运行参数；恢复默认会删除数据库覆盖值，重新回退到环境变量默认值。</div>
                  <div id="categories" class="categories">
                    <div class="empty">请输入 Bearer Token 后点击“刷新设置”。</div>
                  </div>
                </section>

                <section class="panel">
                  <h2>环境状态</h2>
                  <div class="hint" style="margin-bottom: 14px;">这里是只读环境状态面板。密钥不会明文展示，只告诉你当前是否已配置；普通 URL 和基础参数会显示简化预览。</div>
                  <div id="runtime-status" class="categories">
                    <div class="empty">请输入 Bearer Token 后点击“刷新设置”。</div>
                  </div>
                </section>
              </div>
            </section>
          </main>

          <script>
            const statusEl = document.getElementById("status");
            const outputEl = document.getElementById("output");
            const alertHintEl = document.getElementById("alert-hint");
            const tokenEl = document.getElementById("token");
            const operatorEl = document.getElementById("operator");
            const noteEl = document.getElementById("note");
            const categoriesEl = document.getElementById("categories");
            const runtimeStatusEl = document.getElementById("runtime-status");
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

            const setStatus = (text) => {
              statusEl.textContent = text;
            };

            const renderOutput = (value) => {
              outputEl.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
            };

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

            const readDraft = () => {
              tokenEl.value = localStorage.getItem("phase7_settings_token") || "";
              operatorEl.value = localStorage.getItem("phase7_settings_operator") || "admin-console";
              noteEl.value = localStorage.getItem("phase7_settings_note") || "";
            };

            const saveDraft = () => {
              localStorage.setItem("phase7_settings_token", tokenEl.value.trim());
              localStorage.setItem("phase7_settings_operator", operatorEl.value.trim());
              localStorage.setItem("phase7_settings_note", noteEl.value);
            };

            const request = async (path, options = {}) => {
              const token = tokenEl.value.trim();
              if (!token) throw new Error("请先输入 Bearer Token");
              const headers = {
                Authorization: `Bearer ${token}`,
                ...(options.headers || {}),
              };
              const response = await fetch(path, { ...options, headers });
              const text = await response.text();
              let body = null;
              try {
                body = text ? JSON.parse(text) : null;
              } catch (_error) {
                body = text;
              }
              if (!response.ok) {
                const detail = body && typeof body === "object" && body.detail ? body.detail : text || response.statusText;
                throw new Error(detail);
              }
              return body;
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
                        <div class="setting-meta">
                          <div><strong>环境默认：</strong> ${escapeHtml(formatValue(setting.default_value, setting.value_type))}</div>
                          <div><strong>数据库覆盖：</strong> ${setting.has_override ? escapeHtml(formatValue(setting.stored_value, setting.value_type)) : "无"}</div>
                          <div><strong>实际生效：</strong> ${escapeHtml(formatValue(setting.effective_value, setting.value_type))}</div>
                          <div><strong>最后更新时间：</strong> ${setting.updated_at || "无"}</div>
                        </div>
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
                alertHintEl.textContent = `告警已启用 · ${alerts.destination_preview || "Webhook 已配置"}。可以发送测试告警验证连通性。`;
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
              const [settings, runtimeStatus] = await Promise.all([loadSettings(), loadRuntimeStatus()]);
              renderOutput({ settings, runtime_status: runtimeStatus });
              setStatus(`已加载 · ${settings.length} 项设置 / ${runtimeStatus.environment.length} 项环境状态`);
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

            document.getElementById("refresh").addEventListener("click", () => {
              loadAll().catch((error) => {
                setStatus("加载失败");
                renderOutput(error.message || String(error));
              });
            });

            document.getElementById("send-alert").addEventListener("click", () => {
              saveDraft();
              setStatus("发送测试告警中");
              request("/api/v1/admin/alerts/test", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  operator: operatorEl.value.trim() || "admin-console",
                  note: noteEl.value.trim() || null,
                }),
              }).then((result) => {
                renderOutput(result);
                setStatus("测试告警已发送");
              }).catch((error) => {
                setStatus("测试告警失败");
                renderOutput(error.message || String(error));
              });
            });

            document.getElementById("clear-output").addEventListener("click", () => {
              renderOutput("等待请求。");
              setStatus("空闲");
            });

            [tokenEl, operatorEl, noteEl].forEach((element) => {
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
              updateSetting(setting, card, button.dataset.action === "reset").catch((error) => {
                setStatus("操作失败");
                renderOutput(error.message || String(error));
              });
            });

            readDraft();
            if (tokenEl.value.trim()) {
              loadAll().catch((error) => {
                setStatus("加载失败");
                renderOutput(error.message || String(error));
              });
            }
          </script>
        </body>
        </html>
        """
    )
