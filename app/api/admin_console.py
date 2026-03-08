from __future__ import annotations

from textwrap import dedent

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from app.core.security import verify_admin_basic_auth


router = APIRouter()


@router.get("/admin", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def unified_admin_portal(view: str = Query(default="monitor")) -> str:
    initial_view = view if view in {"monitor", "review", "feedback"} else "monitor"
    return dedent(
        f"""\
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>统一后台入口</title>
          <style>
            :root {{
              --bg: #f0e9de;
              --panel: rgba(255, 251, 246, 0.94);
              --line: #d4c2ad;
              --text: #221a11;
              --muted: #6d6256;
              --accent: #255d52;
              --accent-dark: #173f38;
              --shadow: 0 18px 48px rgba(55, 40, 21, 0.1);
            }}
            * {{ box-sizing: border-box; }}
            body {{
              margin: 0;
              min-height: 100vh;
              color: var(--text);
              font-family: "PingFang SC", "Noto Serif SC", serif;
              background:
                radial-gradient(circle at top left, rgba(255, 229, 175, 0.45), transparent 26%),
                radial-gradient(circle at bottom right, rgba(178, 222, 208, 0.38), transparent 28%),
                linear-gradient(140deg, #efe8dd 0%, #f6f2ea 44%, #ebe1d2 100%);
            }}
            main {{
              max-width: 1480px;
              margin: 0 auto;
              padding: 24px 18px 28px;
              display: grid;
              gap: 16px;
            }}
            .hero {{
              display: grid;
              gap: 10px;
            }}
            .eyebrow {{
              display: inline-flex;
              width: fit-content;
              padding: 6px 10px;
              border-radius: 999px;
              background: rgba(37, 93, 82, 0.12);
              color: var(--accent-dark);
              font-size: 12px;
              letter-spacing: 0.08em;
            }}
            h1 {{
              margin: 0;
              font-size: 38px;
              line-height: 1.05;
            }}
            .hero p {{
              margin: 0;
              max-width: 920px;
              color: var(--muted);
              line-height: 1.72;
            }}
            .panel {{
              background: var(--panel);
              border: 1px solid var(--line);
              border-radius: 22px;
              padding: 16px;
              box-shadow: var(--shadow);
              backdrop-filter: blur(8px);
            }}
            .tabs {{
              display: flex;
              flex-wrap: wrap;
              gap: 10px;
              margin-bottom: 10px;
            }}
            .tab {{
              border: none;
              border-radius: 999px;
              padding: 10px 16px;
              font: inherit;
              cursor: pointer;
              background: #e6d7bf;
              color: #2c241a;
            }}
            .tab.active {{
              background: var(--accent);
              color: #f8fbf7;
            }}
            .meta {{
              display: flex;
              flex-wrap: wrap;
              gap: 10px;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }}
            .meta a {{
              color: var(--accent-dark);
              text-decoration: none;
              border-bottom: 1px solid rgba(23, 63, 56, 0.25);
            }}
            iframe {{
              width: 100%;
              min-height: calc(100vh - 260px);
              border: 1px solid var(--line);
              border-radius: 18px;
              background: #fffdf9;
            }}
            @media (max-width: 720px) {{
              h1 {{ font-size: 30px; }}
              iframe {{ min-height: calc(100vh - 220px); }}
            }}
          </style>
        </head>
        <body>
          <main>
            <section class="hero">
              <span class="eyebrow">UNIFIED ADMIN ENTRY</span>
              <h1>统一后台入口</h1>
              <p>以后只需要记一个链接：`/admin`。监控、审核、反馈仍然分成三个视图，但统一放在这个入口里切换。旧链接继续保留兼容，不需要立刻删除。</p>
            </section>

            <section class="panel">
              <div class="tabs">
                <button class="tab" data-view="monitor">监控首页</button>
                <button class="tab" data-view="review">审核台</button>
                <button class="tab" data-view="feedback">反馈台</button>
              </div>
              <div class="meta">
                <span id="view-desc">当前视图：监控首页</span>
                <a id="open-direct" href="/admin/console" target="_blank" rel="noreferrer">新窗口打开当前视图</a>
              </div>
              <iframe id="frame" title="统一后台视图" src="/admin/console"></iframe>
            </section>
          </main>

          <script>
            const VIEWS = {{
              monitor: {{
                label: "监控首页",
                desc: "任务进度、自动轮询、历史筛选和聚合详情",
                src: "/admin/console",
              }},
              review: {{
                label: "审核台",
                desc: "人工通过 / 驳回、推草稿开关和手动推稿",
                src: "/admin/phase5",
              }},
              feedback: {{
                label: "反馈台",
                desc: "反馈导入、Prompt 实验榜和风格资产",
                src: "/admin/phase6",
              }},
            }};

            const frameEl = document.getElementById("frame");
            const descEl = document.getElementById("view-desc");
            const openDirectEl = document.getElementById("open-direct");
            const buttons = Array.from(document.querySelectorAll(".tab"));
            let currentView = "{initial_view}";

            const renderView = (view) => {{
              const config = VIEWS[view] || VIEWS.monitor;
              currentView = view in VIEWS ? view : "monitor";
              frameEl.src = config.src;
              descEl.textContent = `当前视图：${{config.label}} · ${{config.desc}}`;
              openDirectEl.href = config.src;
              buttons.forEach((button) => {{
                button.classList.toggle("active", button.dataset.view === currentView);
              }});
              const url = new URL(window.location.href);
              url.searchParams.set("view", currentView);
              window.history.replaceState({{}}, "", url);
            }};

            buttons.forEach((button) => {{
              button.addEventListener("click", () => renderView(button.dataset.view));
            }});

            renderView(currentView);
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
          <title>Phase 7A 统一控制台</title>
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
              <span class="eyebrow">PHASE 7A UNIFIED CONSOLE</span>
              <h1>统一任务监控首页</h1>
              <p>这一页只负责监控和检索，不替代 Phase 5 审核台或 Phase 6 反馈台。目标是让你在一页内看到任务实时进度、状态分组、历史筛选和聚合详情，再决定是否跳到更深的后台页处理。</p>
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
                      <span>自动轮询任务列表和当前选中任务</span>
                    </div>
                  </div>
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
                    <div class="metric-card"><strong>总任务</strong><span>0</span></div>
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
            const workspaceEl = document.getElementById("workspace");
            const statusEl = document.getElementById("status");
            const outputEl = document.getElementById("output");

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

            const buildTaskQuery = () => {
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
              return params.toString();
            };

            const renderMetrics = (tasks) => {
              const total = tasks.length;
              const active = tasks.filter((item) => !String(item.status).endsWith("_failed") && item.status !== "draft_saved").length;
              const manual = tasks.filter((item) => ["needs_manual_review", "needs_regenerate", "needs_manual_source"].includes(item.status)).length;
              const draftSaved = tasks.filter((item) => item.status === "draft_saved").length;
              const failed = tasks.filter((item) => String(item.status).endsWith("_failed")).length;
              const updated = tasks.length ? formatDate(tasks[0].updated_at) : "暂无";
              metricsEl.innerHTML = `
                <div class="metric-card"><strong>当前列表</strong><span>${escapeHtml(total)}</span></div>
                <div class="metric-card"><strong>待处理</strong><span>${escapeHtml(active)}</span></div>
                <div class="metric-card"><strong>待人工</strong><span>${escapeHtml(manual)}</span></div>
                <div class="metric-card"><strong>已入草稿</strong><span>${escapeHtml(draftSaved)}</span></div>
                <div class="metric-card"><strong>失败任务</strong><span>${escapeHtml(failed)}</span></div>
                <div class="metric-card"><strong>最近更新</strong><span style="font-size:16px; line-height:1.35;">${escapeHtml(updated)}</span></div>
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

            const refreshAll = async () => {
              saveDraft();
              setStatus("刷新中");
              const tasks = await request(`/api/v1/tasks?${buildTaskQuery()}`);
              renderMetrics(tasks);
              renderBoard(tasks);
              if (selectedTaskId) {
                const workspace = await request(`/api/v1/tasks/${selectedTaskId}/workspace`);
                renderWorkspace(workspace);
              }
              renderOutput(tasks);
              setStatus(`已刷新 · ${tasks.length} 个任务`);
            };

            const refreshWorkspace = async (taskId) => {
              selectedTaskId = taskId;
              saveDraft();
              setStatus("加载详情中");
              const workspace = await request(`/api/v1/tasks/${taskId}/workspace`);
              renderWorkspace(workspace);
              renderOutput(workspace);
              setStatus(`已加载 · ${workspace.status}`);
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
            });

            [tokenEl, pollSecondsEl, limitEl, autoRefreshEl, statusFilterEl, sourceFilterEl, queryFilterEl, createdAfterEl, activeOnlyEl].forEach((element) => {
              const eventName = element === queryFilterEl ? "input" : "change";
              element.addEventListener(eventName, () => {
                saveDraft();
                restartTimer();
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
            restartTimer();
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
