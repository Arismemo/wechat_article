from __future__ import annotations

import json
from datetime import datetime
from time import sleep
from textwrap import dedent
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.security import verify_admin_basic_auth
from app.db.session import get_db_session, get_session_factory
from app.api.admin_ui import (
    admin_hero_summary_card,
    admin_overview_card,
    admin_overview_strip,
    admin_page_hero,
    admin_shared_script_helpers,
    admin_shared_styles,
    render_admin_page,
)
from app.templating import render_template
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
    # 注：task_id 仅保留为查询参数（前端通过 JS 自行读取 URL），页面本体不做服务端插值，
    # 因此无论 task_id 取值，渲染结果逐字节一致。页面源自 Jinja2 模板（整段 {% raw %} 包裹），
    # 共享样式 / 脚本占位符由 render_admin_page 注入。
    html = render_template("admin/portal.html")
    return render_admin_page(html, "portal")


@router.get("/admin/console", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def unified_console() -> str:
    hero_html = admin_page_hero(
        eyebrow="ADVANCED OPERATIONS MONITOR",
        title="高级监控台",
        description="这是一张高级排障页，不是日常主入口。它专门负责看任务流、队列和 worker 健康；日常开任务、审稿和回收反馈，仍然回到总览主控台、审核台和反馈台处理。",
        status_aria_label="监控页状态",
        status_slot_html='<span class="status" id="status">等待连接</span>',
        status_message="默认复用后台会话。先拉一次监控快照，再决定是否开启自动实时更新。",
        summary_cards_html="".join(
            [
                admin_hero_summary_card("这页负责什么", "看任务流、队列与 worker 健康，快速定位哪一批任务最需要你介入。"),
                admin_hero_summary_card("日常入口在哪", "开任务回总览，审稿去 Phase 5，复盘反馈去 Phase 6。"),
                admin_hero_summary_card(
                    "当前建议",
                    "先拉一次监控快照，确认今天有哪些任务真正卡住了。",
                    wide=True,
                    content_id="hero-focus",
                ),
            ]
        ),
        hero_body_html=dedent(
            """\
            <div class="hero-warning" aria-label="使用边界提示">
              <span class="warning-kicker">只读排障页</span>
              <strong>不在这里做日常操作。这里只用于队列、worker 和任务卡点排查。</strong>
              <ul class="warning-list">
                <li>开新任务、看草稿、做删除，回总览主控台。</li>
                <li>人工通过 / 驳回 / 推送草稿，去 Phase 5 审核台。</li>
                <li>导入反馈、复盘效果、跑同步，去 Phase 6 反馈台。</li>
              </ul>
            </div>
            """
        ),
        hero_links_html=(
            '<div class="hero-links">'
            '<a href="/admin" target="_blank" rel="noreferrer">回到总览主控台</a>'
            '<a href="/admin/phase5" target="_blank" rel="noreferrer">打开 Phase 5 审核台</a>'
            '<a href="/admin/phase6" target="_blank" rel="noreferrer">打开 Phase 6 反馈台</a>'
            "</div>"
        ),
    )
    overview_html = admin_overview_strip(
        "",
        "".join(
            [
                admin_overview_card("任务", "0", value_id="overview-filtered-count"),
                admin_overview_card("待处理", "0", value_id="overview-manual-count"),
                admin_overview_card("队列", "等待快照", value_id="overview-ops-state"),
            ]
        ),
    )
    # 页面本体源自 Jinja2 模板（整段 {% raw %} 包裹，避免 JS ${...} 与 CSS 花括号被 Jinja 解析）；
    # __ADMIN_HERO__ / __ADMIN_OVERVIEW__ 占位符在下方按原逻辑替换，共享样式由 render_admin_page 注入。
    html = render_template("admin/console.html")
    return render_admin_page(
        html.replace("__ADMIN_HERO__", hero_html).replace("__ADMIN_OVERVIEW__", overview_html),
        "monitor",
    )


@router.get("/admin/pipeline", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def pipeline_console(response: Response) -> str:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    import json as _json
    from app.core.pipeline_registry import ARTICLE_PIPELINE, serialize_pipeline
    _registry_json = _json.dumps(serialize_pipeline(ARTICLE_PIPELINE), ensure_ascii=False)
    # 页面本体源自 Jinja2 模板（整段 {% raw %} 包裹，避免 JS ${...} 与 CSS 花括号被 Jinja 解析）；
    # __PIPELINE_REGISTRY_JSON__ 占位符在下方注入流程注册表，共享样式由 render_admin_page 注入。
    html = render_template("admin/pipeline.html")
    html = html.replace("__PIPELINE_REGISTRY_JSON__", _registry_json)
    return render_admin_page(html, "pipeline")


@router.get("/admin/settings", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def settings_console() -> str:
    return render_admin_page(
        render_template(
            "admin/settings.html",
            shared_styles=admin_shared_styles(),
            shared_script_helpers=admin_shared_script_helpers(),
        ),
        "settings",
    )
