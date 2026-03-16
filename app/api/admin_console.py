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
    render_admin_page,
)
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
            __ADMIN_SHARED_STYLES__

            /* 极简工作流样式 */
            .flow-container {{
              max-width: 720px;
              margin: 0 auto;
              padding: 32px 20px;
            }}

            /* 输入区 */
            .input-section {{
              margin-bottom: 32px;
            }}
            .input-bar {{
              display: flex;
              gap: 10px;
              align-items: center;
              background: var(--bg-card);
              border: 2px solid var(--border);
              border-radius: var(--radius-lg);
              padding: 8px 8px 8px 20px;
              box-shadow: var(--shadow-card);
              transition: border-color var(--transition), box-shadow var(--transition);
            }}
            .input-bar:focus-within {{
              border-color: var(--primary);
              box-shadow: 0 0 0 3px rgba(59,130,246,.12);
            }}
            .input-bar input {{
              flex: 1;
              border: none;
              outline: none;
              font-size: 15px;
              background: transparent;
              color: var(--text);
              line-height: 1.5;
            }}
            .input-bar input::placeholder {{
              color: var(--text-secondary);
              opacity: 0.6;
            }}
            .input-bar button {{
              flex-shrink: 0;
              padding: 10px 24px;
              border: none;
              border-radius: var(--radius-md);
              background: var(--primary);
              color: #fff;
              font-size: 14px;
              font-weight: 600;
              cursor: pointer;
              transition: background var(--transition);
            }}
            .input-bar button:hover {{ background: var(--primary-hover); }}
            .input-bar button:disabled {{
              opacity: 0.5;
              cursor: not-allowed;
            }}
            .input-error {{
              margin-top: 8px;
              padding: 8px 14px;
              border-radius: var(--radius-sm);
              background: var(--danger-soft);
              color: var(--danger);
              font-size: 13px;
              display: none;
            }}

            /* 计数条 */
            .count-bar {{
              display: flex;
              align-items: center;
              gap: 16px;
              margin-bottom: 16px;
              font-size: 13px;
              color: var(--text-secondary);
            }}
            .count-bar .count {{
              font-weight: 600;
              color: var(--text);
            }}
            .count-bar .dot {{
              width: 6px; height: 6px;
              border-radius: 50%;
              display: inline-block;
              margin-right: 4px;
            }}
            .count-bar .dot.blue {{ background: var(--primary); }}
            .count-bar .dot.orange {{ background: var(--warning); }}
            .count-bar .dot.red {{ background: var(--danger); }}
            .count-bar .dot.green {{ background: var(--success); }}

            /* 任务列表 */
            .task-list {{
              display: flex;
              flex-direction: column;
              gap: 8px;
            }}
            .task-empty {{
              text-align: center;
              padding: 48px 20px;
              color: var(--text-secondary);
              font-size: 14px;
            }}
            .task-empty .icon {{
              font-size: 40px;
              margin-bottom: 12px;
              opacity: 0.4;
            }}

            /* 任务卡片 */
            .task-card {{
              background: var(--bg-card);
              border: 1px solid var(--border);
              border-radius: var(--radius-md);
              padding: 14px 18px;
              cursor: pointer;
              transition: border-color var(--transition), box-shadow var(--transition);
              position: relative;
            }}
            .task-card:hover {{
              border-color: var(--primary);
              box-shadow: var(--shadow-card);
            }}
            .task-card.expanded {{
              border-color: var(--primary);
              box-shadow: 0 0 0 2px rgba(59,130,246,.08);
            }}
            .task-card-header {{
              display: grid;
              grid-template-columns: 1fr auto;
              align-items: center;
              min-height: 24px;
              gap: 12px;
            }}
            .task-card-info {{
              display: flex;
              align-items: center;
              gap: 10px;
              overflow: hidden;
            }}
            .task-status-dot {{
              width: 8px; height: 8px;
              border-radius: 50%;
              flex-shrink: 0;
            }}
            .task-status-dot.processing {{
              background: var(--primary);
              animation: pulse-dot 1.5s ease-in-out infinite;
            }}
            .task-status-dot.pending {{ background: var(--warning); }}
            .task-status-dot.done {{ background: var(--success); }}
            .task-status-dot.failed {{ background: var(--danger); }}
            @keyframes pulse-dot {{
              0%, 100% {{ opacity: 1; }}
              50% {{ opacity: 0.3; }}
            }}
            .task-title {{
              flex: 1;
              min-width: 0;
              font-size: 14px;
              font-weight: 500;
              color: var(--text);
              white-space: nowrap;
              overflow: hidden;
              text-overflow: ellipsis;
            }}
            .task-card.done-card .task-title {{
              color: var(--text-secondary);
            }}
            .task-status-label {{
              font-size: 12px;
              font-weight: 600;
              padding: 2px 8px;
              border-radius: 999px;
              white-space: nowrap;
            }}
            .task-status-label.processing {{
              background: var(--primary-soft);
              color: var(--primary);
            }}
            .task-status-label.pending {{
              background: var(--warning-soft);
              color: #B45309;
            }}
            .task-status-label.done {{
              background: var(--success-soft);
              color: #047857;
            }}
            .task-status-label.failed {{
              background: var(--danger-soft);
              color: var(--danger);
            }}
            .task-actions {{
              display: flex;
              gap: 6px;
              flex-shrink: 0;
            }}
            .task-actions button {{
              padding: 4px 12px;
              border: 1px solid var(--border);
              border-radius: var(--radius-sm);
              background: var(--bg-card);
              font-size: 12px;
              font-weight: 500;
              cursor: pointer;
              transition: all var(--transition);
            }}
            .task-actions .btn-primary {{
              background: var(--primary);
              color: #fff;
              border-color: var(--primary);
            }}
            .task-actions .btn-primary:hover {{
              background: var(--primary-hover);
            }}
            .task-actions .btn-danger {{
              color: var(--danger);
              border-color: var(--danger-soft);
            }}
            .task-actions .btn-danger:hover {{
              background: var(--danger-soft);
            }}
            .task-progress {{
              margin-top: 8px;
              height: 3px;
              background: var(--border-light);
              border-radius: 2px;
              overflow: hidden;
            }}
            .task-progress-bar {{
              height: 100%;
              background: var(--primary);
              border-radius: 2px;
              transition: width 0.5s ease;
            }}

            /* 展开详情 */
            /* Modal 弹窗 */
            .modal-overlay {{
              display: none;
              position: fixed; inset: 0; z-index: 1000;
              background: rgba(0,0,0,.45);
              justify-content: center; align-items: center;
            }}
            .modal-overlay.open {{
              display: flex;
            }}
            .modal-content {{
              background: #fff;
              border-radius: 12px;
              width: min(1100px, 94vw);
              max-height: 88vh;
              overflow: hidden;
              box-shadow: 0 20px 60px rgba(0,0,0,.2);
              padding: 0;
              position: relative;
              display: flex;
              flex-direction: column;
            }}
            .modal-header {{
              padding: 20px 28px 16px;
              border-bottom: 1px solid var(--border-light);
              flex-shrink: 0;
            }}
            .modal-close {{
              position: absolute; top: 16px; right: 20px;
              background: none; border: none; font-size: 22px;
              cursor: pointer; color: var(--text-secondary);
              line-height: 1; padding: 4px; z-index: 1;
            }}
            .modal-close:hover {{ color: var(--text); }}
            .modal-title {{
              font-size: 18px; font-weight: 700;
              padding-right: 36px;
              line-height: 1.4;
            }}
            .modal-columns {{
              display: grid;
              grid-template-columns: 360px 1fr;
              flex: 1;
              overflow: hidden;
            }}
            .modal-left {{
              padding: 20px 24px;
              overflow-y: auto;
              border-right: 1px solid var(--border-light);
            }}
            .modal-right {{
              padding: 20px 24px;
              overflow-y: auto;
            }}
            @media (max-width: 768px) {{
              .modal-columns {{
                grid-template-columns: 1fr;
              }}
              .modal-left {{
                border-right: none;
                border-bottom: 1px solid var(--border-light);
                max-height: 40vh;
              }}
            }}
            .detail-section {{
              margin-bottom: 18px;
            }}
            .detail-section h4 {{
              font-size: 13px;
              font-weight: 600;
              color: var(--text-secondary);
              text-transform: uppercase;
              letter-spacing: 0.5px;
              margin-bottom: 8px;
            }}
            .detail-preview {{
              background: var(--bg-input);
              border: 1px solid var(--border-light);
              border-radius: var(--radius-sm);
              padding: 20px;
              font-size: 14px;
              line-height: 1.8;
            }}
            .detail-preview img {{
              max-width: 100%;
              border-radius: var(--radius-sm);
            }}
            .detail-meta {{
              display: grid;
              grid-template-columns: auto 1fr;
              gap: 6px 16px;
              font-size: 13px;
            }}
            .detail-meta dt {{
              color: var(--text-secondary);
              font-weight: 500;
            }}
            .detail-meta dd {{
              color: var(--text);
            }}
            .detail-actions {{
              display: flex;
              gap: 10px;
              margin-top: 20px;
              padding-top: 16px;
              border-top: 1px solid var(--border-light);
            }}
            .detail-actions button {{
              padding: 10px 24px;
              border: none;
              border-radius: var(--radius-sm);
              font-size: 14px;
              font-weight: 600;
              cursor: pointer;
              transition: all var(--transition);
            }}
            .detail-actions .btn-confirm {{
              background: var(--success);
              color: #fff;
            }}
            .detail-actions .btn-confirm:hover {{
              background: #059669;
            }}
            .detail-actions .btn-push {{
              background: var(--primary);
              color: #fff;
            }}
            .detail-actions .btn-push:hover {{
              background: var(--primary-hover);
            }}
            .detail-actions .btn-retry {{
              background: var(--warning-soft);
              color: #92400E;
              border: 1px solid rgba(245,158,11,.2);
            }}
            .detail-actions .btn-retry:hover {{
              background: var(--warning);
              color: #fff;
            }}
            .detail-actions .btn-delete {{
              background: transparent;
              color: var(--danger);
              border: 1px solid var(--danger-soft);
            }}
            .detail-actions .btn-delete:hover {{
              background: var(--danger-soft);
            }}
            .detail-actions button:disabled {{
              opacity: 0.5;
              cursor: not-allowed;
            }}
            .badge {{
              display: inline-block; padding: 2px 8px; border-radius: 10px;
              font-size: 11px; font-weight: 600; line-height: 1.4;
            }}
            .badge.ok {{ background: #d4edda; color: #155724; }}
            .badge.warn {{ background: #fff3cd; color: #856404; }}
            .badge.error {{ background: #f8d7da; color: #721c24; }}

            /* 底部高级入口 */
            .advanced-link {{
              text-align: center;
              margin-top: 32px;
              padding-top: 20px;
              border-top: 1px solid var(--border-light);
            }}
            .advanced-link a {{
              font-size: 13px;
              color: var(--text-secondary);
              text-decoration: none;
              transition: color var(--transition);
            }}
            .advanced-link a:hover {{
              color: var(--primary);
            }}

            /* 加载动画 */
            @keyframes spin {{
              to {{ transform: rotate(360deg); }}
            }}
            .spinner {{
              display: inline-block;
              width: 14px; height: 14px;
              border: 2px solid var(--border);
              border-top-color: var(--primary);
              border-radius: 50%;
              animation: spin 0.6s linear infinite;
              vertical-align: middle;
              margin-right: 6px;
            }}
          </style>
        </head>
        <body class="admin-app">
          <script>__ADMIN_SHARED_SCRIPT_HELPERS__</script>

          <main class="admin-main">
            <div class="flow-container">
              <!-- 输入区 -->
              <section class="input-section">
                <div class="input-bar">
                  <input
                    id="url-input"
                    type="url"
                    placeholder="粘贴微信文章链接..."
                    autocomplete="off"
                  />
                  <button id="submit-btn">开始</button>
                </div>
                <div class="input-error" id="input-error"></div>
              </section>

              <!-- 计数条 -->
              <div class="count-bar" id="count-bar">
                <span><span class="dot blue"></span> 处理中 <span class="count" id="cnt-processing">0</span></span>
                <span><span class="dot orange"></span> 待确认 <span class="count" id="cnt-pending">0</span></span>
                <span><span class="dot red"></span> 失败 <span class="count" id="cnt-failed">0</span></span>
                <span><span class="dot green"></span> 已推送 <span class="count" id="cnt-done">0</span></span>
              </div>

              <!-- 任务列表 -->
              <div class="task-list" id="task-list">
                <div class="task-empty">
                  <div class="icon">📋</div>
                  粘贴一个微信文章链接开始
                </div>
              </div>

            </div>

              <div class="advanced-link">
                <a href="/admin/pipeline">🔧 流程配置</a>
                &nbsp;&nbsp;·&nbsp;&nbsp;
                <a href="/admin/settings">⚙ 设置</a>
              </div>
          </main>

          <!-- Modal 弹窗 -->
          <div class="modal-overlay" id="modal-overlay">
            <div class="modal-content">
              <button class="modal-close" id="modal-close">&times;</button>
              <div class="modal-header">
                <div class="modal-title" id="modal-title">加载中...</div>
              </div>
              <div class="modal-columns">
                <div class="modal-left" id="modal-left">加载中...</div>
                <div class="modal-right" id="modal-right"></div>
              </div>
            </div>
          </div>

          <script>
            const {{ escapeHtml }} = AdminUiShared;
            // 状态映射
            const PROCESSING = new Set(["queued", "building_brief", "generating", "reviewing"]);
            const PENDING = new Set(["needs_manual_review", "needs_regenerate", "review_passed", "needs_manual_source"]);
            const DONE = new Set(["draft_saved"]);

            const statusCategory = (s) => {{
              if (PROCESSING.has(s)) return "processing";
              if (PENDING.has(s)) return "pending";
              if (DONE.has(s)) return "done";
              if (String(s || "").endsWith("_failed")) return "failed";
              return "processing";
            }};

            const statusLabel = (s) => {{
              const cat = statusCategory(s);
              if (cat === "processing") return "处理中";
              if (cat === "pending") {{
                if (s === "review_passed") return "待推送";
                if (s === "needs_regenerate") return "待重写";
                return "待确认";
              }}
              if (cat === "done") return "已推送 ✓";
              if (cat === "failed") return "失败";
              return s;
            }};

            // 进度估算
            const statusProgress = (s) => {{
              const map = {{
                "queued": 10,
                "building_brief": 30,
                "generating": 55,
                "reviewing": 80,
                "needs_manual_review": 90,
                "needs_regenerate": 70,
                "review_passed": 95,
                "draft_saved": 100,
              }};
              return map[s] || 50;
            }};

            // DOM 元素
            const urlInput = document.getElementById("url-input");
            const submitBtn = document.getElementById("submit-btn");
            const inputError = document.getElementById("input-error");
            const taskList = document.getElementById("task-list");
            const cntProcessing = document.getElementById("cnt-processing");
            const cntPending = document.getElementById("cnt-pending");
            const cntFailed = document.getElementById("cnt-failed");
            const cntDone = document.getElementById("cnt-done");

            let allTasks = [];

            // DOM
            const modalOverlay = document.getElementById("modal-overlay");
            const modalTitle = document.getElementById("modal-title");
            const modalLeft = document.getElementById("modal-left");
            const modalRight = document.getElementById("modal-right");
            const modalClose = document.getElementById("modal-close");

            // Modal 控制
            const openModal = (title) => {{
              modalTitle.textContent = title || "任务详情";
              modalLeft.innerHTML = '<div style="color:var(--text-secondary);padding:8px 0">加载中...</div>';
              modalRight.innerHTML = '';
              modalOverlay.classList.add("open");
              document.body.style.overflow = "hidden";
            }};
            const closeModal = () => {{
              modalOverlay.classList.remove("open");
              document.body.style.overflow = "";
            }};
            modalClose.addEventListener("click", closeModal);
            modalOverlay.addEventListener("click", (e) => {{
              if (e.target === modalOverlay) closeModal();
            }});
            document.addEventListener("keydown", (e) => {{
              if (e.key === "Escape") closeModal();
            }});

            // API 请求
            const api = async (method, path, body) => {{
              const opts = {{
                method,
                headers: {{ "Content-Type": "application/json" }},
                credentials: "same-origin",
              }};
              if (body) opts.body = JSON.stringify(body);
              const res = await fetch(path, opts);
              if (!res.ok) {{
                const err = await res.json().catch(() => ({{ detail: res.statusText }}));
                throw new Error(err.detail || res.statusText);
              }}
              return res.json();
            }};

            // 显示错误
            const showError = (msg) => {{
              inputError.textContent = msg;
              inputError.style.display = "block";
              setTimeout(() => {{ inputError.style.display = "none"; }}, 5000);
            }};

            // 提交链接
            const submitUrl = async () => {{
              const url = urlInput.value.trim();
              if (!url) return;
              submitBtn.disabled = true;
              submitBtn.textContent = "提交中...";
              inputError.style.display = "none";
              try {{
                await api("POST", "/admin/api/ingest", {{ url }});
                urlInput.value = "";
                await refreshTasks();
              }} catch (e) {{
                showError(e.message || "提交失败");
              }} finally {{
                submitBtn.disabled = false;
                submitBtn.textContent = "开始";
              }}
            }};

            submitBtn.addEventListener("click", submitUrl);
            urlInput.addEventListener("keydown", (e) => {{
              if (e.key === "Enter") submitUrl();
            }});

            // 刷新任务列表
            const refreshTasks = async () => {{
              try {{
                const data = await api("GET", "/admin/api/home-snapshot?limit=30");
                allTasks = data.tasks || [];
                renderTasks();
              }} catch (e) {{
                console.error("刷新失败:", e);
              }}
            }};

            // 渲染任务列表
            const renderTasks = () => {{
              // 计数
              let pCnt = 0, nCnt = 0, fCnt = 0, dCnt = 0;
              allTasks.forEach((t) => {{
                const cat = statusCategory(t.status);
                if (cat === "processing") pCnt++;
                else if (cat === "pending") nCnt++;
                else if (cat === "failed") fCnt++;
                else if (cat === "done") dCnt++;
              }});
              cntProcessing.textContent = pCnt;
              cntPending.textContent = nCnt;
              cntFailed.textContent = fCnt;
              cntDone.textContent = dCnt;

              if (!allTasks.length) {{
                taskList.innerHTML = `
                  <div class="task-empty">
                    <div class="icon">\U0001F4CB</div>
                    粘贴一个微信文章链接开始
                  </div>`;
                return;
              }}

              // 排序：待确认 → 处理中 → 失败 → 已推送
              const order = {{ pending: 0, processing: 1, failed: 2, done: 3 }};
              const sorted = [...allTasks].sort((a, b) => {{
                const oa = order[statusCategory(a.status)] ?? 1;
                const ob = order[statusCategory(b.status)] ?? 1;
                if (oa !== ob) return oa - ob;
                return new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at);
              }});

              taskList.innerHTML = sorted.map((t) => {{
                const cat = statusCategory(t.status);
                const label = statusLabel(t.status);
                const progress = statusProgress(t.status);
                const title = t.title || t.source_url || t.task_id.slice(0, 12);
                const cardClass = `task-card ${{cat === "done" ? "done-card" : ""}}`;

                // 进度条（仅处理中）
                let progressBar = "";
                if (cat === "processing") {{
                  progressBar = `<div class="task-progress"><div class="task-progress-bar" style="width:${{progress}}%"></div></div>`;
                }}

                return `
                  <div class="${{cardClass}}" data-task-id="${{t.task_id}}" style="cursor:pointer;">
                    <div class="task-card-header">
                      <div class="task-card-info">
                        <div class="task-status-dot ${{cat}}"></div>
                        <div class="task-title">${{escapeHtml(title)}}</div>
                      </div>
                      <span class="task-status-label ${{cat}}">${{label}}</span>
                    </div>
                    ${{progressBar}}
                  </div>`;
              }}).join("");
            }};

            // 格式化评分（兼容 0-1 和 0-100 两种格式）
            const fmtScore = (v) => {{
              if (v == null) return null;
              const n = v <= 1 ? v * 100 : v;
              return n.toFixed(0) + "%";
            }};

            // 加载任务详情到 Modal
            const loadTaskDetail = async (taskId) => {{
              try {{
                const data = await api("GET", `/admin/api/home-snapshot?limit=1&selected_task_id=${{taskId}}`);
                const ws = data.workspace;
                if (!ws) {{
                  modalLeft.innerHTML = '<div style="color:var(--text-secondary)">无详情数据</div>';
                  modalRight.innerHTML = '';
                  return;
                }}

                const cat = statusCategory(ws.status);
                const gens = ws.generations || [];
                const gen = gens[0];
                const review = gen?.review;
                const srcArt = ws.source_article;

                // 标题
                modalTitle.textContent = ws.title || srcArt?.title || ws.source_url || "任务详情";

                // 计算耗时
                const elapsed = (() => {{
                  if (!ws.created_at) return null;
                  const ms = new Date(ws.updated_at || Date.now()) - new Date(ws.created_at);
                  const mins = Math.floor(ms / 60000);
                  if (mins < 1) return "不到 1 分钟";
                  if (mins < 60) return `${{mins}} 分钟`;
                  const hrs = Math.floor(mins / 60);
                  return `${{hrs}} 小时 ${{mins % 60}} 分`;
                }})();

                // 元信息
                const meta = [];
                if (srcArt?.title && srcArt.title !== ws.title) meta.push(["原文标题", escapeHtml(srcArt.title)]);
                if (ws.source_url) meta.push(["来源", `<a href="${{escapeHtml(ws.source_url)}}" target="_blank" style="color:var(--primary);word-break:break-all;">${{escapeHtml(ws.source_url.substring(0, 80))}}</a>`]);
                meta.push(["状态", `<span class="badge ${{cat === "done" ? "ok" : cat === "failed" ? "error" : "warn"}}">${{statusLabel(ws.status)}}</span>`]);
                if (gen) meta.push(["版本", `第 ${{gen.version_no}} 版`]);
                if (elapsed) meta.push(["耗时", elapsed]);
                if (ws.created_at) meta.push(["创建", escapeHtml(new Date(ws.created_at).toLocaleString("zh-CN"))]);
                if (ws.error) meta.push(["错误", `<span style="color:var(--danger)">${{escapeHtml(ws.error)}}</span>`]);

                let metaHtml = `
                  <div class="detail-section">
                    <h4>基本信息</h4>
                    <dl class="detail-meta">
                      ${{meta.map(([k, v]) => `<dt>${{k}}</dt><dd>${{v}}</dd>`).join("")}}
                    </dl>
                  </div>`;

                // AI 审核意见
                let reviewHtml = "";
                if (review) {{
                  const verdict = review.final_decision || "—";
                  const verdictClass = verdict === "pass" ? "ok" : (verdict === "fail" ? "error" : "warn");
                  const verdictLabel = verdict === "pass" ? "通过" : (verdict === "fail" ? "未通过" : verdict);
                  const items = [];
                  if (review.similarity_score != null) items.push(`相似度 ${{fmtScore(review.similarity_score)}}`);
                  if (review.readability_score != null) items.push(`可读性 ${{fmtScore(review.readability_score)}}`);
                  if (review.ai_trace_score != null) items.push(`AI 痕迹 ${{fmtScore(review.ai_trace_score)}}`);
                  if (review.factual_risk_score != null) items.push(`事实风险 ${{fmtScore(review.factual_risk_score)}}`);
                  const summaryText = review.voice_summary || (review.suggestions ? JSON.stringify(review.suggestions).slice(0, 200) : "");
                  reviewHtml = `
                    <div class="detail-section">
                      <h4>AI 审核 <span class="badge ${{verdictClass}}" style="margin-left:6px;vertical-align:middle;">${{verdictLabel}}</span></h4>
                      ${{items.length ? `<div style="font-size:13px;color:var(--text-secondary);margin-bottom:6px;">${{items.join(" · ")}}</div>` : ""}}
                      ${{summaryText ? `<div style="font-size:13px;color:var(--text-secondary);line-height:1.6;">${{escapeHtml(summaryText.slice(0, 300))}}</div>` : ""}}
                    </div>`;
                }}

                // 文章预览
                let previewHtml = "";
                if (gen?.html_content) {{
                  previewHtml = `
                    <div class="detail-section">
                      <h4>文章预览</h4>
                      <div class="detail-preview">${{gen.html_content}}</div>
                    </div>`;
                }}

                // 微信草稿链接
                let draftHtml = "";
                if (ws.wechat_draft_url) {{
                  draftHtml = `
                    <div class="detail-section">
                      <h4>微信草稿</h4>
                      <a href="${{escapeHtml(ws.wechat_draft_url)}}" target="_blank" style="color:var(--primary);font-size:13px;">${{ws.wechat_draft_url_hint || "查看草稿 →"}}</a>
                    </div>`;
                }}

                // 操作按钮
                let actionsHtml = "";
                if (cat === "pending") {{
                  if (ws.status === "review_passed") {{
                    actionsHtml = `<div class="detail-actions">
                      <button class="btn-push" data-action="push" data-id="${{ws.task_id}}">推送到草稿箱</button>
                      <button class="btn-delete" data-action="delete" data-id="${{ws.task_id}}">删除</button>
                    </div>`;
                  }} else {{
                    actionsHtml = `<div class="detail-actions">
                      <button class="btn-confirm" data-action="approve" data-id="${{ws.task_id}}">确认通过</button>
                      <button class="btn-retry" data-action="retry" data-id="${{ws.task_id}}">重新生成</button>
                      <button class="btn-delete" data-action="delete" data-id="${{ws.task_id}}">删除</button>
                    </div>`;
                  }}
                }} else if (cat === "failed") {{
                  actionsHtml = `<div class="detail-actions">
                    <button class="btn-retry" data-action="retry" data-id="${{ws.task_id}}">重试</button>
                    <button class="btn-delete" data-action="delete" data-id="${{ws.task_id}}">删除</button>
                  </div>`;
                }} else if (cat === "done") {{
                  actionsHtml = `<div class="detail-actions">
                    <button class="btn-delete" data-action="delete" data-id="${{ws.task_id}}">删除</button>
                  </div>`;
                }}

                modalLeft.innerHTML = metaHtml + reviewHtml + draftHtml + actionsHtml;
                modalRight.innerHTML = previewHtml || '<div style="color:var(--text-secondary);padding:20px;text-align:center">暂无预览内容</div>';

              }} catch (e) {{
                modalLeft.innerHTML = `<div style="color:var(--danger)">${{escapeHtml(e.message)}}</div>`;
                modalRight.innerHTML = '';
              }}
            }};

            // 处理操作按钮（卡片和弹窗中通用）
            const handleAction = async (actionBtn) => {{
              const action = actionBtn.dataset.action;
              const id = actionBtn.dataset.id;
              actionBtn.disabled = true;
              const origText = actionBtn.textContent;
              actionBtn.textContent = "处理中...";
              try {{
                if (action === "approve") {{
                  await api("POST", `/admin/api/tasks/${{id}}/approve`, {{ device_id: "admin-web" }});
                }} else if (action === "push") {{
                  await api("POST", `/admin/api/tasks/${{id}}/push`, {{ device_id: "admin-web" }});
                }} else if (action === "retry") {{
                  await api("POST", `/admin/api/tasks/${{id}}/retry`);
                }} else if (action === "delete") {{
                  if (!confirm("确定要删除这个任务吗？")) {{
                    actionBtn.disabled = false;
                    actionBtn.textContent = origText;
                    return;
                  }}
                  await api("DELETE", `/admin/api/tasks/${{id}}`);
                }}
                closeModal();
                await refreshTasks();
              }} catch (err) {{
                showError(err.message || "操作失败");
                actionBtn.disabled = false;
                actionBtn.textContent = origText;
              }}
            }};

            // 事件代理 - 任务列表
            taskList.addEventListener("click", (e) => {{
              const actionBtn = e.target.closest("[data-action]");
              if (actionBtn) {{ e.stopPropagation(); handleAction(actionBtn); return; }}

              const card = e.target.closest(".task-card");
              if (!card) return;
              const id = card.dataset.taskId;
              const t = allTasks.find(x => x.task_id === id);
              openModal(t?.title || t?.source_url || "任务详情");
              loadTaskDetail(id);
            }});

            // 事件代理 - Modal 内操作按钮
            modalLeft.addEventListener("click", (e) => {{
              const actionBtn = e.target.closest("[data-action]");
              if (actionBtn) handleAction(actionBtn);
            }});

            // 自动刷新
            let refreshTimer = null;
            const startAutoRefresh = () => {{
              refreshTimer = setInterval(refreshTasks, 8000);
            }};
            const stopAutoRefresh = () => {{
              if (refreshTimer) clearInterval(refreshTimer);
            }};

            // 页面可见性控制
            document.addEventListener("visibilitychange", () => {{
              if (document.hidden) {{
                stopAutoRefresh();
              }} else {{
                refreshTasks();
                startAutoRefresh();
              }}
            }});

            // 初始化
            refreshTasks();
            startAutoRefresh();
          </script>
        </body>
        </html>
        """
    )
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
    html = dedent(
        """\
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>高级监控台</title>
          <style>
            :root {
              --bg: var(--bg-body);
              --panel: var(--bg-card);
              --line: var(--border);
              --muted: var(--text-secondary);
              --accent: var(--primary);
              --accent-dark: var(--primary-hover);
              --warn: var(--warning);
              --ok: var(--success);
              --shadow: var(--shadow-card);
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
            .hero-warning {
              display: grid;
              gap: 10px;
              padding: 14px 16px;
              border-radius: 20px;
              border: 1px solid rgba(158, 64, 50, 0.16);
              background: linear-gradient(135deg, rgba(158, 64, 50, 0.09), rgba(255, 249, 242, 0.95));
            }
            .warning-kicker {
              display: inline-flex;
              width: fit-content;
              padding: 5px 10px;
              border-radius: 999px;
              background: rgba(158, 64, 50, 0.12);
              color: var(--danger);
              font-size: 12px;
              letter-spacing: 0.08em;
            }
            .hero-warning strong {
              font-size: 17px;
              line-height: 1.5;
            }
            .warning-list {
              display: grid;
              gap: 6px;
              margin: 0;
              padding: 0;
              list-style: none;
              color: var(--muted);
              font-size: 14px;
              line-height: 1.75;
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
            .alerts-grid[aria-busy="true"],
            .trend-grid[aria-busy="true"],
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
            .panel-row {
              display: flex;
              align-items: flex-start;
              justify-content: space-between;
              gap: 14px;
              margin-bottom: 14px;
            }
            .panel-row h2 {
              margin: 0 0 8px;
            }
            .panel-row .panel-intro {
              margin: 0;
            }
            .panel-tools {
              display: flex;
              flex-wrap: wrap;
              justify-content: flex-end;
              align-items: center;
              gap: 8px;
            }
            .mini-note {
              color: var(--muted);
              font-size: 12px;
              line-height: 1.6;
            }
            .alerts-grid {
              display: grid;
              gap: 12px;
            }
            .alert-card {
              display: grid;
              gap: 12px;
              padding: 16px;
              border-radius: 20px;
              border: 1px solid rgba(65, 48, 27, 0.12);
              background: linear-gradient(180deg, rgba(255, 252, 247, 0.98), rgba(247, 242, 233, 0.96));
              box-shadow: 0 14px 30px rgba(58, 40, 18, 0.06);
            }
            .alert-card.warn {
              border-color: rgba(176, 122, 24, 0.28);
              background: linear-gradient(160deg, rgba(255, 248, 235, 0.98), rgba(250, 244, 232, 0.94));
            }
            .alert-card.critical {
              border-color: rgba(158, 64, 50, 0.3);
              background: linear-gradient(160deg, rgba(255, 244, 241, 0.98), rgba(252, 242, 238, 0.94));
            }
            .alert-head {
              display: flex;
              align-items: flex-start;
              justify-content: space-between;
              gap: 12px;
            }
            .alert-head h3 {
              margin: 6px 0 0;
              font-size: 17px;
              line-height: 1.45;
            }
            .alert-level {
              display: inline-flex;
              align-items: center;
              border-radius: 999px;
              padding: 4px 10px;
              font-size: 12px;
              letter-spacing: 0.06em;
              background: rgba(37, 93, 82, 0.12);
              color: var(--accent-dark);
            }
            .alert-level.warn {
              background: rgba(176, 122, 24, 0.16);
              color: #8a5c12;
            }
            .alert-level.critical {
              background: rgba(158, 64, 50, 0.14);
              color: var(--danger);
            }
            .alert-body {
              margin: 0;
              font-size: 14px;
              line-height: 1.75;
            }
            .alert-meta {
              margin: 0;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }
            .alert-actions {
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
            }
            .alert-actions button,
            .alert-actions a {
              width: auto;
              min-width: 120px;
            }
            .alert-actions a {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              padding: 12px 16px;
              border-radius: 14px;
              border: 1px solid rgba(37, 93, 82, 0.18);
              background: rgba(255, 253, 249, 0.9);
              color: var(--accent-dark);
              text-decoration: none;
              transition: transform 0.12s ease, border-color 0.12s ease;
            }
            .alert-actions a:hover {
              border-color: rgba(23, 63, 56, 0.3);
              transform: translateY(-1px);
            }
            .alert-muted-note {
              padding: 14px 16px;
              border-radius: 18px;
              border: 1px dashed rgba(65, 48, 27, 0.18);
              background: rgba(255, 253, 249, 0.74);
              color: var(--muted);
              font-size: 13px;
              line-height: 1.75;
            }
            .trend-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
              gap: 12px;
            }
            .trend-card {
              display: grid;
              gap: 12px;
              padding: 16px;
              border-radius: 20px;
              border: 1px solid rgba(65, 48, 27, 0.12);
              background: linear-gradient(180deg, rgba(255, 252, 247, 0.98), rgba(247, 242, 233, 0.96));
              box-shadow: 0 14px 30px rgba(58, 40, 18, 0.05);
            }
            .trend-top {
              display: flex;
              align-items: baseline;
              justify-content: space-between;
              gap: 10px;
            }
            .trend-top strong {
              font-size: 13px;
              color: var(--muted);
              font-weight: 600;
            }
            .trend-top span {
              font-size: 13px;
              color: var(--text);
            }
            .trend-bars {
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: 10px;
              align-items: end;
              min-height: 110px;
            }
            .trend-column {
              display: grid;
              justify-items: center;
              gap: 8px;
            }
            .trend-rail {
              display: flex;
              align-items: flex-end;
              justify-content: center;
              width: 100%;
              max-width: 56px;
              height: 88px;
              padding: 4px;
              border-radius: 999px;
              background: rgba(36, 29, 20, 0.08);
            }
            .trend-bar {
              display: block;
              width: 100%;
              border-radius: 999px;
              min-height: 6px;
              transition: height 180ms ease;
            }
            .trend-bar.submitted {
              background: linear-gradient(180deg, rgba(37, 93, 82, 0.62), rgba(37, 93, 82, 0.96));
            }
            .trend-bar.failed {
              background: linear-gradient(180deg, rgba(158, 64, 50, 0.46), rgba(158, 64, 50, 0.92));
            }
            .trend-column label {
              margin: 0;
              font-size: 12px;
              color: var(--muted);
            }
            .trend-rates {
              display: grid;
              gap: 8px;
            }
            .trend-rate {
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 8px;
              padding-top: 8px;
              border-top: 1px solid rgba(65, 48, 27, 0.08);
            }
            .trend-rate strong {
              font-size: 12px;
              color: var(--muted);
              font-weight: 500;
            }
            .trend-rate span {
              font-size: 18px;
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
              .trend-grid,
              .detail-grid,
              .task-grid {
                grid-template-columns: 1fr;
              }
              .panel-row,
              .alert-head {
                flex-direction: column;
              }
              .overview-card.highlight {
                grid-column: span 1;
              }
            }
            __ADMIN_SHARED_STYLES__
          </style>
        </head>
        <body>
          <a class="skip-link" href="#monitor-region">跳到监控主区</a>
          <main class="admin-main">
            __ADMIN_SECTION_NAV__
            __ADMIN_HERO__
            __ADMIN_OVERVIEW__

            <section class="layout" id="monitor-region">
              <div class="stack">
                <section class="panel">
                  <h2>控制</h2>
                  <div class="grid">
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
                  <h2>筛选</h2>
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
                  <h2>响应</h2>
                  <pre id="output">等待刷新...</pre>
                </section>
              </div>

              <div class="stack">
                <section class="panel">
                  <h2>快照</h2>
                  <div class="metrics" id="metrics" aria-busy="false">
                    <div class="metric-card"><strong>当前筛选</strong><span>0</span></div>
                  </div>
                </section>

                <section class="panel" id="alerts-panel">
                  <div class="panel-row">
                    <div>
                      <h2>告警</h2>
                    </div>
                    <div class="panel-tools">
                      <span class="mini-note" id="alerts-summary">等待监控快照</span>
                      <button id="clear-alert-silence" class="secondary" type="button">恢复全部静默</button>
                    </div>
                  </div>
                  <div class="alerts-grid" id="alerts" aria-busy="false">
                    <div class="hint">等待快照</div>
                  </div>
                </section>

                <section class="panel" id="trends-panel">
                  <h2>24h 趋势</h2>
                  <div class="trend-grid" id="trends" aria-busy="false">
                    <div class="hint">等待快照</div>
                  </div>
                </section>

                <section class="panel" id="operations-panel">
                  <h2>队列 / Worker</h2>
                  <div class="ops-grid" id="operations" aria-busy="false">
                    <div class="hint">等待快照</div>
                  </div>
                </section>

                <section class="panel" id="board-panel">
                  <h2>看板</h2>
                  <div class="board" id="board" aria-busy="false">
                    <div class="hint">点击“立即刷新”</div>
                  </div>
                </section>

                <section class="panel">
                  <h2>详情</h2>
                  <div id="workspace" class="workspace" aria-busy="false">
                    <div class="hint">← 从看板选择任务</div>
                  </div>
                </section>
              </div>
            </section>
          </main>

          <script>
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
            const alertsEl = document.getElementById("alerts");
            const trendsEl = document.getElementById("trends");
            const operationsEl = document.getElementById("operations");
            const workspaceEl = document.getElementById("workspace");
            const statusEl = document.getElementById("status");
            const flashMessageEl = document.getElementById("flash-message");
            const heroFocusEl = document.getElementById("hero-focus");
            const outputEl = document.getElementById("output");
            const liveHintEl = document.getElementById("live-hint");
            const alertsSummaryEl = document.getElementById("alerts-summary");
            const clearAlertSilenceEl = document.getElementById("clear-alert-silence");
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
            const SESSION_EXPIRED_MESSAGE = "后台会话已失效，请刷新页面重新进入后台。";
            const ALERT_SILENCE_STORAGE_KEY = "phase7_console_silenced_alerts";
            const ALERT_SILENCE_HOURS = 6;
            let silencedAlerts = {};

            const escapeHtml = (value) => {
              return String(value ?? "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#39;");
            };
            const readSilencedAlerts = () => {
              try {
                const raw = localStorage.getItem(ALERT_SILENCE_STORAGE_KEY);
                if (!raw) return {};
                const parsed = JSON.parse(raw);
                return parsed && typeof parsed === "object" ? parsed : {};
              } catch (_error) {
                return {};
              }
            };
            const persistSilencedAlerts = () => {
              const entries = Object.entries(silencedAlerts);
              if (!entries.length) {
                localStorage.removeItem(ALERT_SILENCE_STORAGE_KEY);
                return;
              }
              localStorage.setItem(ALERT_SILENCE_STORAGE_KEY, JSON.stringify(Object.fromEntries(entries)));
            };
            const cleanupSilencedAlerts = () => {
              const now = Date.now();
              let changed = false;
              Object.entries(silencedAlerts).forEach(([key, expiresAt]) => {
                const timestamp = new Date(expiresAt).getTime();
                if (!Number.isFinite(timestamp) || timestamp <= now) {
                  delete silencedAlerts[key];
                  changed = true;
                }
              });
              if (changed) {
                persistSilencedAlerts();
              }
            };
            const alertDedupeKey = (alert) => alert?.dedupe_key || alert?.key || "";
            const isAlertSilenced = (alert) => {
              cleanupSilencedAlerts();
              const key = alertDedupeKey(alert);
              if (!key) return false;
              const expiresAt = silencedAlerts[key];
              return Boolean(expiresAt && new Date(expiresAt).getTime() > Date.now());
            };
            const silenceAlert = (key, hours = ALERT_SILENCE_HOURS) => {
              if (!key) return;
              silencedAlerts[key] = new Date(Date.now() + hours * 60 * 60 * 1000).toISOString();
              persistSilencedAlerts();
            };
            const resetSilencedAlerts = () => {
              silencedAlerts = {};
              persistSilencedAlerts();
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
            const formatRate = (value) => value === null || value === undefined ? "暂无" : `${value}%`;
            const reviewAiTraceScore = (review) => (review && review.ai_trace_score !== null && review.ai_trace_score !== undefined)
              ? Number(review.ai_trace_score)
              : null;
            const reviewAiTraceLabel = (review) => {
              const score = reviewAiTraceScore(review);
              return score === null ? "暂无" : `${Math.round(score)}分`;
            };
            const reviewAiTracePatternCount = (review) => Array.isArray(review?.ai_trace_patterns)
              ? review.ai_trace_patterns.length
              : 0;
            const reviewHumanizeLabel = (review) => review?.humanize_applied
              ? `已定点润色 ${Array.isArray(review?.humanize_block_ids) ? review.humanize_block_ids.length : 0} 段`
              : "未触发";
            const reviewVoiceSummary = (review) => truncate(review?.voice_summary || "", 120) || "暂无";

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
              alertsEl.setAttribute("aria-busy", value);
              trendsEl.setAttribute("aria-busy", value);
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
              let focus = "无待处理任务";
              let note = "";
              if (selectedTaskId) {
                focus = `任务 ${selectedTaskId.slice(0, 8)}`;
                note = "";
              } else if (summary) {
                if (summary.filtered_manual > 0) {
                  focus = `${summary.filtered_manual} 个待处理`;
                  note = "";
                } else if (summary.filtered_failed > 0) {
                  focus = `${summary.filtered_failed} 个异常`;
                  note = "";
                } else if (summary.filtered_total === 0) {
                  focus = "当前筛选无结果";
                  note = "";
                } else {
                  focus = "无异常";
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
              const response = await fetch(apiUrl(path), {
                credentials: "same-origin",
              });
              const text = await response.text();
              let body = null;
              try {
                body = text ? JSON.parse(text) : null;
              } catch (_error) {
                body = text;
              }
              if (!response.ok) {
                if (response.status === 401) {
                  throw new Error(SESSION_EXPIRED_MESSAGE);
                }
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
                boardEl.innerHTML = '<div class="hint">当前筛选无结果</div>';
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
              const latestAiTrace = reviewAiTraceLabel(latestReview);
              const latestHumanize = reviewHumanizeLabel(latestReview);
              const latestPatternCount = reviewAiTracePatternCount(latestReview);
              const latestVoiceSummary = reviewVoiceSummary(latestReview);
              workspaceEl.innerHTML = `
                <div class="summary-grid">
                  <div class="summary-item"><strong>状态</strong><span>${escapeHtml(workspace.status)} · ${escapeHtml(workspace.progress)}%</span></div>
                  <div class="summary-item"><strong>标题</strong><span>${escapeHtml(workspace.title || "暂无")}</span></div>
                  <div class="summary-item"><strong>task_code</strong><span>${escapeHtml(workspace.task_code)}</span></div>
                  <div class="summary-item"><strong>已推草稿</strong><span>${escapeHtml(workspace.wechat_media_id || "暂无")}</span></div>
                  <div class="summary-item"><strong>AI 痕迹</strong><span>${escapeHtml(latestAiTrace)}</span></div>
                  <div class="summary-item"><strong>定点润色</strong><span>${escapeHtml(latestHumanize)} · ${escapeHtml(latestPatternCount)} 类模式</span></div>
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
                      <div><strong>AI 痕迹 / 模式数 / 定点润色</strong> ${escapeHtml(latestAiTrace)} / ${escapeHtml(latestPatternCount)} / ${escapeHtml(latestHumanize)}</div>
                      <div><strong>语气诊断</strong> ${escapeHtml(latestVoiceSummary)}</div>
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
                setStatus(`已刷新 · ${snapshot.tasks.length} 个任务`, "", "高级监控快照已刷新，可以继续收窄筛选或点开任务详情。");
              }
              renderOverview(snapshot);
            };

            const refreshAll = async () => {
              saveDraft();
              setStatus("刷新中", "", "正在拉取最新高级监控快照。");
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
                  if ((error.message || String(error)) === SESSION_EXPIRED_MESSAGE) {
                    if (refreshTimer) {
                      clearInterval(refreshTimer);
                      refreshTimer = null;
                    }
                    setLiveHint("当前模式：后台会话失效");
                    setStatus("待重新进入", "warn", SESSION_EXPIRED_MESSAGE);
                    renderOutput(error.message || String(error));
                    return;
                  }
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

            [pollSecondsEl, limitEl, autoRefreshEl, statusFilterEl, sourceFilterEl, queryFilterEl, createdAfterEl, activeOnlyEl].forEach((element) => {
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
            refreshAll().catch((error) => {
              setStatus("失败", "danger", "首次加载监控快照失败，详见输出区域。");
              renderOutput(error.message || String(error));
            });
          </script>
        </body>
        </html>
        """
    )
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
    html = dedent(
        """\
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>流程配置</title>
          <link rel="preconnect" href="https://fonts.googleapis.com" crossorigin />
          <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
          <style>
            __ADMIN_SHARED_STYLES__

            :root {
              --pipe-font: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
              --phase-fetch: #3b82f6;
              --phase-fetch-bg: rgba(59,130,246,.08);
              --phase-fetch-border: rgba(59,130,246,.2);
              --phase-prepare: #10b981;
              --phase-prepare-bg: rgba(16,185,129,.08);
              --phase-prepare-border: rgba(16,185,129,.2);
              --phase-produce: #8b5cf6;
              --phase-produce-bg: rgba(139,92,246,.08);
              --phase-produce-border: rgba(139,92,246,.2);
              --pipe-surface: #ffffff;
              --pipe-surface-alt: #f8fafc;
              --pipe-border: #e2e8f0;
              --pipe-text: #1e293b;
              --pipe-text-dim: #64748b;
              --pipe-text-muted: #94a3b8;
              --pipe-shadow: 0 1px 3px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04);
              --pipe-shadow-lg: 0 10px 25px rgba(0,0,0,.08), 0 4px 10px rgba(0,0,0,.04);
              --pipe-radius: 12px;
            }

            .pipe-page {
              font-family: var(--pipe-font);
              max-width: 1000px;
              margin: 0 auto;
              padding: 40px 24px;
            }

            /* 顶部 */
            .pipe-hero {
              display: flex;
              align-items: flex-start;
              justify-content: space-between;
              margin-bottom: 36px;
              animation: fadeIn .4s ease;
            }
            .pipe-hero h1 {
              font-size: 24px;
              font-weight: 700;
              color: var(--pipe-text);
              margin: 0 0 6px;
              letter-spacing: -.02em;
            }
            .pipe-hero .desc {
              font-size: 14px;
              color: var(--pipe-text-dim);
              margin: 0;
            }
            .pipe-hero .back-link {
              font-size: 13px;
              color: var(--pipe-text-muted);
              text-decoration: none;
              padding: 8px 16px;
              border: 1px solid var(--pipe-border);
              border-radius: 8px;
              transition: all .15s;
              white-space: nowrap;
            }
            .pipe-hero .back-link:hover {
              color: var(--pipe-text);
              border-color: var(--pipe-text-dim);
              box-shadow: var(--pipe-shadow);
            }

            /* Phase 区块 */
            .phase-section {
              margin-bottom: 28px;
              animation: slideUp .4s ease both;
            }
            .phase-section:nth-child(1) { animation-delay: .05s; }
            .phase-section:nth-child(2) { animation-delay: .12s; }
            .phase-section:nth-child(3) { animation-delay: .19s; }

            .phase-header {
              display: flex;
              align-items: center;
              gap: 10px;
              margin-bottom: 14px;
              padding-left: 2px;
            }
            .phase-dot {
              width: 8px; height: 8px;
              border-radius: 50%;
              flex-shrink: 0;
            }
            .phase-title {
              font-size: 12px;
              font-weight: 600;
              text-transform: uppercase;
              letter-spacing: .08em;
            }
            .phase-line {
              flex: 1;
              height: 1px;
              background: var(--pipe-border);
              margin-left: 8px;
            }

            /* 节点容器 */
            .phase-steps {
              display: flex;
              align-items: center;
              gap: 0;
              flex-wrap: wrap;
            }

            /* 连接箭头 */
            .step-connector {
              display: flex;
              align-items: center;
              padding: 0 4px;
              flex-shrink: 0;
            }
            .step-connector svg {
              width: 32px;
              height: 16px;
            }

            /* 节点卡片 */
            .step-card {
              display: flex;
              align-items: center;
              gap: 10px;
              padding: 14px 20px;
              border-radius: var(--pipe-radius);
              background: var(--pipe-surface);
              border: 1.5px solid var(--pipe-border);
              cursor: pointer;
              transition: all .2s cubic-bezier(.4,0,.2,1);
              position: relative;
              box-shadow: var(--pipe-shadow);
              overflow: visible;
            }
            .step-card:hover {
              transform: translateY(-2px);
              box-shadow: var(--pipe-shadow-lg);
            }
            .step-card.active {
              box-shadow: var(--pipe-shadow-lg);
              transform: translateY(-2px);
            }
            .step-card .step-icon {
              font-size: 22px;
              line-height: 1;
              flex-shrink: 0;
            }
            .step-card .step-info {
              display: flex;
              flex-direction: column;
              gap: 2px;
            }
            .step-card .step-name {
              font-size: 14px;
              font-weight: 600;
              color: var(--pipe-text);
              white-space: nowrap;
            }
            .step-card .step-hint {
              font-size: 11px;
              color: var(--pipe-text-muted);
              white-space: nowrap;
            }

            /* Phase 颜色主题 */
            .step-card[data-phase="fetch"] { border-color: var(--phase-fetch-border); }
            .step-card[data-phase="fetch"]:hover,
            .step-card[data-phase="fetch"].active { border-color: var(--phase-fetch); background: var(--phase-fetch-bg); }
            .step-card[data-phase="prepare"] { border-color: var(--phase-prepare-border); }
            .step-card[data-phase="prepare"]:hover,
            .step-card[data-phase="prepare"].active { border-color: var(--phase-prepare); background: var(--phase-prepare-bg); }
            .step-card[data-phase="produce"] { border-color: var(--phase-produce-border); }
            .step-card[data-phase="produce"]:hover,
            .step-card[data-phase="produce"].active { border-color: var(--phase-produce); background: var(--phase-produce-bg); }

            /* 可配置徽标 */
            .step-badge {
              position: absolute;
              top: -8px;
              right: -8px;
              min-width: 20px; height: 20px;
              padding: 0 6px;
              background: linear-gradient(135deg, #6366f1, #8b5cf6);
              color: #fff;
              border-radius: 10px;
              font-size: 10px;
              font-weight: 700;
              line-height: 20px;
              text-align: center;
              box-shadow: 0 2px 6px rgba(99,102,241,.3);
            }
            .step-children-tag {
              position: absolute;
              bottom: -20px;
              left: 50%;
              transform: translateX(-50%);
              font-size: 10px;
              color: var(--pipe-text-muted);
              white-space: nowrap;
              background: var(--pipe-surface-alt);
              padding: 2px 8px;
              border-radius: 4px;
              border: 1px solid var(--pipe-border);
            }

            /* 配置面板 */
            .config-panel {
              margin-top: 20px;
              background: var(--pipe-surface);
              border: 1.5px solid var(--pipe-border);
              border-radius: var(--pipe-radius);
              overflow: hidden;
              box-shadow: var(--pipe-shadow-lg);
              animation: panelSlide .25s ease;
            }
            @keyframes panelSlide {
              from { opacity: 0; transform: translateY(-10px); }
              to { opacity: 1; transform: translateY(0); }
            }
            .config-header {
              display: flex;
              align-items: center;
              gap: 10px;
              padding: 18px 24px;
              border-bottom: 1px solid var(--pipe-border);
              background: var(--pipe-surface-alt);
            }
            .config-header .cfg-icon { font-size: 20px; }
            .config-header .cfg-title {
              font-size: 15px;
              font-weight: 600;
              color: var(--pipe-text);
            }
            .config-body { padding: 8px 0; }
            .config-row {
              display: flex;
              align-items: center;
              gap: 12px;
              padding: 12px 24px;
              transition: background .1s;
            }
            .config-row:hover { background: var(--pipe-surface-alt); }
            .config-label {
              flex: 1;
              font-size: 13px;
              font-weight: 500;
              color: var(--pipe-text);
            }
            .config-default {
              font-size: 11px;
              color: var(--pipe-text-muted);
              min-width: 76px;
              text-align: right;
            }
            .config-input {
              width: 76px;
              padding: 7px 10px;
              border: 1.5px solid var(--pipe-border);
              border-radius: 8px;
              background: var(--pipe-surface);
              color: var(--pipe-text);
              font-size: 13px;
              font-family: var(--pipe-font);
              text-align: right;
              transition: all .15s;
            }
            .config-input:focus {
              outline: none;
              border-color: #6366f1;
              box-shadow: 0 0 0 3px rgba(99,102,241,.12);
            }
            .config-btn {
              padding: 7px 16px;
              font-size: 12px;
              font-weight: 600;
              font-family: var(--pipe-font);
              border: none;
              border-radius: 8px;
              cursor: pointer;
              transition: all .15s;
            }
            .config-btn.save {
              background: linear-gradient(135deg, #6366f1, #8b5cf6);
              color: #fff;
              box-shadow: 0 2px 6px rgba(99,102,241,.25);
            }
            .config-btn.save:hover { box-shadow: 0 4px 12px rgba(99,102,241,.35); transform: translateY(-1px); }
            .config-btn.save:disabled { opacity: .5; cursor: not-allowed; transform: none; }
            .config-btn.reset {
              background: var(--pipe-surface);
              color: var(--pipe-text-dim);
              border: 1.5px solid var(--pipe-border);
            }
            .config-btn.reset:hover { background: var(--pipe-surface-alt); color: var(--pipe-text); }
            .config-saved {
              font-size: 12px;
              font-weight: 600;
              color: #10b981;
              opacity: 0;
              transition: opacity .2s;
            }
            .config-saved.show { opacity: 1; }

            /* 弹窗 */
            .modal-overlay {
              display: none;
              position: fixed;
              inset: 0;
              background: rgba(15,23,42,.5);
              backdrop-filter: blur(4px);
              z-index: 1000;
              justify-content: center;
              align-items: center;
            }
            .modal-overlay.open { display: flex; }
            .modal-box {
              background: var(--pipe-surface);
              border-radius: 16px;
              padding: 0;
              max-width: 520px;
              width: 90%;
              box-shadow: 0 25px 50px rgba(0,0,0,.15);
              animation: modalUp .25s cubic-bezier(.4,0,.2,1);
              overflow: hidden;
            }
            @keyframes modalUp {
              from { transform: translateY(20px) scale(.97); opacity: 0; }
              to { transform: translateY(0) scale(1); opacity: 1; }
            }
            .modal-header {
              display: flex;
              align-items: center;
              justify-content: space-between;
              padding: 20px 24px;
              border-bottom: 1px solid var(--pipe-border);
              background: var(--pipe-surface-alt);
            }
            .modal-header h3 {
              font-size: 16px;
              font-weight: 600;
              color: var(--pipe-text);
              margin: 0;
            }
            .modal-close {
              width: 32px; height: 32px;
              background: var(--pipe-surface);
              border: 1px solid var(--pipe-border);
              border-radius: 8px;
              font-size: 16px;
              color: var(--pipe-text-dim);
              cursor: pointer;
              display: flex;
              align-items: center;
              justify-content: center;
              transition: all .15s;
            }
            .modal-close:hover { color: var(--pipe-text); border-color: var(--pipe-text-dim); }
            .modal-body { padding: 20px 24px; }
            .sub-step {
              display: flex;
              align-items: center;
              gap: 12px;
              padding: 12px 16px;
              border-radius: 10px;
              background: var(--pipe-surface-alt);
              border: 1px solid var(--pipe-border);
              font-size: 13px;
              font-weight: 500;
              color: var(--pipe-text);
              animation: fadeIn .2s ease both;
            }
            .sub-step:nth-child(1) { animation-delay: .05s; }
            .sub-step:nth-child(3) { animation-delay: .1s; }
            .sub-step:nth-child(5) { animation-delay: .15s; }
            .sub-step .sub-icon { font-size: 18px; }
            .sub-arrow {
              display: flex;
              justify-content: center;
              padding: 4px 0;
              color: var(--pipe-text-muted);
              font-size: 13px;
            }

            .pipe-loading {
              text-align: center;
              padding: 80px 20px;
              color: var(--pipe-text-muted);
              font-size: 14px;
            }
            .pipe-loading .spinner {
              display: inline-block;
              width: 24px; height: 24px;
              border: 2.5px solid var(--pipe-border);
              border-top-color: #6366f1;
              border-radius: 50%;
              animation: spin .6s linear infinite;
              margin-bottom: 12px;
            }
            @keyframes spin { to { transform: rotate(360deg); } }

            @keyframes fadeIn { from { opacity:0 } to { opacity:1 } }
            @keyframes slideUp {
              from { opacity:0; transform: translateY(12px); }
              to { opacity:1; transform: translateY(0); }
            }

            @media (max-width: 640px) {
              .pipe-page { padding: 20px 12px; }
              .step-card { padding: 10px 14px; }
              .config-row { padding: 10px 16px; }
              .phase-steps { gap: 4px; }
            }
          </style>
        </head>
        <body class="admin-app">
          <div class="pipe-page">
            <div class="pipe-hero">
              <div>
                <h1>流程配置</h1>
                <p class="desc" id="pipeDesc">加载中…</p>
              </div>
              <a href="/admin" class="back-link">← 返回工作台</a>
            </div>
            <div id="pipeGraph">
              <div class="pipe-loading">
                <div class="spinner"></div>
                <div>加载流程定义…</div>
              </div>
            </div>
            <div id="configPanel"></div>
          </div>

          <div class="modal-overlay" id="modal">
            <div class="modal-box">
              <div class="modal-header">
                <h3 id="modalTitle"></h3>
                <button class="modal-close" id="modalClose">✕</button>
              </div>
              <div class="modal-body" id="modalBody"></div>
            </div>
          </div>

          <script>
          (function(){
            const API_BASE = '/api/v1';
            function buildFetchOpts(extra) {
              const opts = { credentials: 'same-origin' };
              const h = { 'Content-Type': 'application/json' };
              opts.headers = h;
              return Object.assign(opts, extra || {});
            }

            const PHASE_COLORS = {
              fetch:   { color: '#3b82f6', label: 'Phase 2 · 抓取' },
              prepare: { color: '#10b981', label: 'Phase 3 · 准备' },
              produce: { color: '#8b5cf6', label: 'Phase 4 · 生产' },
            };

            // pipeline 定义内嵌在 HTML 中，无需 API 调用
            const EMBEDDED_REGISTRY = __PIPELINE_REGISTRY_JSON__;

            let pipelineData = null;
            let settingsData = {};
            let activeStepId = null;

            async function init() {
              try {
                const registry = EMBEDDED_REGISTRY;
                pipelineData = registry;
                // settings 仍从 API 获取（error-tolerant）
                try {
                  const r = await fetch(API_BASE + '/admin/settings', buildFetchOpts());
                  if (r.ok) { const arr = await r.json(); for (const s of arr) settingsData[s.key] = s; }
                } catch(_) {}
                document.getElementById('pipeDesc').textContent = registry.description || '';
                renderPipeline(registry);
              } catch(e) {
                document.getElementById('pipeGraph').innerHTML =
                  '<div class="pipe-loading">' + e.message + '</div>';
              }
            }

            function connectorSVG(color) {
              return '<div class="step-connector">' +
                '<svg viewBox="0 0 32 16"><path d="M2 8h20" stroke="' + color +
                '" stroke-width="1.5" fill="none" stroke-linecap="round"/>' +
                '<path d="M20 4l6 4-6 4" stroke="' + color +
                '" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg></div>';
            }

            function renderPipeline(reg) {
              let html = '';
              for (const phase of reg.phases) {
                const pc = PHASE_COLORS[phase.id] || { color: '#64748b', label: phase.label };
                html += '<div class="phase-section">';
                html += '<div class="phase-header">';
                html += '<span class="phase-dot" style="background:' + pc.color + '"></span>';
                html += '<span class="phase-title" style="color:' + pc.color + '">' + pc.label + '</span>';
                html += '<span class="phase-line"></span>';
                html += '</div>';
                html += '<div class="phase-steps">';

                const steps = phase.steps.map(sid => reg.all_steps.find(s => s.id === sid)).filter(Boolean);
                steps.forEach((step, i) => {
                  if (i > 0) html += connectorSVG(pc.color);
                  const hasBadge = step.configurable && step.settings && step.settings.length > 0;
                  const hasKids = step.children && step.children.length > 0;
                  let hint = '';
                  if (hasBadge) hint = step.settings.length + ' 项可配置';
                  else if (hasKids) hint = step.children.length + ' 个子步骤';

                  html += '<div class="step-card" data-step-id="' + step.id + '" data-phase="' + phase.id + '">';
                  html += '<span class="step-icon">' + step.icon + '</span>';
                  html += '<div class="step-info"><span class="step-name">' + step.label + '</span>';
                  if (hint) html += '<span class="step-hint">' + hint + '</span>';
                  html += '</div>';
                  if (hasBadge) html += '<span class="step-badge">' + step.settings.length + '</span>';
                  html += '</div>';
                });

                html += '</div></div>';
              }

              const el = document.getElementById('pipeGraph');
              el.innerHTML = html;
              el.querySelectorAll('.step-card').forEach(node => {
                node.addEventListener('click', () => handleClick(node.dataset.stepId));
              });
            }

            function handleClick(stepId) {
              const step = pipelineData.all_steps.find(s => s.id === stepId);
              if (!step) return;
              if (step.children && step.children.length > 0) { showModal(step); return; }
              if (step.configurable && step.settings && step.settings.length > 0) { toggleConfig(step); return; }
            }

            function toggleConfig(step) {
              const panel = document.getElementById('configPanel');
              document.querySelectorAll('.step-card.active').forEach(n => n.classList.remove('active'));

              if (activeStepId === step.id) { panel.innerHTML = ''; activeStepId = null; return; }
              activeStepId = step.id;

              const nodeEl = document.querySelector('[data-step-id="' + step.id + '"]');
              if (nodeEl) nodeEl.classList.add('active');

              let html = '<div class="config-panel">';
              html += '<div class="config-header"><span class="cfg-icon">' + step.icon + '</span>';
              html += '<span class="cfg-title">' + step.label + ' 参数配置</span></div>';
              html += '<div class="config-body">';

              step.settings.forEach(key => {
                const s = settingsData[key];
                if (!s) {
                  html += '<div class="config-row"><span class="config-label">' + key + '</span><span class="config-default">未注册</span></div>';
                  return;
                }
                const val = s.effective_value || s.default_value || '';
                const def = s.default_value || '';
                html += '<div class="config-row" data-key="' + key + '">';
                html += '<span class="config-label">' + s.label + '</span>';
                html += '<span class="config-default">默认 ' + def + '</span>';
                html += '<input class="config-input" type="text" value="' + val + '" />';
                html += '<button class="config-btn save" onclick="window._save(\'' + key + '\',this)">保存</button>';
                if (s.has_override) html += '<button class="config-btn reset" onclick="window._reset(\'' + key + '\',this)">恢复</button>';
                html += '<span class="config-saved">✓ 已保存</span>';
                html += '</div>';
              });

              html += '</div></div>';
              panel.innerHTML = html;
            }

            window._save = async function(key, btn) {
              const row = btn.closest('.config-row');
              const input = row.querySelector('.config-input');
              btn.disabled = true;
              try {
                const r = await fetch(API_BASE + '/admin/settings/' + key, buildFetchOpts({
                  method: 'PUT',
                  body: JSON.stringify({ value: input.value.trim() }),
                }));
                if (!r.ok) { const e = await r.json().catch(() => ({})); alert('失败: ' + (e.detail||r.statusText)); return; }
                const u = await r.json();
                settingsData[key] = u;
                const ok = row.querySelector('.config-saved');
                if (ok) { ok.classList.add('show'); setTimeout(() => ok.classList.remove('show'), 2000); }
              } finally { btn.disabled = false; }
            };

            window._reset = async function(key, btn) {
              const row = btn.closest('.config-row');
              btn.disabled = true;
              try {
                const r = await fetch(API_BASE + '/admin/settings/' + key, buildFetchOpts({
                  method: 'PUT',
                  body: JSON.stringify({ reset_to_default: true }),
                }));
                if (!r.ok) { const e = await r.json().catch(() => ({})); alert('失败: ' + (e.detail||r.statusText)); return; }
                const u = await r.json();
                settingsData[key] = u;
                const input = row.querySelector('.config-input');
                if (input) input.value = u.effective_value || u.default_value || '';
                btn.remove();
                const ok = row.querySelector('.config-saved');
                if (ok) { ok.textContent = '✓ 已恢复'; ok.classList.add('show'); setTimeout(() => ok.classList.remove('show'), 2000); }
              } finally { btn.disabled = false; }
            };

            function showModal(step) {
              document.getElementById('modalTitle').textContent = step.icon + ' ' + step.label + ' — 子流程';
              let html = '';
              step.children.forEach((c, i) => {
                if (i > 0) html += '<div class="sub-arrow">↓</div>';
                html += '<div class="sub-step"><span class="sub-icon">' + c.icon + '</span>' + c.label + '</div>';
              });
              document.getElementById('modalBody').innerHTML = html;
              document.getElementById('modal').classList.add('open');
            }

            document.getElementById('modalClose').onclick = () => document.getElementById('modal').classList.remove('open');
            document.getElementById('modal').onclick = (e) => {
              if (e.target.id === 'modal') document.getElementById('modal').classList.remove('open');
            };

            init();
          })();
          </script>
        </body>
        </html>
        """
    )
    html = html.replace("__PIPELINE_REGISTRY_JSON__", _registry_json)
    return render_admin_page(html, "pipeline")


@router.get("/admin/settings", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def settings_console() -> str:
    html = dedent(
        """\
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>设置</title>
          <style>
            __ADMIN_SHARED_STYLES__

            .settings-container {
              max-width: 720px;
              margin: 0 auto;
              padding: 32px 20px;
            }
            .section {
              margin-bottom: 28px;
            }
            .section-header {
              display: flex;
              align-items: center;
              justify-content: space-between;
              margin-bottom: 12px;
            }
            .section-title {
              font-size: 14px;
              font-weight: 600;
              color: var(--text);
              text-transform: uppercase;
              letter-spacing: 0.5px;
            }
            .section-action {
              font-size: 12px;
              color: var(--primary);
              cursor: pointer;
              background: none;
              border: none;
              font-weight: 500;
            }
            .section-action:hover {
              text-decoration: underline;
            }

            /* 配置卡片 */
            .config-card {
              background: var(--bg-card);
              border: 1px solid var(--border);
              border-radius: var(--radius-md);
              overflow: hidden;
            }
            .config-row {
              display: flex;
              align-items: center;
              justify-content: space-between;
              padding: 12px 18px;
              border-bottom: 1px solid var(--border-light);
              gap: 12px;
              min-height: 44px;
            }
            .config-row:last-child {
              border-bottom: none;
            }
            .config-key {
              font-size: 13px;
              font-weight: 500;
              color: var(--text-secondary);
              flex-shrink: 0;
              min-width: 100px;
            }
            .config-value {
              font-size: 13px;
              color: var(--text);
              text-align: right;
              word-break: break-all;
              flex: 1;
            }
            .config-value select,
            .config-value input {
              padding: 4px 8px;
              border: 1px solid var(--border);
              border-radius: var(--radius-sm);
              font-size: 13px;
              background: var(--bg-input);
              color: var(--text);
              text-align: right;
              min-width: 140px;
            }
            .config-value select:focus,
            .config-value input:focus {
              outline: none;
              border-color: var(--primary);
            }

            /* 状态标签 */
            .badge {
              display: inline-block;
              padding: 2px 8px;
              border-radius: 999px;
              font-size: 11px;
              font-weight: 600;
            }
            .badge.ok {
              background: var(--success-soft);
              color: #047857;
            }
            .badge.warn {
              background: var(--warning-soft);
              color: #B45309;
            }
            .badge.error {
              background: var(--danger-soft);
              color: var(--danger);
            }
            .badge.na {
              background: var(--border-light);
              color: var(--text-secondary);
            }

            /* 操作栏 */
            .action-bar {
              display: flex;
              gap: 8px;
              margin-bottom: 24px;
            }
            .action-bar button {
              padding: 8px 20px;
              border: none;
              border-radius: var(--radius-sm);
              font-size: 13px;
              font-weight: 600;
              cursor: pointer;
              transition: all var(--transition);
            }
            .btn-refresh {
              background: var(--bg-card);
              color: var(--text);
              border: 1px solid var(--border) !important;
            }
            .btn-refresh:hover {
              border-color: var(--primary) !important;
              color: var(--primary);
            }
            .btn-save {
              background: var(--primary);
              color: #fff;
            }
            .btn-save:hover {
              background: var(--primary-hover);
            }
            .btn-save:disabled {
              opacity: 0.5;
              cursor: not-allowed;
            }

            /* 消息提示 */
            .flash {
              display: none;
              padding: 10px 16px;
              border-radius: var(--radius-sm);
              font-size: 13px;
              margin-bottom: 16px;
            }
            .flash.ok {
              background: var(--success-soft);
              color: #047857;
            }
            .flash.fail {
              background: var(--danger-soft);
              color: var(--danger);
            }

            /* 底部返回 */
            .back-link {
              text-align: center;
              margin-top: 32px;
              padding-top: 20px;
              border-top: 1px solid var(--border-light);
            }
            .back-link a {
              font-size: 13px;
              color: var(--text-secondary);
              text-decoration: none;
            }
            .back-link a:hover {
              color: var(--primary);
            }

            .loading {
              text-align: center;
              padding: 20px;
              color: var(--text-secondary);
              font-size: 13px;
            }
          </style>
        </head>
        <body class="admin-app">
          <script>__ADMIN_SHARED_SCRIPT_HELPERS__</script>

          <main class="admin-main">
            <div class="settings-container">
              <!-- 消息提示 -->
              <div class="flash" id="flash-msg"></div>

              <!-- 操作栏 -->
              <div class="action-bar">
                <button class="btn-refresh" id="btn-refresh" onclick="loadAll()">刷新</button>
                <button class="btn-save" id="btn-save" onclick="saveChanges()" disabled>保存修改</button>
              </div>

              <!-- LLM 配置 -->
              <div class="section">
                <div class="section-header">
                  <span class="section-title">LLM 配置</span>
                  <button class="section-action" onclick="testLlm()">测试连通</button>
                </div>
                <div class="config-card" id="llm-card">
                  <div class="loading">加载中...</div>
                </div>
              </div>

              <!-- 运行设置 -->
              <div class="section">
                <div class="section-header">
                  <span class="section-title">运行设置</span>
                </div>
                <div class="config-card" id="settings-card">
                  <div class="loading">加载中...</div>
                </div>
              </div>

              <!-- 环境状态 -->
              <div class="section">
                <div class="section-header">
                  <span class="section-title">环境状态</span>
                </div>
                <div class="config-card" id="env-card">
                  <div class="loading">加载中...</div>
                </div>
              </div>

              <!-- 返回工作台 -->
              <div class="back-link">
                <a href="/admin">← 返回工作台</a>
              </div>
            </div>
          </main>

          <script>
            const { apiUrl, escapeHtml, parseJsonResponse, setButtonBusy } = AdminUiShared;

            // API 请求
            const request = async (path, opts = {}) => {
              const res = await fetch(apiUrl(path), {
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                ...opts,
              });
              if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || res.statusText);
              }
              return res.json();
            };

            // 消息提示
            const flash = (msg, type = "ok") => {
              const el = document.getElementById("flash-msg");
              el.textContent = msg;
              el.className = `flash ${type}`;
              el.style.display = "block";
              setTimeout(() => { el.style.display = "none"; }, 4000);
            };

            // 状态
            let llmConfig = null;
            let settingsData = [];
            let envData = [];
            let pendingChanges = {};

            // 加载全部
            const loadAll = async () => {
              setButtonBusy(document.getElementById("btn-refresh"), true);
              try {
                await Promise.all([loadLlm(), loadSettings(), loadEnv()]);
                flash("已刷新");
              } catch (e) {
                flash(e.message || "加载失败", "fail");
              } finally {
                setButtonBusy(document.getElementById("btn-refresh"), false);
              }
            };

            // LLM 配置
            const loadLlm = async () => {
              const data = await request("/api/v1/admin/llm-config");
              llmConfig = data;
              const card = document.getElementById("llm-card");
              const rows = [
                configRow("供应商", escapeHtml(data.provider || "—")),
                configRow("分析模型", escapeHtml(data.model_analyze || "—")),
                configRow("写作模型", escapeHtml(data.model_write || "—")),
                configRow("审核模型", escapeHtml(data.model_review || "—")),
              ];
              card.innerHTML = rows.join("");
            };

            // 运行设置
            const loadSettings = async () => {
              const data = await request("/api/v1/admin/settings");
              settingsData = data.settings || [];
              const card = document.getElementById("settings-card");
              if (!settingsData.length) {
                card.innerHTML = '<div class="loading">无可配置项</div>';
                return;
              }
              card.innerHTML = settingsData.map((s) => {
                const key = escapeHtml(s.key);
                const val = escapeHtml(s.value ?? s.default ?? "");
                if (s.type === "bool") {
                  return configRowSelect(key, escapeHtml(s.label || s.key), val === "true" ? "true" : "false", [
                    { v: "true", l: "开" },
                    { v: "false", l: "关" },
                  ]);
                }
                return configRowInput(key, escapeHtml(s.label || s.key), val);
              }).join("");
              pendingChanges = {};
              document.getElementById("btn-save").disabled = true;
            };

            // 环境状态
            const loadEnv = async () => {
              const data = await request("/api/v1/admin/runtime-status");
              envData = data;
              const card = document.getElementById("env-card");
              const items = data.checks || data.items || [];
              if (Array.isArray(items) && items.length) {
                card.innerHTML = items.map((item) => {
                  const status = item.ok ? "ok" : (item.warning ? "warn" : "error");
                  const label = item.ok ? "正常" : (item.warning ? "警告" : "异常");
                  return `<div class="config-row">
                    <span class="config-key">${escapeHtml(item.name || item.key)}</span>
                    <span class="config-value"><span class="badge ${status}">${label}</span></span>
                  </div>`;
                }).join("");
              } else {
                // 如果返回的是平铺字段
                const entries = Object.entries(data).filter(([k]) => !["ok", "message"].includes(k));
                card.innerHTML = entries.map(([k, v]) => {
                  const val = typeof v === "object" ? JSON.stringify(v) : String(v);
                  return `<div class="config-row">
                    <span class="config-key">${escapeHtml(k)}</span>
                    <span class="config-value">${escapeHtml(val)}</span>
                  </div>`;
                }).join("") || '<div class="loading">无数据</div>';
              }
            };

            // Helper: 只读行
            const configRow = (label, value) => `
              <div class="config-row">
                <span class="config-key">${label}</span>
                <span class="config-value">${value}</span>
              </div>`;

            // Helper: 输入行
            const configRowInput = (key, label, value) => `
              <div class="config-row">
                <span class="config-key">${label}</span>
                <span class="config-value">
                  <input type="text" value="${value}" data-key="${key}" onchange="markChanged(this)" />
                </span>
              </div>`;

            // Helper: 下拉行
            const configRowSelect = (key, label, value, options) => `
              <div class="config-row">
                <span class="config-key">${label}</span>
                <span class="config-value">
                  <select data-key="${key}" onchange="markChanged(this)">
                    ${options.map((o) => `<option value="${o.v}" ${o.v === value ? 'selected' : ''}>${o.l}</option>`).join("")}
                  </select>
                </span>
              </div>`;

            // 标记修改
            const markChanged = (el) => {
              pendingChanges[el.dataset.key] = el.value;
              document.getElementById("btn-save").disabled = Object.keys(pendingChanges).length === 0;
            };

            // 保存修改
            const saveChanges = async () => {
              const btn = document.getElementById("btn-save");
              setButtonBusy(btn, true);
              try {
                for (const [key, value] of Object.entries(pendingChanges)) {
                  await request(`/api/v1/admin/settings/${encodeURIComponent(key)}`, {
                    method: "PUT",
                    body: JSON.stringify({ value, operator: "admin-web", note: "" }),
                  });
                }
                flash(`已保存 ${Object.keys(pendingChanges).length} 项`);
                pendingChanges = {};
                btn.disabled = true;
                await loadSettings();
              } catch (e) {
                flash(e.message || "保存失败", "fail");
              } finally {
                setButtonBusy(btn, false);
              }
            };

            // 测试 LLM 连通
            const testLlm = async () => {
              flash("测试中...");
              try {
                const result = await request("/api/v1/admin/llm-test", { method: "POST" });
                flash(result.ok ? "LLM 连通正常 ✓" : `LLM 测试失败: ${result.message || "未知错误"}`, result.ok ? "ok" : "fail");
              } catch (e) {
                flash(e.message || "测试失败", "fail");
              }
            };

            // 初始化
            loadAll();
          </script>
        </body>
        </html>
        """
    )
    return render_admin_page(html, "settings")
