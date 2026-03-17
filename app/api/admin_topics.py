from __future__ import annotations

from textwrap import dedent

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.admin_ui import admin_overview_card, admin_overview_strip, render_admin_page
from app.core.security import verify_admin_basic_auth
from app.db.session import get_db_session
from app.schemas.topic_intelligence import (
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

    html = dedent(
        """\
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>选题情报台</title>
          <style>
            __ADMIN_SHARED_STYLES__

            .topics-shell { display: grid; gap: 20px; }
            .topics-grid {
              display: grid;
              grid-template-columns: minmax(340px, 420px) minmax(0, 1fr);
              gap: 20px;
              align-items: start;
            }
            .topics-status-banner {
              margin-bottom: 12px;
              padding: 10px 12px;
              border-radius: var(--radius-sm);
              border: 1px solid var(--border);
              background: var(--bg-input);
              color: var(--text-secondary);
              font-size: 13px;
              line-height: 1.6;
            }
            .topics-status-banner.success {
              background: var(--success-soft);
              color: #047857;
              border-color: rgba(16,185,129,.18);
            }
            .topics-status-banner.warn {
              background: var(--warning-soft);
              color: #B45309;
              border-color: rgba(245,158,11,.18);
            }
            .topics-status-banner.error {
              background: var(--danger-soft);
              color: var(--danger);
              border-color: rgba(239,68,68,.18);
            }
            .topics-list {
              display: grid;
              gap: 10px;
              max-height: 420px;
              overflow: auto;
              padding-right: 4px;
            }
            .topics-filter-grid {
              display: grid;
              grid-template-columns: repeat(3, minmax(0, 1fr));
              gap: 10px;
              margin-bottom: 14px;
            }
            .topic-card {
              display: grid;
              gap: 10px;
              padding: 14px;
              border: 1px solid var(--border);
              border-radius: var(--radius-md);
              background: linear-gradient(180deg, #fff 0%, #f8fbff 100%);
              box-shadow: var(--shadow-card);
            }
            .topic-card.selected {
              border-color: rgba(59,130,246,.35);
              box-shadow: 0 0 0 3px rgba(59,130,246,.08), var(--shadow-card);
            }
            .topic-card-head {
              display: flex;
              justify-content: space-between;
              gap: 10px;
              align-items: flex-start;
            }
            .topic-card-head h3 {
              margin: 0;
              font-size: 15px;
              line-height: 1.45;
            }
            .topic-card-meta {
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
              font-size: 12px;
              color: var(--text-secondary);
            }
            .topic-card-copy {
              margin: 0;
              font-size: 13px;
              color: var(--text-secondary);
              line-height: 1.7;
            }
            .topic-card-actions {
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
            }
            .topic-card-actions button,
            .topic-card-actions a {
              min-height: 30px;
              padding: 5px 10px;
              font-size: 12px;
            }
            .topic-pill-row {
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
            }
            .topic-workspace-empty {
              min-height: 320px;
              display: grid;
              place-items: center;
              text-align: center;
              border: 1px dashed var(--border);
              border-radius: var(--radius-md);
              color: var(--text-secondary);
              background: var(--bg-input);
              padding: 24px;
              line-height: 1.8;
            }
            .topic-workspace {
              display: grid;
              gap: 16px;
            }
            .topic-workspace-head {
              display: grid;
              gap: 10px;
              padding-bottom: 14px;
              border-bottom: 1px solid var(--border);
            }
            .topic-workspace-head h2 {
              margin: 0;
              font-size: 24px;
              line-height: 1.3;
            }
            .topic-workspace-summary {
              margin: 0;
              color: var(--text-secondary);
              line-height: 1.8;
            }
            .topic-metrics {
              display: grid;
              grid-template-columns: repeat(4, minmax(0, 1fr));
              gap: 10px;
            }
            .topic-metric {
              display: grid;
              gap: 4px;
              padding: 12px;
              border: 1px solid var(--border);
              border-radius: var(--radius-sm);
              background: var(--bg-input);
            }
            .topic-metric strong {
              color: var(--text-secondary);
              font-size: 11px;
              font-weight: 600;
              text-transform: uppercase;
              letter-spacing: .04em;
            }
            .topic-metric span {
              font-size: 22px;
              font-weight: 800;
              letter-spacing: -.02em;
            }
            .topic-section {
              display: grid;
              gap: 10px;
              padding: 14px;
              border: 1px solid var(--border);
              border-radius: var(--radius-md);
              background: #fff;
            }
            .topic-section h3 {
              margin: 0;
              font-size: 16px;
            }
            .topic-kv {
              display: grid;
              grid-template-columns: 120px minmax(0, 1fr);
              gap: 10px 12px;
              align-items: start;
            }
            .topic-kv strong {
              color: var(--text-secondary);
              font-size: 12px;
              text-transform: uppercase;
              letter-spacing: .04em;
            }
            .topic-kv div,
            .topic-kv p {
              margin: 0;
              font-size: 14px;
              line-height: 1.75;
            }
            .topic-tag-list,
            .topic-bullet-list {
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
              margin: 0;
              padding: 0;
              list-style: none;
            }
            .topic-bullet-list {
              display: grid;
              gap: 8px;
            }
            .topic-bullet-list li {
              padding: 10px 12px;
              border-radius: var(--radius-sm);
              background: var(--bg-input);
              border: 1px solid var(--border);
              line-height: 1.7;
            }
            .topic-tag {
              display: inline-flex;
              align-items: center;
              padding: 6px 10px;
              border-radius: 999px;
              background: var(--primary-soft);
              color: var(--primary);
              font-size: 12px;
              font-weight: 600;
            }
            .topic-source-list,
            .topic-task-link-list {
              display: grid;
              gap: 10px;
            }
            .topic-source-item,
            .topic-task-link-item {
              display: grid;
              gap: 8px;
              padding: 12px;
              border-radius: var(--radius-sm);
              background: var(--bg-input);
              border: 1px solid var(--border);
            }
            .topic-source-item h4,
            .topic-task-link-item h4 {
              margin: 0;
              font-size: 14px;
              line-height: 1.6;
            }
            .topic-source-item p,
            .topic-task-link-item p {
              margin: 0;
              color: var(--text-secondary);
              font-size: 13px;
              line-height: 1.7;
            }
            .topic-source-item a,
            .topic-task-link-item a {
              width: fit-content;
            }
            .topic-form-grid {
              display: grid;
              gap: 10px;
            }
            .topic-inline-check {
              display: flex;
              align-items: center;
              gap: 8px;
              color: var(--text-secondary);
              font-size: 13px;
            }
            .topic-inline-check input {
              width: auto;
              min-height: auto;
            }
            @media (max-width: 1180px) {
              .topics-grid { grid-template-columns: 1fr; }
              .topic-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            }
            @media (max-width: 760px) {
              .topics-filter-grid,
              .topic-metrics,
              .topic-kv { grid-template-columns: 1fr; }
            }
          </style>
        </head>
        <body>
          <div class="topics-shell shell">
            <section class="hero">
              <div class="hero-grid">
                <div class="hero-copy">
                  <span class="eyebrow">Topic Intelligence</span>
                  <h1>长期选题情报台</h1>
                  <p>持续抓取公开信号，形成候选池和计划，再把值得做的题推进到任务链路。这里解决的是“写什么”，不是“怎么写”。</p>
                  <div class="hero-links">
                    <a href="/admin">回工作台</a>
                    <a href="/admin/console">看监控</a>
                    <a href="/admin/settings">调整运行参数</a>
                  </div>
                </div>
                <div class="hero-status-card">
                  <p class="hero-status-copy">推荐工作流：先跑来源，再刷新候选池，最后在右侧工作区确认角度、证据和推进动作。</p>
                  <div class="hero-summary">
                    <div class="hero-summary-card">
                      <strong>来源操作</strong>
                      <span>立即运行 / 仅入队</span>
                    </div>
                    <div class="hero-summary-card">
                      <strong>候选筛选</strong>
                      <span>按状态、内容支柱和数量过滤</span>
                    </div>
                    <div class="hero-summary-card wide">
                      <strong>推进动作</strong>
                      <span>在工作区直接把计划提升为任务，并决定是否自动进入 Phase 3。</span>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            __TOPICS_OVERVIEW__

            <section class="topics-grid">
              <div class="stack">
                <section class="panel">
                  <div class="panel-head">
                    <div>
                      <h2>来源监控</h2>
                      <p class="panel-intro">对单个 watchlist 立刻抓取，或者只把它放进后台队列。</p>
                    </div>
                    <div class="panel-tools">
                      <button id="refresh-snapshot" class="secondary tiny-button" type="button">刷新快照</button>
                      <button id="refresh-candidates" class="tiny-button" type="button">刷新候选池</button>
                    </div>
                  </div>
                  <div id="topics-status-banner" class="topics-status-banner">准备加载选题快照...</div>
                  <div id="topics-source-list" class="topics-list">
                    <div class="topic-workspace-empty">正在加载来源...</div>
                  </div>
                </section>

                <section class="panel">
                  <div class="panel-head">
                    <div>
                      <h2>候选池</h2>
                      <p class="panel-intro">点击左侧候选，在右侧查看计划、证据和推进动作。</p>
                    </div>
                    <div class="panel-tools">
                      <button id="clear-selection" class="ghost tiny-button" type="button">清空选择</button>
                    </div>
                  </div>
                  <div class="topics-filter-grid">
                    <div class="field">
                      <label for="topic-status-filter">状态</label>
                      <select id="topic-status-filter">
                        <option value="">全部状态</option>
                        <option value="new">new</option>
                        <option value="planned">planned</option>
                        <option value="promoted">promoted</option>
                        <option value="watching">watching</option>
                        <option value="ignored">ignored</option>
                      </select>
                    </div>
                    <div class="field">
                      <label for="topic-pillar-filter">内容支柱</label>
                      <select id="topic-pillar-filter">
                        <option value="">全部支柱</option>
                        <option value="wechat_ecosystem">微信生态</option>
                        <option value="ai_industry">AI 产业</option>
                        <option value="solopreneur_methods">单人运营</option>
                      </select>
                    </div>
                    <div class="field">
                      <label for="topic-limit-filter">数量</label>
                      <select id="topic-limit-filter">
                        <option value="10">10</option>
                        <option value="20">20</option>
                        <option value="50">50</option>
                        <option value="100">100</option>
                      </select>
                    </div>
                  </div>
                  <div id="topics-candidate-list" class="topics-list">
                    <div class="topic-workspace-empty">正在加载候选...</div>
                  </div>
                </section>
              </div>

              <div class="stack">
                <section class="panel">
                  <div class="panel-head">
                    <div>
                      <h2>选题工作区</h2>
                      <p class="panel-intro">这里汇总当前计划、证据信号和已推进任务。</p>
                    </div>
                  </div>
                  <div id="topics-workspace" class="topic-workspace-empty">
                    先从左侧选择一个候选，系统会展示当前最新计划和对应信号。
                  </div>
                </section>
              </div>
            </section>
          </div>

          <script>
            __ADMIN_SHARED_SCRIPT_HELPERS__

            (() => {
              const PILLAR_LABELS = {
                wechat_ecosystem: "微信生态",
                ai_industry: "AI 产业",
                solopreneur_methods: "单人运营"
              };

              const statusEl = document.getElementById("topics-status-banner");
              const sourceListEl = document.getElementById("topics-source-list");
              const candidateListEl = document.getElementById("topics-candidate-list");
              const workspaceEl = document.getElementById("topics-workspace");
              const refreshSnapshotBtn = document.getElementById("refresh-snapshot");
              const refreshCandidatesBtn = document.getElementById("refresh-candidates");
              const clearSelectionBtn = document.getElementById("clear-selection");
              const statusFilterEl = document.getElementById("topic-status-filter");
              const pillarFilterEl = document.getElementById("topic-pillar-filter");
              const limitFilterEl = document.getElementById("topic-limit-filter");

              const state = {
                status: AdminUiShared.storageGet("admin_topics_status", ""),
                pillar: AdminUiShared.storageGet("admin_topics_pillar", ""),
                limit: AdminUiShared.storageGet("admin_topics_limit", "20"),
                selectedCandidateId: AdminUiShared.storageGet("admin_topics_selected_candidate", ""),
                operator: AdminUiShared.storageGet("admin_topics_operator", "admin-topics"),
                note: AdminUiShared.storageGet("admin_topics_note", ""),
                enqueuePhase3: AdminUiShared.storageGet("admin_topics_enqueue_phase3", "true") !== "false",
                snapshot: null,
                sources: []
              };

              const setStatus = (message, tone = "info") => {
                statusEl.className = `topics-status-banner${tone === "info" ? "" : ` ${tone}`}`;
                statusEl.textContent = message;
              };

              const persist = () => {
                AdminUiShared.storageSet("admin_topics_status", state.status);
                AdminUiShared.storageSet("admin_topics_pillar", state.pillar);
                AdminUiShared.storageSet("admin_topics_limit", state.limit);
                AdminUiShared.storageSet("admin_topics_selected_candidate", state.selectedCandidateId);
                AdminUiShared.storageSet("admin_topics_operator", state.operator);
                AdminUiShared.storageSet("admin_topics_note", state.note);
                AdminUiShared.storageSet("admin_topics_enqueue_phase3", state.enqueuePhase3 ? "true" : "false");
              };

              const formatDate = (value) => {
                if (!value) return "未记录";
                const date = new Date(value);
                if (Number.isNaN(date.getTime())) return String(value);
                return date.toLocaleString("zh-CN", { hour12: false });
              };

              const formatScore = (value) => {
                if (value === null || value === undefined || value === "") return "--";
                const numeric = Number(value);
                if (Number.isNaN(numeric)) return String(value);
                return numeric.toFixed(1);
              };

              const pill = (text) => `<span class="topic-tag">${AdminUiShared.escapeHtml(text)}</span>`;

              const toList = (value) => {
                if (Array.isArray(value)) return value.filter(Boolean);
                if (!value || typeof value !== "object") return [];
                return []
                  .concat(Array.isArray(value.items) ? value.items : [])
                  .concat(Array.isArray(value.points) ? value.points : [])
                  .concat(Array.isArray(value.primary) ? value.primary : [])
                  .concat(Array.isArray(value.queries) ? value.queries : [])
                  .concat(Array.isArray(value.urls) ? value.urls : [])
                  .filter(Boolean);
              };

              const requestJson = async (path, { method = "GET", body } = {}) => {
                const response = await fetch(AdminUiShared.apiUrl(path), {
                  method,
                  headers: body ? { "Content-Type": "application/json" } : undefined,
                  body: body ? JSON.stringify(body) : undefined,
                  credentials: "same-origin"
                });
                const payload = await AdminUiShared.parseJsonResponse(response);
                if (!response.ok) {
                  throw new Error(payload.detail || payload.raw || JSON.stringify(payload));
                }
                return payload;
              };

              const buildSnapshotPath = () => {
                const params = new URLSearchParams();
                params.set("limit", state.limit || "20");
                if (state.status) params.set("status", state.status);
                if (state.pillar) params.set("content_pillar", state.pillar);
                if (state.selectedCandidateId) params.set("selected_candidate_id", state.selectedCandidateId);
                return `/api/v1/admin/topics/snapshot?${params.toString()}`;
              };

              const renderSummary = (summary) => {
                document.getElementById("summary-source-enabled").textContent = String(summary?.source_enabled ?? 0);
                document.getElementById("summary-candidate-total").textContent = String(summary?.candidate_total ?? 0);
                document.getElementById("summary-planned-total").textContent = String(summary?.planned_total ?? 0);
                document.getElementById("summary-new-signal-24h").textContent = String(summary?.new_signal_24h ?? 0);
              };

              const renderSources = (sources) => {
                if (!Array.isArray(sources) || sources.length === 0) {
                  sourceListEl.innerHTML = '<div class="topic-workspace-empty">还没有可用来源。</div>';
                  return;
                }
                sourceListEl.innerHTML = sources.map((source) => `
                  <article class="topic-card">
                    <div class="topic-card-head">
                      <div>
                        <h3>${AdminUiShared.escapeHtml(source.name)}</h3>
                        <div class="topic-card-meta">
                          ${pill(PILLAR_LABELS[source.content_pillar] || source.content_pillar || "未分组")}
                          ${pill(source.enabled ? "enabled" : "disabled")}
                          ${pill(`${source.signal_count ?? 0} 条信号`)}
                        </div>
                      </div>
                    </div>
                    <p class="topic-card-copy">${AdminUiShared.escapeHtml((source.config?.queries || []).slice(0, 2).join(" / ") || "暂无查询词")}</p>
                    <div class="topic-card-meta">
                      <span>最近成功：${AdminUiShared.escapeHtml(formatDate(source.last_success_at))}</span>
                      <span>上次抓取：${AdminUiShared.escapeHtml(formatDate(source.last_fetched_at))}</span>
                    </div>
                    ${source.last_error ? `<p class="topic-card-copy">最近错误：${AdminUiShared.escapeHtml(source.last_error)}</p>` : ""}
                    <div class="topic-card-actions">
                      <button type="button" class="tiny-button" data-run-source="${AdminUiShared.escapeHtml(source.source_id)}">立即运行</button>
                      <button type="button" class="secondary tiny-button" data-enqueue-source="${AdminUiShared.escapeHtml(source.source_id)}">仅入队</button>
                    </div>
                  </article>
                `).join("");
              };

              const renderCandidates = (candidates) => {
                if (!Array.isArray(candidates) || candidates.length === 0) {
                  candidateListEl.innerHTML = '<div class="topic-workspace-empty">当前筛选条件下没有候选。</div>';
                  return;
                }
                candidateListEl.innerHTML = candidates.map((candidate) => `
                  <article class="topic-card ${state.selectedCandidateId === candidate.candidate_id ? "selected" : ""}">
                    <div class="topic-card-head">
                      <div>
                        <h3>${AdminUiShared.escapeHtml(candidate.topic_title)}</h3>
                        <div class="topic-card-meta">
                          ${pill(candidate.status)}
                          ${pill(PILLAR_LABELS[candidate.content_pillar] || candidate.content_pillar || "未分组")}
                          ${pill(`总分 ${formatScore(candidate.total_score)}`)}
                        </div>
                      </div>
                    </div>
                    <p class="topic-card-copy">${AdminUiShared.escapeHtml(candidate.topic_summary || "暂无摘要")}</p>
                    <div class="topic-card-meta">
                      <span>信号数：${AdminUiShared.escapeHtml(String(candidate.signal_count ?? 0))}</span>
                      <span>最近信号：${AdminUiShared.escapeHtml(formatDate(candidate.latest_signal_at))}</span>
                    </div>
                    <div class="topic-card-actions">
                      <button type="button" class="secondary tiny-button" data-select-candidate="${AdminUiShared.escapeHtml(candidate.candidate_id)}">查看工作区</button>
                    </div>
                  </article>
                `).join("");
              };

              const renderWorkspace = (workspace) => {
                if (!workspace) {
                  workspaceEl.className = "topic-workspace-empty";
                  workspaceEl.innerHTML = "先从左侧选择一个候选，系统会展示当前最新计划和对应信号。";
                  return;
                }

                const candidate = workspace.candidate || {};
                const plan = workspace.plan || {};
                const mustCover = toList(plan.must_cover);
                const mustAvoid = toList(plan.must_avoid);
                const keywords = toList(plan.keywords);
                const recommendedQueries = toList(plan.recommended_queries);
                const taskLinks = Array.isArray(workspace.task_links) ? workspace.task_links : [];
                const signals = Array.isArray(workspace.signals) ? workspace.signals : [];

                workspaceEl.className = "topic-workspace";
                workspaceEl.innerHTML = `
                  <div class="topic-workspace-head">
                    <div class="topic-pill-row">
                      ${pill(candidate.status || "unknown")}
                      ${pill(PILLAR_LABELS[candidate.content_pillar] || candidate.content_pillar || "未分组")}
                      ${pill(`计划 v${plan.plan_version ?? 1}`)}
                    </div>
                    <h2>${AdminUiShared.escapeHtml(candidate.topic_title || "未命名选题")}</h2>
                    <p class="topic-workspace-summary">${AdminUiShared.escapeHtml(plan.summary || candidate.topic_summary || "暂无摘要")}</p>
                  </div>

                  <div class="topic-metrics">
                    <div class="topic-metric">
                      <strong>总分</strong>
                      <span>${AdminUiShared.escapeHtml(formatScore(candidate.total_score))}</span>
                    </div>
                    <div class="topic-metric">
                      <strong>信号数</strong>
                      <span>${AdminUiShared.escapeHtml(String(candidate.signal_count ?? 0))}</span>
                    </div>
                    <div class="topic-metric">
                      <strong>商业匹配</strong>
                      <span>${AdminUiShared.escapeHtml(formatScore(candidate.commercial_fit_score))}</span>
                    </div>
                    <div class="topic-metric">
                      <strong>微信适配</strong>
                      <span>${AdminUiShared.escapeHtml(formatScore(candidate.wechat_fit_score))}</span>
                    </div>
                  </div>

                  <section class="topic-section">
                    <h3>当前计划</h3>
                    <div class="topic-kv">
                      <strong>文章类型</strong>
                      <div>${AdminUiShared.escapeHtml(plan.article_type || "未指定")}</div>
                      <strong>业务目标</strong>
                      <div>${AdminUiShared.escapeHtml(plan.business_goal || "未指定")}</div>
                      <strong>角度</strong>
                      <p>${AdminUiShared.escapeHtml(plan.angle || "暂无")}</p>
                      <strong>为什么现在写</strong>
                      <p>${AdminUiShared.escapeHtml(plan.why_now || "暂无")}</p>
                      <strong>目标读者</strong>
                      <p>${AdminUiShared.escapeHtml(plan.target_reader || "暂无")}</p>
                      <strong>搜索标题</strong>
                      <p>${AdminUiShared.escapeHtml(plan.search_friendly_title || "暂无")}</p>
                      <strong>分发标题</strong>
                      <p>${AdminUiShared.escapeHtml(plan.distribution_friendly_title || "暂无")}</p>
                    </div>
                    ${keywords.length ? `<div><strong class="mini">关键词</strong><div class="topic-tag-list">${keywords.map((item) => pill(item)).join("")}</div></div>` : ""}
                    ${recommendedQueries.length ? `<div><strong class="mini">推荐查询词</strong><ul class="topic-bullet-list">${recommendedQueries.map((item) => `<li>${AdminUiShared.escapeHtml(item)}</li>`).join("")}</ul></div>` : ""}
                    ${mustCover.length ? `<div><strong class="mini">必须覆盖</strong><ul class="topic-bullet-list">${mustCover.map((item) => `<li>${AdminUiShared.escapeHtml(item)}</li>`).join("")}</ul></div>` : ""}
                    ${mustAvoid.length ? `<div><strong class="mini">必须回避</strong><ul class="topic-bullet-list">${mustAvoid.map((item) => `<li>${AdminUiShared.escapeHtml(item)}</li>`).join("")}</ul></div>` : ""}
                  </section>

                  <section class="topic-section">
                    <h3>推进动作</h3>
                    <div class="topic-form-grid">
                      <div class="field">
                        <label for="topic-promote-operator">operator</label>
                        <input id="topic-promote-operator" type="text" value="${AdminUiShared.escapeHtml(state.operator)}" />
                      </div>
                      <div class="field">
                        <label for="topic-promote-note">备注</label>
                        <textarea id="topic-promote-note" placeholder="例如：准备纳入本周重点题库">${AdminUiShared.escapeHtml(state.note)}</textarea>
                      </div>
                      <label class="topic-inline-check">
                        <input id="topic-promote-enqueue-phase3" type="checkbox" ${state.enqueuePhase3 ? "checked" : ""} />
                        提升为任务后，顺手进入 Phase 3 队列
                      </label>
                      <div class="topic-card-actions">
                        <button type="button" id="topic-promote-action" data-plan-id="${AdminUiShared.escapeHtml(plan.plan_id || "")}">
                          ${taskLinks.length ? "再次推进（走去重）" : "提升为任务"}
                        </button>
                      </div>
                    </div>
                  </section>

                  <section class="topic-section">
                    <h3>证据信号</h3>
                    <div class="topic-source-list">
                      ${signals.length ? signals.map((signal) => `
                        <article class="topic-source-item">
                          <h4>${AdminUiShared.escapeHtml(signal.title || "未命名信号")}</h4>
                          <p>${AdminUiShared.escapeHtml(signal.summary || "暂无摘要")}</p>
                          <div class="topic-card-meta">
                            ${pill(signal.source_tier || "未评级")}
                            <span>${AdminUiShared.escapeHtml(signal.source_site || "未知来源")}</span>
                            <span>${AdminUiShared.escapeHtml(formatDate(signal.published_at || signal.discovered_at))}</span>
                          </div>
                          <a class="button-link secondary tiny-button" href="${AdminUiShared.escapeHtml(signal.url || "#")}" target="_blank" rel="noreferrer">打开原文</a>
                        </article>
                      `).join("") : '<div class="topic-workspace-empty">暂无证据信号。</div>'}
                    </div>
                  </section>

                  <section class="topic-section">
                    <h3>已推进任务</h3>
                    <div class="topic-task-link-list">
                      ${taskLinks.length ? taskLinks.map((link) => `
                        <article class="topic-task-link-item">
                          <h4>${AdminUiShared.escapeHtml(link.task_id)}</h4>
                          <p>operator: ${AdminUiShared.escapeHtml(link.operator || "system")}</p>
                          <p>${AdminUiShared.escapeHtml(link.note || "无备注")}</p>
                          <a class="button-link secondary tiny-button" href="/admin?task_id=${encodeURIComponent(link.task_id)}">打开任务</a>
                        </article>
                      `).join("") : '<div class="topic-workspace-empty">这个计划还没有推进到任务链路。</div>'}
                    </div>
                  </section>
                `;
              };

              const loadPageData = async ({ autoSelect = false } = {}) => {
                try {
                  setStatus("正在刷新选题快照...");
                  const [snapshotPayload, sourcePayload] = await Promise.all([
                    requestJson(buildSnapshotPath()),
                    requestJson("/api/v1/admin/topics/sources")
                  ]);
                  state.snapshot = snapshotPayload;
                  state.sources = Array.isArray(sourcePayload) ? sourcePayload : [];
                  const candidates = Array.isArray(snapshotPayload?.candidates) ? snapshotPayload.candidates : [];
                  if (state.selectedCandidateId && !candidates.some((item) => item.candidate_id === state.selectedCandidateId)) {
                    state.selectedCandidateId = "";
                    persist();
                  }
                  if (autoSelect && !state.selectedCandidateId && Array.isArray(snapshotPayload?.candidates) && snapshotPayload.candidates.length) {
                    state.selectedCandidateId = snapshotPayload.candidates[0].candidate_id;
                    persist();
                    return loadPageData({ autoSelect: false });
                  }
                  renderSummary(snapshotPayload?.summary || {});
                  renderSources(state.sources);
                  renderCandidates(candidates);
                  renderWorkspace(snapshotPayload?.workspace || null);
                  setStatus(`快照已刷新：${snapshotPayload?.summary?.candidate_total ?? 0} 个候选，${snapshotPayload?.summary?.source_enabled ?? 0} 个启用来源。`, "success");
                } catch (error) {
                  setStatus(`刷新失败：${error.message}`, "error");
                }
              };

              const runAction = async (button, path, body, successMessage) => {
                try {
                  AdminUiShared.setButtonBusy(button, true);
                  const payload = await requestJson(path, { method: "POST", body });
                  setStatus(typeof successMessage === "function" ? successMessage(payload) : successMessage, "success");
                  await loadPageData();
                  return payload;
                } catch (error) {
                  setStatus(`操作失败：${error.message}`, "error");
                  throw error;
                } finally {
                  AdminUiShared.setButtonBusy(button, false);
                }
              };

              const bindEvents = () => {
                refreshSnapshotBtn.addEventListener("click", () => { loadPageData(); });
                refreshCandidatesBtn.addEventListener("click", () => {
                  runAction(
                    refreshCandidatesBtn,
                    "/admin/api/topics/refresh-candidates",
                    undefined,
                    (payload) => `候选池已刷新，生成或更新 ${Array.isArray(payload) ? payload.length : 0} 个计划。`
                  );
                });
                clearSelectionBtn.addEventListener("click", () => {
                  state.selectedCandidateId = "";
                  persist();
                  loadPageData();
                });

                statusFilterEl.addEventListener("change", () => {
                  state.status = statusFilterEl.value;
                  state.selectedCandidateId = "";
                  persist();
                  loadPageData({ autoSelect: true });
                });
                pillarFilterEl.addEventListener("change", () => {
                  state.pillar = pillarFilterEl.value;
                  state.selectedCandidateId = "";
                  persist();
                  loadPageData({ autoSelect: true });
                });
                limitFilterEl.addEventListener("change", () => {
                  state.limit = limitFilterEl.value;
                  persist();
                  loadPageData({ autoSelect: true });
                });

                document.addEventListener("click", (event) => {
                  const runSourceBtn = event.target.closest("[data-run-source]");
                  if (runSourceBtn) {
                    const sourceId = runSourceBtn.getAttribute("data-run-source");
                    runAction(
                      runSourceBtn,
                      `/admin/api/topics/sources/${encodeURIComponent(sourceId)}/run`,
                      undefined,
                      (payload) => `来源已运行：新增 ${payload.new_signal_count} 条信号，更新 ${payload.candidate_count} 个候选。`
                    );
                    return;
                  }

                  const enqueueSourceBtn = event.target.closest("[data-enqueue-source]");
                  if (enqueueSourceBtn) {
                    const sourceId = enqueueSourceBtn.getAttribute("data-enqueue-source");
                    runAction(
                      enqueueSourceBtn,
                      `/admin/api/topics/sources/${encodeURIComponent(sourceId)}/enqueue`,
                      undefined,
                      (payload) => payload.enqueued
                        ? `来源已入队，当前队列深度 ${payload.queue_depth}。`
                        : `来源已在队列中，当前队列深度 ${payload.queue_depth}。`
                    );
                    return;
                  }

                  const selectCandidateBtn = event.target.closest("[data-select-candidate]");
                  if (selectCandidateBtn) {
                    state.selectedCandidateId = selectCandidateBtn.getAttribute("data-select-candidate") || "";
                    persist();
                    loadPageData();
                    return;
                  }

                  const promoteBtn = event.target.closest("#topic-promote-action");
                  if (promoteBtn) {
                    const planId = promoteBtn.getAttribute("data-plan-id");
                    if (!planId) {
                      setStatus("当前没有可推进的计划。", "warn");
                      return;
                    }
                    const operatorInput = document.getElementById("topic-promote-operator");
                    const noteInput = document.getElementById("topic-promote-note");
                    const enqueueCheckbox = document.getElementById("topic-promote-enqueue-phase3");
                    state.operator = operatorInput?.value.trim() || "admin-topics";
                    state.note = noteInput?.value.trim() || "";
                    state.enqueuePhase3 = Boolean(enqueueCheckbox?.checked);
                    persist();
                    runAction(
                      promoteBtn,
                      `/admin/api/topics/plans/${encodeURIComponent(planId)}/promote`,
                      {
                        operator: state.operator,
                        note: state.note || null,
                        enqueue_phase3: state.enqueuePhase3
                      },
                      (payload) => `计划已推进到任务 ${payload.task_code}，状态 ${payload.status}。`
                    ).then(() => {
                      if (state.status === "planned") {
                        state.selectedCandidateId = "";
                        persist();
                      }
                    });
                  }
                });

                document.addEventListener("input", (event) => {
                  if (event.target?.id === "topic-promote-operator") {
                    state.operator = event.target.value;
                    persist();
                  }
                  if (event.target?.id === "topic-promote-note") {
                    state.note = event.target.value;
                    persist();
                  }
                });

                document.addEventListener("change", (event) => {
                  if (event.target?.id === "topic-promote-enqueue-phase3") {
                    state.enqueuePhase3 = Boolean(event.target.checked);
                    persist();
                  }
                });
              };

              const init = () => {
                statusFilterEl.value = state.status;
                pillarFilterEl.value = state.pillar;
                limitFilterEl.value = state.limit;
                persist();
                bindEvents();
                loadPageData({ autoSelect: true });
              };

              init();
            })();
          </script>
        </body>
        </html>
        """
    ).replace("__TOPICS_OVERVIEW__", overview_html)

    return render_admin_page(html, "topics")
