from __future__ import annotations

from textwrap import dedent

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.api.admin_ui import admin_section_nav, admin_section_nav_styles
from app.core.security import verify_admin_basic_auth


router = APIRouter()


@router.get("/admin/phase2", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def phase2_console() -> str:
    return dedent(
        """\
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>Phase 2 手动触发台</title>
          <style>
            :root {
              --bg: #f5f1e8;
              --panel: #fffaf0;
              --line: #d3c6a6;
              --text: #2a2418;
              --muted: #6b624e;
              --accent: #986b2f;
              --accent-dark: #6f4d22;
              --danger: #9c2f1e;
            }
            * { box-sizing: border-box; }
            body {
              margin: 0;
              font-family: "PingFang SC", "Noto Serif SC", serif;
              color: var(--text);
              background:
                radial-gradient(circle at top left, #fff6d6 0%, transparent 28%),
                linear-gradient(135deg, #efe6d5 0%, #f6f2ea 45%, #ece4d3 100%);
              min-height: 100vh;
            }
            main {
              max-width: 980px;
              margin: 0 auto;
              padding: 32px 20px 48px;
            }
            .hero {
              margin-bottom: 20px;
            }
            .hero h1 {
              margin: 0 0 8px;
              font-size: 36px;
              line-height: 1.05;
              letter-spacing: 0.02em;
            }
            .hero p {
              margin: 0;
              color: var(--muted);
              max-width: 680px;
              line-height: 1.7;
            }
            .panel {
              background: rgba(255, 250, 240, 0.9);
              border: 1px solid var(--line);
              border-radius: 20px;
              padding: 20px;
              box-shadow: 0 18px 40px rgba(70, 52, 20, 0.08);
              backdrop-filter: blur(6px);
              margin-bottom: 18px;
            }
            .panel h2 {
              margin: 0 0 14px;
              font-size: 18px;
            }
            .grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
              gap: 14px;
            }
            label {
              display: block;
              font-size: 13px;
              color: var(--muted);
              margin-bottom: 6px;
            }
            input, textarea, button {
              width: 100%;
              border-radius: 12px;
              border: 1px solid var(--line);
              font: inherit;
            }
            input, textarea {
              padding: 12px 14px;
              background: #fffdf8;
              color: var(--text);
            }
            textarea {
              min-height: 140px;
              resize: vertical;
            }
            .actions {
              display: flex;
              flex-wrap: wrap;
              gap: 10px;
              margin-top: 14px;
            }
            button {
              width: auto;
              min-width: 170px;
              padding: 12px 18px;
              cursor: pointer;
              background: var(--accent);
              color: #fff7eb;
              border: none;
              transition: transform 0.12s ease, background 0.12s ease;
            }
            button:hover { background: var(--accent-dark); transform: translateY(-1px); }
            button.secondary { background: #cab992; color: #2a2418; }
            button.danger { background: var(--danger); }
            .status {
              display: inline-block;
              padding: 6px 10px;
              border-radius: 999px;
              background: #f0e1bb;
              color: #65431a;
              font-size: 12px;
              margin-bottom: 12px;
            }
            pre {
              margin: 0;
              white-space: pre-wrap;
              word-break: break-word;
              background: #2f261a;
              color: #f9f2de;
              padding: 16px;
              border-radius: 14px;
              min-height: 240px;
              line-height: 1.6;
              overflow: auto;
            }
            .hint {
              font-size: 13px;
              color: var(--muted);
              line-height: 1.7;
            }
            .recent-list {
              display: grid;
              gap: 12px;
            }
            .recent-card {
              border: 1px solid var(--line);
              border-radius: 16px;
              padding: 14px;
              background: #fffdf8;
            }
            .recent-card h3 {
              margin: 0 0 8px;
              font-size: 16px;
            }
            .recent-meta {
              display: grid;
              gap: 4px;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.6;
            }
            .recent-actions {
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
              margin-top: 12px;
            }
            .recent-actions button {
              min-width: 132px;
            }
            @media (max-width: 720px) {
              .hero h1 { font-size: 28px; }
              .actions { flex-direction: column; }
              .recent-actions { flex-direction: column; }
              button { width: 100%; }
            }
          </style>
        </head>
        <body>
          <main>
            <section class="hero">
              <h1>Phase 2 手动触发台</h1>
              <p>这个页面只做联调和人工补触发。真正的写权限仍然由 Bearer Token 控制，页面本身不内置任何服务端密钥。</p>
            </section>

            <section class="panel">
              <h2>认证与输入</h2>
              <div class="grid">
                <div>
                  <label for="token">Bearer Token</label>
                  <input id="token" type="password" placeholder="输入 API_BEARER_TOKEN" />
                </div>
                <div>
                  <label for="device">device_id</label>
                  <input id="device" type="text" value="admin-console" />
                </div>
              </div>
              <div style="margin-top: 14px;">
                <label for="url">微信文章链接</label>
                <input id="url" type="url" placeholder="https://mp.weixin.qq.com/s/..." />
              </div>
              <div style="margin-top: 14px;">
                <label for="task">已有 task_id</label>
                <input id="task" type="text" placeholder="d7b573d9-..." />
              </div>
              <div class="actions">
                <button id="queue-new">提交链接并入队</button>
                <button id="run-new">提交链接并执行阶段2</button>
                <button id="queue-task" class="secondary">将已有 Task 入队</button>
                <button id="run-task" class="secondary">执行已有 Task</button>
                <button id="query-task" class="secondary">查询 Task 状态</button>
                <button id="clear" class="danger">清空输出</button>
              </div>
              <p class="hint">建议流程：联调用同步执行，日常补触发用“提交链接并入队”。如果之前已经创建过任务，也可以直接填 task_id 运行、入队或查询。</p>
            </section>

            <section class="panel">
              <h2>最近任务</h2>
              <div class="actions" style="margin-top: 0;">
                <button id="refresh-recent" class="secondary">刷新最近任务</button>
              </div>
              <p class="hint">最近任务会显示标题、状态、草稿 `media_id` 和创建时间。点击卡片按钮可直接填入 `task_id`、查询或重跑。</p>
              <div class="recent-list" id="recent-list">
                <div class="hint">等待加载最近任务...</div>
              </div>
            </section>

            <section class="panel">
              <span class="status" id="status">空闲</span>
              <pre id="output">等待输入...</pre>
            </section>
          </main>

          <script>
            const tokenEl = document.getElementById("token");
            const urlEl = document.getElementById("url");
            const taskEl = document.getElementById("task");
            const reviewNoteEl = document.getElementById("review-note");
            const deviceEl = document.getElementById("device");
            const outputEl = document.getElementById("output");
            const statusEl = document.getElementById("status");
            const recentListEl = document.getElementById("recent-list");

            const loadDraft = () => {
              tokenEl.value = localStorage.getItem("phase2_console_token") || "";
              urlEl.value = localStorage.getItem("phase2_console_url") || "";
              taskEl.value = localStorage.getItem("phase2_console_task") || "";
            };

            const saveDraft = () => {
              localStorage.setItem("phase2_console_token", tokenEl.value.trim());
              localStorage.setItem("phase2_console_url", urlEl.value.trim());
              localStorage.setItem("phase2_console_task", taskEl.value.trim());
            };

            const setStatus = (text) => { statusEl.textContent = text; };
            const render = (value) => {
              outputEl.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
            };
            const escapeHtml = (value) => String(value ?? "")
              .replaceAll("&", "&amp;")
              .replaceAll("<", "&lt;")
              .replaceAll(">", "&gt;")
              .replaceAll('"', "&quot;");
            const formatDate = (value) => {
              if (!value) return "未知";
              const date = new Date(value);
              if (Number.isNaN(date.getTime())) return String(value);
              return date.toLocaleString("zh-CN", { hour12: false });
            };
            const apiUrl = (path) => new URL(path, window.location.origin).toString();

            const request = async (method, path, body) => {
              const token = tokenEl.value.trim();
              if (!token) throw new Error("缺少 Bearer Token");
              const response = await fetch(apiUrl(path), {
                method,
                headers: {
                  "Authorization": `Bearer ${token}`,
                  "Content-Type": "application/json"
                },
                body: body ? JSON.stringify(body) : undefined
              });
              const text = await response.text();
              let payload = text;
              try { payload = JSON.parse(text); } catch (_) {}
              if (!response.ok) {
                throw new Error(typeof payload === "string" ? payload : JSON.stringify(payload, null, 2));
              }
              return payload;
            };

            const renderRecent = (items) => {
              if (!Array.isArray(items) || items.length === 0) {
                recentListEl.innerHTML = '<div class="hint">暂无任务记录。</div>';
                return;
              }

              recentListEl.innerHTML = items.map((item) => `
                <article class="recent-card">
                  <h3>${escapeHtml(item.title || item.source_url || item.task_code)}</h3>
                  <div class="recent-meta">
                    <div>task_id: ${escapeHtml(item.task_id)}</div>
                    <div>task_code: ${escapeHtml(item.task_code)}</div>
                    <div>状态: ${escapeHtml(item.status)} / 进度 ${escapeHtml(item.progress)}%</div>
                    <div>媒体ID: ${escapeHtml(item.wechat_media_id || "-")}</div>
                    <div>创建时间: ${escapeHtml(formatDate(item.created_at))}</div>
                  </div>
                  <div class="recent-actions">
                    <button class="secondary" data-action="fill" data-task-id="${escapeHtml(item.task_id)}">填入 task_id</button>
                    <button class="secondary" data-action="query" data-task-id="${escapeHtml(item.task_id)}">查询</button>
                    <button class="secondary" data-action="queue" data-task-id="${escapeHtml(item.task_id)}">入队</button>
                    <button data-action="run" data-task-id="${escapeHtml(item.task_id)}">同步执行</button>
                  </div>
                </article>
              `).join("");
            };

            const refreshRecent = async () => {
              const tasks = await request("GET", "/api/v1/tasks?limit=10");
              renderRecent(tasks);
              return tasks;
            };

            const ingestPayload = () => ({
              url: urlEl.value.trim(),
              source: "admin-console",
              device_id: deviceEl.value.trim() || "admin-console",
              trigger: "manual-ui",
              dispatch_mode: "ingest_only"
            });

            const setTaskId = (taskId) => {
              taskEl.value = taskId;
              localStorage.setItem("phase2_console_task", taskId);
            };

            const enqueueExistingTask = async (taskId) => {
              setStatus("入队中");
              const queued = await request("POST", `/internal/v1/tasks/${taskId}/enqueue-phase2`);
              setStatus(queued.enqueued ? "已入队" : "已在队列中");
              render(queued);
              await refreshRecent();
              return queued;
            };

            document.getElementById("queue-new").addEventListener("click", async () => {
              try {
                saveDraft();
                const url = urlEl.value.trim();
                if (!url) throw new Error("请先输入微信文章链接");
                setStatus("创建任务中");
                const ingest = await request("POST", "/api/v1/ingest/link", ingestPayload());
                setTaskId(ingest.task_id);
                const queued = await enqueueExistingTask(ingest.task_id);
                render({ ingest, queued });
              } catch (error) {
                setStatus("失败");
                render(error.message || String(error));
              }
            });

            document.getElementById("run-new").addEventListener("click", async () => {
              try {
                saveDraft();
                const url = urlEl.value.trim();
                if (!url) throw new Error("请先输入微信文章链接");
                setStatus("创建任务中");
                const ingest = await request("POST", "/api/v1/ingest/link", ingestPayload());
                setTaskId(ingest.task_id);
                setStatus("执行阶段2中");
                const run = await request("POST", `/internal/v1/tasks/${ingest.task_id}/run-phase2`);
                setStatus(run.status || "完成");
                render({ ingest, run });
                await refreshRecent();
              } catch (error) {
                setStatus("失败");
                render(error.message || String(error));
              }
            });

            document.getElementById("queue-task").addEventListener("click", async () => {
              try {
                saveDraft();
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                await enqueueExistingTask(taskId);
              } catch (error) {
                setStatus("失败");
                render(error.message || String(error));
              }
            });

            document.getElementById("run-task").addEventListener("click", async () => {
              try {
                saveDraft();
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("执行阶段2中");
                const run = await request("POST", `/internal/v1/tasks/${taskId}/run-phase2`);
                setStatus(run.status || "完成");
                render(run);
                await refreshRecent();
              } catch (error) {
                setStatus("失败");
                render(error.message || String(error));
              }
            });

            document.getElementById("query-task").addEventListener("click", async () => {
              try {
                saveDraft();
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("查询中");
                const task = await request("GET", `/api/v1/tasks/${taskId}`);
                setStatus(task.status || "完成");
                render(task);
              } catch (error) {
                setStatus("失败");
                render(error.message || String(error));
              }
            });

            document.getElementById("clear").addEventListener("click", () => {
              setStatus("空闲");
              render("等待输入...");
            });

            document.getElementById("refresh-recent").addEventListener("click", async () => {
              try {
                saveDraft();
                setStatus("刷新列表中");
                await refreshRecent();
                setStatus("空闲");
              } catch (error) {
                setStatus("失败");
                render(error.message || String(error));
              }
            });

            recentListEl.addEventListener("click", async (event) => {
              const button = event.target.closest("button[data-action]");
              if (!button) return;
              const taskId = button.getAttribute("data-task-id");
              const action = button.getAttribute("data-action");
              if (!taskId || !action) return;

              try {
                saveDraft();
                setTaskId(taskId);
                if (action === "fill") {
                  setStatus("已填入");
                  render(`已填入 task_id: ${taskId}`);
                  return;
                }
                if (action === "query") {
                  setStatus("查询中");
                  const task = await request("GET", `/api/v1/tasks/${taskId}`);
                  setStatus(task.status || "完成");
                  render(task);
                  return;
                }
                if (action === "queue") {
                  await enqueueExistingTask(taskId);
                  return;
                }
                if (action === "run") {
                  setStatus("执行阶段2中");
                  const run = await request("POST", `/internal/v1/tasks/${taskId}/run-phase2`);
                  setStatus(run.status || "完成");
                  render(run);
                  await refreshRecent();
                }
              } catch (error) {
                setStatus("失败");
                render(error.message || String(error));
              }
            });

            loadDraft();
            if (tokenEl.value.trim()) {
              refreshRecent().catch(() => {
                recentListEl.innerHTML = '<div class="hint">最近任务加载失败，请确认 Bearer Token 后手动刷新。</div>';
              });
            } else {
              recentListEl.innerHTML = '<div class="hint">先输入 Bearer Token，再点“刷新最近任务”。</div>';
            }
          </script>
        </body>
        </html>
        """
    )


@router.get("/admin/phase5", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def phase5_console() -> str:
    html = dedent(
        """\
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>Phase 5 工作台</title>
          <style>
            :root {
              --bg: #f4efe6;
              --panel: rgba(255, 250, 242, 0.92);
              --line: #d4c2aa;
              --text: #241d14;
              --muted: #6a5e50;
              --accent: #1d6a5f;
              --accent-dark: #12483f;
              --danger: #9d3a2e;
              --warn: #ba7d1c;
              --ok: #2d7b4f;
              --shadow: 0 18px 48px rgba(63, 47, 25, 0.1);
            }
            * { box-sizing: border-box; }
            body {
              margin: 0;
              line-height: 1.5;
              font-family: "PingFang SC", "Noto Serif SC", serif;
              color: var(--text);
              background:
                radial-gradient(circle at top left, rgba(255, 233, 191, 0.55), transparent 24%),
                radial-gradient(circle at bottom right, rgba(182, 224, 209, 0.45), transparent 28%),
                linear-gradient(140deg, #f0e8db 0%, #f7f3eb 42%, #ece4d7 100%);
              min-height: 100vh;
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
              max-width: 1280px;
              margin: 0 auto;
              padding: 32px 20px 52px;
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
              background: rgba(29, 106, 95, 0.12);
              color: var(--accent-dark);
              font-size: 12px;
              letter-spacing: 0.08em;
            }
            .hero h1 {
              margin: 0;
              font-size: 42px;
              line-height: 1.04;
              letter-spacing: 0.01em;
            }
            .hero p {
              margin: 0;
              color: var(--muted);
              max-width: 820px;
              line-height: 1.75;
            }
            .hero-status-card {
              display: grid;
              gap: 14px;
              padding: 18px;
              border-radius: 24px;
              border: 1px solid rgba(29, 106, 95, 0.12);
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
              background: linear-gradient(135deg, rgba(29, 106, 95, 0.1), rgba(255, 249, 242, 0.95));
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
              background: linear-gradient(135deg, rgba(29, 106, 95, 0.1), rgba(255, 249, 242, 0.96));
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
            .grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
              gap: 12px;
            }
            .grid.single {
              grid-template-columns: 1fr;
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
            input, textarea, button {
              width: 100%;
              font: inherit;
              border-radius: 14px;
            }
            input, textarea {
              padding: 12px 14px;
              background: #fffdf9;
              color: var(--text);
              border: 1px solid var(--line);
            }
            input:focus-visible,
            textarea:focus-visible,
            button:focus-visible,
            select:focus-visible,
            a:focus-visible,
            summary:focus-visible {
              outline: 2px solid rgba(29, 106, 95, 0.18);
              outline-offset: 3px;
            }
            textarea {
              min-height: 120px;
              resize: vertical;
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
              color: #2a2219;
            }
            button.warn {
              background: var(--warn);
              color: #fff8e8;
            }
            button.danger {
              background: var(--danger);
            }
            button[aria-busy="true"] {
              opacity: 0.82;
              cursor: progress;
            }
            .actions {
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: 10px;
              margin-top: 14px;
            }
            .action-blocks {
              display: grid;
              gap: 10px;
              margin-top: 14px;
            }
            .action-block {
              border: 1px solid var(--line);
              border-radius: 18px;
              padding: 12px;
              background: rgba(255, 253, 249, 0.84);
            }
            .action-block h3 {
              margin: 0 0 10px;
              font-size: 13px;
              color: var(--muted);
            }
            .action-grid {
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: 10px;
            }
            .action-grid button {
              width: 100%;
            }
            .status {
              display: inline-flex;
              padding: 7px 12px;
              border-radius: 999px;
              background: rgba(29, 106, 95, 0.12);
              color: var(--accent-dark);
              font-size: 12px;
              margin-bottom: 12px;
            }
            .status.warn {
              background: rgba(186, 125, 28, 0.16);
              color: #8a5c10;
            }
            .hint, .meta {
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }
            .board {
              display: grid;
              align-content: start;
              grid-auto-rows: max-content;
              gap: 12px;
            }
            .filter-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
              gap: 10px;
              margin-bottom: 12px;
            }
            .filter-grid select {
              width: 100%;
              padding: 12px 14px;
              border-radius: 14px;
              border: 1px solid var(--line);
              background: #fffdf9;
              color: var(--text);
              font: inherit;
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
              color: var(--text);
            }
            .check-row input {
              width: auto;
              margin: 0;
            }
            .summary-strip {
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
              margin-bottom: 12px;
            }
            .board[aria-busy="true"], .workspace[aria-busy="true"] {
              opacity: 0.82;
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
              margin-top: 2px;
            }
            .group-title h3 {
              margin: 0;
              font-size: 15px;
            }
            .group-title span {
              font-size: 12px;
              color: var(--muted);
            }
            .task-card, .detail-card, .generation-card, .audit-card {
              background: #fffdf9;
              border: 1px solid var(--line);
              border-radius: 18px;
              padding: 14px;
              display: grid;
              align-content: start;
              gap: 8px;
              min-width: 0;
              position: relative;
              isolation: isolate;
            }
            .task-card h3, .detail-card h3, .generation-card h3 {
              margin: 0 0 8px;
              font-size: 16px;
              line-height: 1.45;
              overflow-wrap: anywhere;
            }
            .task-card .meta, .detail-card .meta {
              display: grid;
              gap: 4px;
              overflow-wrap: anywhere;
            }
            .task-actions {
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
              margin-top: 12px;
            }
            .task-actions button {
              width: auto;
              min-width: 110px;
            }
            .workspace {
              display: grid;
              gap: 16px;
            }
            .summary-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
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
            .generation-list, .audit-list {
              display: grid;
              align-content: start;
              grid-auto-rows: max-content;
              gap: 12px;
            }
            .compare-toolbar {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
              gap: 10px;
              margin-bottom: 14px;
            }
            .compare-toolbar select {
              width: 100%;
              padding: 12px 14px;
              border-radius: 14px;
              border: 1px solid var(--line);
              background: #fffdf9;
              color: var(--text);
              font: inherit;
            }
            .diff-summary {
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
              margin-bottom: 10px;
            }
            .diff-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
              gap: 10px;
              margin-bottom: 10px;
            }
            .diff-card {
              background: #fffdf8;
              border: 1px solid var(--line);
              border-radius: 16px;
              padding: 12px;
            }
            .diff-card strong {
              display: block;
              margin-bottom: 6px;
              font-size: 12px;
              color: var(--muted);
              font-weight: 500;
            }
            .diff-card .before {
              color: #7c3427;
            }
            .diff-card .after {
              color: #1f6942;
            }
            .diff-pre {
              margin-top: 0;
            }
            .diff-line {
              display: block;
              padding: 1px 0;
            }
            .diff-line.add {
              color: #d8f7df;
              background: rgba(45, 123, 79, 0.28);
            }
            .diff-line.remove {
              color: #ffe3dc;
              background: rgba(157, 58, 46, 0.28);
            }
            .diff-line.same {
              color: #f7f1df;
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
            .generation-header {
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
              align-items: center;
              margin-bottom: 8px;
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
              background: rgba(45, 123, 79, 0.12);
              color: var(--ok);
            }
            .pill.warn {
              background: rgba(186, 125, 28, 0.12);
              color: #8a5c10;
            }
            .pill.danger {
              background: rgba(157, 58, 46, 0.12);
              color: var(--danger);
            }
            details {
              margin-top: 10px;
            }
            details summary {
              cursor: pointer;
              color: var(--accent-dark);
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
            .audit-card {
              display: grid;
              gap: 6px;
            }
            .link-row {
              display: flex;
              flex-wrap: wrap;
              gap: 10px;
              margin-top: 6px;
            }
            .link-row a {
              color: var(--accent-dark);
              text-decoration: none;
              border-bottom: 1px solid rgba(18, 72, 63, 0.25);
            }
            .fold {
              border: 1px dashed var(--line);
              border-radius: 16px;
              padding: 12px 14px;
              background: rgba(255, 253, 249, 0.7);
            }
            .fold summary {
              cursor: pointer;
              color: var(--muted);
              font-size: 13px;
            }
            .fold .meta {
              margin-top: 10px;
            }
            __ADMIN_NAV_STYLES__
            @media (max-width: 1024px) {
              .hero-grid {
                grid-template-columns: 1fr;
              }
              .overview-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
              }
              .layout {
                grid-template-columns: 1fr;
              }
            }
            @media (max-width: 720px) {
              main { padding: 22px 14px 36px; }
              .hero { padding: 18px; }
              .panel { padding: 16px; border-radius: 20px; }
              .hero h1 { font-size: 30px; }
              .hero-summary { grid-template-columns: 1fr; }
              .overview-strip { grid-template-columns: 1fr; }
              .overview-card.highlight { grid-column: span 1; }
              .actions { grid-template-columns: 1fr; }
              .action-grid { grid-template-columns: 1fr; }
              .task-actions { flex-direction: column; }
              .task-actions button { width: 100%; }
            }
          </style>
        </head>
        <body>
          <a class="skip-link" href="#review-region">跳到审核主区</a>
          <main>
            __ADMIN_SECTION_NAV__
            <section class="hero">
              <div class="hero-grid">
                <div class="hero-copy">
                  <span class="eyebrow">PHASE 5 ADMIN CONSOLE</span>
                  <h1>审核台</h1>
                  <p>先看任务，再决定：通过、重写，还是推草稿。</p>
                </div>
                <aside class="hero-status-card" aria-label="审核台状态">
                  <span class="status" id="status">空闲</span>
                  <p class="hero-status-copy" id="flash-message" role="status" aria-live="polite" aria-atomic="true">先刷新最近任务，再点一条卡片进入工作区。</p>
                  <div class="hero-summary" aria-label="首屏提示">
                    <div class="hero-summary-card">
                      <strong>主要流程</strong>
                      <span>先选任务，再看工作区，再决定动作。</span>
                    </div>
                    <div class="hero-summary-card">
                      <strong>人工介入点</strong>
                      <span>通过、重写、允许推稿、禁止推稿。</span>
                    </div>
                    <div class="hero-summary-card wide">
                      <strong>当前建议</strong>
                      <span id="hero-focus">先刷新最近任务，再点一条卡片进入工作区。</span>
                    </div>
                  </div>
                </aside>
              </div>
            </section>

            <section class="overview-strip" aria-label="审核概览">
              <article class="overview-card">
                <strong>可见任务</strong>
                <span id="overview-total">0</span>
                <p>当前筛选后显示在审核台里的任务数量。</p>
              </article>
              <article class="overview-card">
                <strong>等你处理</strong>
                <span id="overview-manual">0</span>
                <p>需要人工审核、重写或决定是否推稿的任务。</p>
              </article>
              <article class="overview-card">
                <strong>待推草稿</strong>
                <span id="overview-ready">0</span>
                <p>已经通过审核，下一步是决定是否推送草稿。</p>
              </article>
              <article class="overview-card">
                <strong>失败 / 异常</strong>
                <span id="overview-failed">0</span>
                <p>优先看失败任务，先判断补数据还是直接重跑。</p>
              </article>
              <article class="overview-card highlight">
                <strong>当前优先</strong>
                <span id="overview-focus">先刷新最近任务，再点一条卡片进入工作区。</span>
                <p id="overview-focus-note">右侧工作区会集中展示当前动作、草稿状态、版本差异和审计轨迹。</p>
              </article>
            </section>

            <section class="layout" id="review-region">
              <div class="stack">
                <section class="panel">
                  <h2>先选任务</h2>
                  <p class="panel-intro">默认直接复用当前后台会话。左边只负责选任务和触发动作，右边统一看工作区内容；如果长时间停留后提示未授权，刷新页面重新进入后台即可。</p>
                  <div class="grid single">
                    <div class="field">
                      <label for="device">device_id</label>
                      <input id="device" type="text" value="phase5-console" aria-describedby="device-hint" />
                    </div>
                    <p class="field-hint" id="device-hint">会写入审计日志，建议填当前值班人或具体操作来源。</p>
                    <div class="field">
                      <label for="url">微信文章链接</label>
                      <input id="url" type="url" placeholder="https://mp.weixin.qq.com/s/..." aria-describedby="url-hint" />
                    </div>
                    <p class="field-hint" id="url-hint">当你要从新链接直接开任务时再填它；已有任务优先直接填 `task_id`。</p>
                    <div class="field">
                      <label for="task">task_id</label>
                      <input id="task" type="text" placeholder="f703c3ef-..." aria-describedby="task-hint" />
                    </div>
                    <p class="field-hint" id="task-hint">刷新最近任务后，点卡片按钮会自动把 `task_id` 填到这里。</p>
                    <div class="field">
                      <label for="review-note">人工审核备注</label>
                      <textarea id="review-note" placeholder="会写入 audit log，例如：结构已达标，可人工放行；或：观点重复，退回重写。" aria-describedby="review-note-hint"></textarea>
                    </div>
                    <p class="field-hint" id="review-note-hint">备注会跟随人工通过、驳回和推稿许可一起写入审计轨迹，尽量写出决定依据。</p>
                  </div>
                  <div class="action-blocks">
                    <div class="action-block">
                      <h3>开始</h3>
                      <div class="action-grid">
                        <button id="queue-url">链接入队</button>
                        <button id="run-url">直接执行</button>
                        <button id="load-workspace" class="secondary">加载详情</button>
                        <button id="clear" class="danger">清空</button>
                      </div>
                    </div>
                    <div class="action-block">
                      <h3>继续任务</h3>
                      <div class="action-grid">
                        <button id="queue-phase3" class="secondary">入队 Phase3</button>
                        <button id="run-phase4" class="secondary">执行 P4</button>
                        <button id="queue-phase4" class="secondary">入队 Phase4</button>
                        <button id="push-draft" class="warn">推送草稿</button>
                      </div>
                    </div>
                    <div class="action-block">
                      <h3>人工处理</h3>
                      <div class="action-grid">
                        <button id="approve-generation" class="secondary">人工通过</button>
                        <button id="reject-generation" class="danger">人工驳回重写</button>
                        <button id="allow-push" class="secondary">允许推稿</button>
                        <button id="block-push" class="danger">禁止推稿</button>
                      </div>
                    </div>
                  </div>
                  <p class="hint">先加载详情，再决定：重跑、通过、驳回，或者推稿。危险动作会在工作区里给出上下文再判断。</p>
                </section>

                <section class="panel">
                  <h2>怎么用</h2>
                  <p class="panel-intro">审核台不是从左到右把所有按钮都点一遍，而是按任务状态决定下一步。</p>
                  <div class="meta">
                    <div>1. 先刷新最近任务，再点一条卡片。</div>
                    <div>2. 右边先看状态、最新一稿和风险。</div>
                    <div>3. 可用就通过，不行就驳回或重跑。</div>
                  </div>
                  <details class="fold">
                    <summary>再看完整规则</summary>
                    <div class="meta">
                      <div>研究层明显缺信息时，先入队 Phase3；Brief 已够但稿子不行时，直接重跑 Phase4。</div>
                      <div>已推草稿的版本不允许再驳回；人工审核备注会写入 audit log。</div>
                      <div>只有 latest generation 已 accepted 且推草稿许可允许时，才推微信草稿箱。</div>
                    </div>
                  </details>
                </section>

                <section class="panel">
                  <h2>任务看板</h2>
                  <p class="panel-intro">默认先把还没收口的任务放到前面。先筛“待人工审核 / 待重生成 / 待推草稿”，再看右侧工作区。</p>
                  <div class="filter-grid">
                    <div>
                      <label for="recent-status-filter">状态筛选</label>
                      <select id="recent-status-filter">
                        <option value="">全部状态</option>
                        <option value="queued">queued</option>
                        <option value="review_passed">review_passed</option>
                        <option value="needs_regenerate">needs_regenerate</option>
                        <option value="needs_manual_review">needs_manual_review</option>
                        <option value="draft_saved">draft_saved</option>
                        <option value="review_failed">review_failed</option>
                        <option value="push_failed">push_failed</option>
                      </select>
                    </div>
                    <div>
                      <label for="recent-limit">任务数量</label>
                      <input id="recent-limit" type="number" min="6" max="50" value="18" />
                    </div>
                    <div>
                      <label>队列过滤</label>
                      <div class="check-row">
                        <input id="recent-active-only" type="checkbox" checked />
                        <span>只看待处理任务</span>
                      </div>
                    </div>
                  </div>
                  <div class="actions" style="margin-top: 0;">
                    <button id="refresh-recent" class="secondary">刷新最近任务</button>
                  </div>
                  <div class="summary-strip" id="recent-summary"></div>
                  <div class="board" id="recent-list" aria-busy="false">
                    <div class="hint">等待加载最近任务...</div>
                  </div>
                </section>
              </div>

              <div class="stack">
                <section class="panel">
                  <h2>任务工作台</h2>
                  <p class="panel-intro">这里集中看当前动作、推稿许可、源文摘要、Brief、最新成稿、版本差异和审计轨迹。</p>
                  <div class="workspace" id="workspace" aria-busy="false">
                    <div class="hint">先加载 task_id 或刷新最近任务。</div>
                  </div>
                </section>

                <section class="panel">
                  <h2>接口输出</h2>
                  <pre id="output">等待输入...</pre>
                </section>
              </div>
            </section>
          </main>

          <script>
            const urlEl = document.getElementById("url");
            const taskEl = document.getElementById("task");
            const reviewNoteEl = document.getElementById("review-note");
            const deviceEl = document.getElementById("device");
            const outputEl = document.getElementById("output");
            const statusEl = document.getElementById("status");
            const flashMessageEl = document.getElementById("flash-message");
            const heroFocusEl = document.getElementById("hero-focus");
            const recentListEl = document.getElementById("recent-list");
            const recentSummaryEl = document.getElementById("recent-summary");
            const recentStatusEl = document.getElementById("recent-status-filter");
            const recentLimitEl = document.getElementById("recent-limit");
            const recentActiveEl = document.getElementById("recent-active-only");
            const workspaceEl = document.getElementById("workspace");
            const overviewTotalEl = document.getElementById("overview-total");
            const overviewManualEl = document.getElementById("overview-manual");
            const overviewReadyEl = document.getElementById("overview-ready");
            const overviewFailedEl = document.getElementById("overview-failed");
            const overviewFocusEl = document.getElementById("overview-focus");
            const overviewFocusNoteEl = document.getElementById("overview-focus-note");
            const STATUS_LABELS = {
              queued: "待执行",
              deduping: "去重中",
              fetching_source: "抓原文",
              source_ready: "原文就绪",
              analyzing_source: "分析中",
              searching_related: "搜索中",
              fetching_related: "拉素材",
              building_brief: "建 Brief",
              brief_ready: "Brief 就绪",
              generating: "生成中",
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
              needs_regenerate: "待重生成",
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
              "building_brief",
              "generating",
              "reviewing",
              "pushing_wechat_draft",
              "draft_saved",
            ];
            const WAITING_STATUSES = new Set(["needs_manual_review", "needs_regenerate"]);
            const READY_STATUSES = new Set(["review_passed"]);
            const FAILED_STATUSES = new Set([
              "fetch_failed",
              "analyze_failed",
              "search_failed",
              "brief_failed",
              "generate_failed",
              "review_failed",
              "push_failed",
              "needs_manual_source",
            ]);
            const SESSION_EXPIRED_MESSAGE = "后台会话已失效，请刷新页面重新进入后台。";

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

            const loadDraft = () => {
              urlEl.value = localStorage.getItem("phase5_console_url") || "";
              taskEl.value = localStorage.getItem("phase5_console_task") || "";
              reviewNoteEl.value = localStorage.getItem("phase5_console_review_note") || "";
              recentStatusEl.value = localStorage.getItem("phase5_console_recent_status") || "";
              recentLimitEl.value = localStorage.getItem("phase5_console_recent_limit") || "18";
              recentActiveEl.checked = (localStorage.getItem("phase5_console_recent_active_only") || "true") !== "false";
            };

            const saveDraft = () => {
              localStorage.setItem("phase5_console_url", urlEl.value.trim());
              localStorage.setItem("phase5_console_task", taskEl.value.trim());
              localStorage.setItem("phase5_console_review_note", reviewNoteEl.value.trim());
              localStorage.setItem("phase5_console_recent_status", recentStatusEl.value);
              localStorage.setItem("phase5_console_recent_limit", recentLimitEl.value);
              localStorage.setItem("phase5_console_recent_active_only", recentActiveEl.checked ? "true" : "false");
            };

            const setStatus = (text) => {
              statusEl.textContent = text;
              if (flashMessageEl) {
                flashMessageEl.textContent = text;
              }
            };
            const setPanelsBusy = (busy) => {
              recentListEl.setAttribute("aria-busy", busy ? "true" : "false");
              workspaceEl.setAttribute("aria-busy", busy ? "true" : "false");
            };
            const scrollWorkspaceIntoView = () => {
              if (!window.matchMedia("(max-width: 1024px)").matches) return;
              const panel = workspaceEl.closest(".panel");
              if (!panel) return;
              window.requestAnimationFrame(() => {
                panel.scrollIntoView({ behavior: "smooth", block: "start" });
              });
            };

            const renderOutput = (payload) => {
              if (typeof payload === "string") {
                outputEl.textContent = payload;
                return;
              }
              outputEl.textContent = JSON.stringify(payload, null, 2);
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
                setStatus("失败");
                renderOutput(error.message || String(error));
              } finally {
                setButtonBusy(button, false);
              }
            };
            const apiUrl = (path) => new URL(path, window.location.origin).toString();

            const request = async (method, path, body) => {
              saveDraft();
              const headers = {};
              if (body !== undefined) {
                headers["Content-Type"] = "application/json";
              }
              const response = await fetch(apiUrl(path), {
                method,
                headers,
                credentials: "same-origin",
                body: body === undefined ? undefined : JSON.stringify(body),
              });
              const text = await response.text();
              let data;
              try {
                data = text ? JSON.parse(text) : {};
              } catch {
                data = { raw: text };
              }
              if (!response.ok) {
                if (response.status === 401) {
                  throw new Error(SESSION_EXPIRED_MESSAGE);
                }
                throw new Error(data.detail || data.raw || `HTTP ${response.status}`);
              }
              return data;
            };

            const formatDate = (value) => value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "未知";
            const truncate = (value, limit = 220) => {
              const text = String(value || "");
              return text.length > limit ? `${text.slice(0, limit)}...` : text;
            };
            const nextStepText = (task) => {
              if (!task) return "先刷新最近任务，再点一条卡片。";
              if (task.error) return `先处理这个报错：${task.error}`;
              if (READY_STATUSES.has(task.status)) return "这条已经审过了，下一步是决定是否推草稿。";
              if (WAITING_STATUSES.has(task.status)) return "这条需要你判断是否通过还是退回重写。";
              if (FAILED_STATUSES.has(task.status)) return "这条先看错误，再决定补数据还是重跑。";
              if (task.status === "draft_saved") return "这条已经进草稿箱，可以去公众号后台检查并发布。";
              return "系统还在推进，先看右侧工作区和最新状态。";
            };
            const renderOverview = (tasks = []) => {
              const manualCount = tasks.filter((task) => WAITING_STATUSES.has(task.status)).length;
              const readyCount = tasks.filter((task) => READY_STATUSES.has(task.status)).length;
              const failedCount = tasks.filter((task) => FAILED_STATUSES.has(task.status)).length;
              let focus = "先刷新最近任务，再点一条卡片进入工作区。";
              let note = "右侧工作区会集中展示当前动作、草稿状态、版本差异和审计轨迹。";
              if (manualCount > 0) {
                focus = `先处理 ${manualCount} 条待人工判断任务`;
                note = "优先看待人工审核和待重生成任务，避免稿件停在最后一步。";
              } else if (readyCount > 0) {
                focus = `有 ${readyCount} 条任务已经待推草稿`;
                note = "先确认最新一稿和推稿许可，再决定是否推送到微信草稿箱。";
              } else if (failedCount > 0) {
                focus = `有 ${failedCount} 条异常任务需要排查`;
                note = "优先看失败任务的错误信息，再决定补源文、重跑 P3 还是重跑 P4。";
              } else if (tasks.length > 0) {
                focus = "当前列表没有卡住任务，可以按更新时间继续检查。";
                note = "先抽查最新几条任务，确认审稿结论、草稿状态和推稿许可一致。";
              }
              overviewTotalEl.textContent = String(tasks.length);
              overviewManualEl.textContent = String(manualCount);
              overviewReadyEl.textContent = String(readyCount);
              overviewFailedEl.textContent = String(failedCount);
              overviewFocusEl.textContent = focus;
              overviewFocusNoteEl.textContent = note;
              if (heroFocusEl) {
                heroFocusEl.textContent = focus;
              }
            };

            const scorePillClass = (decision) => {
              if (decision === "pass") return "pill ok";
              if (decision === "reject") return "pill danger";
              if (decision === "revise") return "pill warn";
              return "pill";
            };
            const statusLabel = (status) => STATUS_LABELS[status] || status || "未知状态";
            const pushPolicyLabel = (policy) => {
              if (!policy) return "默认允许";
              if (policy.mode === "blocked") return "已禁止推草稿";
              if (policy.mode === "allowed") return "已人工允许";
              return "默认允许";
            };
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
            const diffFieldCard = (label, before, after) => `
              <div class="diff-card">
                <strong>${escapeHtml(label)}</strong>
                <div class="meta before"><strong>旧版本</strong><span>${escapeHtml(before || "暂无")}</span></div>
                <div class="meta after" style="margin-top: 8px;"><strong>新版本</strong><span>${escapeHtml(after || "暂无")}</span></div>
              </div>
            `;
            const buildLcsMatrix = (left, right) => {
              const rows = Array.from({ length: left.length + 1 }, () => Array(right.length + 1).fill(0));
              for (let i = left.length - 1; i >= 0; i -= 1) {
                for (let j = right.length - 1; j >= 0; j -= 1) {
                  rows[i][j] = left[i] === right[j] ? rows[i + 1][j + 1] + 1 : Math.max(rows[i + 1][j], rows[i][j + 1]);
                }
              }
              return rows;
            };
            const buildLineDiff = (beforeText, afterText) => {
              const left = String(beforeText || "").split("\\n");
              const right = String(afterText || "").split("\\n");
              const matrix = buildLcsMatrix(left, right);
              const diff = [];
              let i = 0;
              let j = 0;
              while (i < left.length && j < right.length) {
                if (left[i] === right[j]) {
                  diff.push({ type: "same", text: left[i] });
                  i += 1;
                  j += 1;
                } else if (matrix[i + 1][j] >= matrix[i][j + 1]) {
                  diff.push({ type: "remove", text: left[i] });
                  i += 1;
                } else {
                  diff.push({ type: "add", text: right[j] });
                  j += 1;
                }
              }
              while (i < left.length) {
                diff.push({ type: "remove", text: left[i] });
                i += 1;
              }
              while (j < right.length) {
                diff.push({ type: "add", text: right[j] });
                j += 1;
              }
              return diff;
            };
            const renderGenerationDiff = (generations) => {
              if (!Array.isArray(generations) || generations.length < 2) {
                return `
                  <div class="detail-card">
                    <h3>版本差异视图</h3>
                    <div class="hint">至少需要两版 generation，才能比较标题、摘要和正文差异。</div>
                  </div>
                `;
              }
              const left = generations[1];
              const right = generations[0];
              const diffRows = buildLineDiff(left.markdown_content, right.markdown_content);
              const addCount = diffRows.filter((item) => item.type === "add").length;
              const removeCount = diffRows.filter((item) => item.type === "remove").length;
              return `
                <div class="detail-card">
                  <h3>版本差异视图</h3>
                  <div class="hint">默认比较最新版本和上一版本。切换版本后，会同步更新标题、摘要和正文的行级差异。</div>
                  <div class="compare-toolbar">
                    <div>
                      <label for="compare-left">旧版本</label>
                      <select id="compare-left">${generations.map((item, index) => `
                        <option value="${escapeHtml(item.generation_id)}" ${index === 1 ? "selected" : ""}>
                          v${escapeHtml(item.version_no)} · ${escapeHtml(item.review?.final_decision || item.status)}
                        </option>
                      `).join("")}</select>
                    </div>
                    <div>
                      <label for="compare-right">新版本</label>
                      <select id="compare-right">${generations.map((item, index) => `
                        <option value="${escapeHtml(item.generation_id)}" ${index === 0 ? "selected" : ""}>
                          v${escapeHtml(item.version_no)} · ${escapeHtml(item.review?.final_decision || item.status)}
                        </option>
                      `).join("")}</select>
                    </div>
                  </div>
                  <div id="diff-view"></div>
                </div>
              `;
            };
            const updateDiffView = (generations) => {
              const diffViewEl = document.getElementById("diff-view");
              const leftSelect = document.getElementById("compare-left");
              const rightSelect = document.getElementById("compare-right");
              if (!diffViewEl || !leftSelect || !rightSelect) {
                return;
              }
              const left = generations.find((item) => item.generation_id === leftSelect.value);
              const right = generations.find((item) => item.generation_id === rightSelect.value);
              if (!left || !right) {
                diffViewEl.innerHTML = '<div class="hint">请选择有效版本。</div>';
                return;
              }
              if (left.generation_id === right.generation_id) {
                diffViewEl.innerHTML = '<div class="hint">请选择两个不同的版本进行比较。</div>';
                return;
              }
              const diffRows = buildLineDiff(left.markdown_content, right.markdown_content);
              const addCount = diffRows.filter((item) => item.type === "add").length;
              const removeCount = diffRows.filter((item) => item.type === "remove").length;
              diffViewEl.innerHTML = `
                <div class="diff-summary">
                  <span class="pill">旧版本 v${escapeHtml(left.version_no)} -> 新版本 v${escapeHtml(right.version_no)}</span>
                  <span class="pill ok">新增行 ${escapeHtml(addCount)}</span>
                  <span class="pill danger">删除行 ${escapeHtml(removeCount)}</span>
                </div>
                <div class="diff-grid">
                  ${diffFieldCard("标题对比", left.title, right.title)}
                  ${diffFieldCard("摘要对比", left.digest, right.digest)}
                </div>
                <pre class="diff-pre">${diffRows.map((item) => `
<span class="diff-line ${escapeHtml(item.type)}">${escapeHtml(item.type === "add" ? "+ " : item.type === "remove" ? "- " : "  ")}${escapeHtml(item.text || "")}</span>`).join("")}
</pre>
              `;
            };

            const renderWorkspace = (workspace) => {
              const latest = workspace.generations[0];
              const latestReview = latest?.review;
              const pushPolicy = workspace.wechat_push_policy;
              const latestAiTrace = reviewAiTraceLabel(latestReview);
              const latestHumanize = reviewHumanizeLabel(latestReview);
              const latestPatternCount = reviewAiTracePatternCount(latestReview);
              workspaceEl.innerHTML = `
                <div class="summary-grid">
                  <div class="summary-item">
                    <strong>任务状态</strong>
                    <span>${escapeHtml(workspace.status)}</span>
                  </div>
                  <div class="summary-item">
                    <strong>任务进度</strong>
                    <span>${escapeHtml(workspace.progress)}%</span>
                  </div>
                  <div class="summary-item">
                    <strong>最新 generation</strong>
                    <span>${escapeHtml(workspace.generation_id || "暂无")}</span>
                  </div>
                  <div class="summary-item">
                    <strong>微信草稿 media_id</strong>
                    <span>${escapeHtml(workspace.wechat_media_id || "暂无")}</span>
                  </div>
                  <div class="summary-item">
                    <strong>推草稿许可</strong>
                    <span>${escapeHtml(pushPolicyLabel(pushPolicy))}</span>
                  </div>
                  <div class="summary-item">
                    <strong>AI 痕迹</strong>
                    <span>${escapeHtml(latestAiTrace)}</span>
                  </div>
                  <div class="summary-item">
                    <strong>定点润色</strong>
                    <span>${escapeHtml(latestHumanize)} · ${escapeHtml(latestPatternCount)} 类模式</span>
                  </div>
                  <div class="summary-item">
                    <strong>已选同题素材</strong>
                    <span>${escapeHtml(workspace.related_article_count)}</span>
                  </div>
                  <div class="summary-item">
                    <strong>最近更新时间</strong>
                    <span>${escapeHtml(formatDate(workspace.updated_at))}</span>
                  </div>
                </div>

                <div class="detail-card">
                  <h3>${escapeHtml(workspace.title || "未抓到标题")}</h3>
                  <div class="meta">
                    <div><strong>task_id</strong> ${escapeHtml(workspace.task_id)}</div>
                    <div><strong>task_code</strong> ${escapeHtml(workspace.task_code)}</div>
                    <div><strong>source_url</strong> ${escapeHtml(workspace.source_url)}</div>
                    <div><strong>错误</strong> ${escapeHtml(workspace.error || "无")}</div>
                    <div><strong>推草稿许可</strong> ${escapeHtml(pushPolicyLabel(pushPolicy))}</div>
                    <div><strong>许可备注</strong> ${escapeHtml(pushPolicy?.note || "无")}</div>
                  </div>
                  <div class="link-row">
                    <a href="${escapeHtml(workspace.source_url)}" target="_blank" rel="noreferrer">打开原文</a>
                  </div>
                </div>

                <div class="grid">
                  <div class="detail-card">
                    <h3>源文摘要</h3>
                    <div class="meta">
                      <div><strong>作者</strong> ${escapeHtml(workspace.source_article?.author || "未知")}</div>
                      <div><strong>发布时间</strong> ${escapeHtml(formatDate(workspace.source_article?.published_at))}</div>
                      <div><strong>抓取状态</strong> ${escapeHtml(workspace.source_article?.fetch_status || "未知")}</div>
                      <div><strong>摘要</strong> ${escapeHtml(workspace.source_article?.summary || "暂无")}</div>
                    </div>
                    <details>
                      <summary>展开源文节选</summary>
                      <pre>${escapeHtml(workspace.source_article?.cleaned_text_excerpt || "暂无")}</pre>
                    </details>
                  </div>

                  <div class="detail-card">
                    <h3>Brief 与分析</h3>
                    <div class="meta">
                      <div><strong>主题</strong> ${escapeHtml(workspace.analysis?.theme || "暂无")}</div>
                      <div><strong>角度</strong> ${escapeHtml(workspace.analysis?.angle || "暂无")}</div>
                      <div><strong>目标读者</strong> ${escapeHtml(workspace.brief?.target_reader || "暂无")}</div>
                      <div><strong>新角度</strong> ${escapeHtml(workspace.brief?.new_angle || "暂无")}</div>
                      <div><strong>定位</strong> ${escapeHtml(workspace.brief?.positioning || "暂无")}</div>
                    </div>
                    <details>
                      <summary>展开 Brief JSON</summary>
                      <pre>${escapeHtml(JSON.stringify(workspace.brief || {}, null, 2))}</pre>
                    </details>
                  </div>
                </div>

                <div class="detail-card">
                  <h3>生成稿版本与审稿结论</h3>
                  <div class="generation-list">
                    ${workspace.generations.length ? workspace.generations.map((generation) => `
                      <div class="generation-card">
                        <div class="generation-header">
                          <span class="pill">v${escapeHtml(generation.version_no)}</span>
                          <span class="${scorePillClass(generation.review?.final_decision)}">${escapeHtml(generation.review?.final_decision || generation.status)}</span>
                          <span class="pill">model: ${escapeHtml(generation.model_name)}</span>
                          <span class="pill">prompt: ${escapeHtml(generation.prompt_version || "未记录")}</span>
                        </div>
                        <h3>${escapeHtml(generation.title || "未命名稿件")}</h3>
                        <div class="meta">
                          <div><strong>创建时间</strong> ${escapeHtml(formatDate(generation.created_at))}</div>
                          <div><strong>综合分</strong> ${escapeHtml(generation.score_overall ?? "暂无")}</div>
                          <div><strong>标题 / 可读性 / 新颖度 / 风险</strong> ${escapeHtml(generation.score_title ?? "-")} / ${escapeHtml(generation.score_readability ?? "-")} / ${escapeHtml(generation.score_novelty ?? "-")} / ${escapeHtml(generation.score_risk ?? "-")}</div>
                          <div><strong>AI 痕迹 / 命中模式 / 定点润色</strong> ${escapeHtml(reviewAiTraceLabel(generation.review))} / ${escapeHtml(reviewAiTracePatternCount(generation.review))} / ${escapeHtml(reviewHumanizeLabel(generation.review))}</div>
                          <div><strong>语气诊断</strong> ${escapeHtml(reviewVoiceSummary(generation.review))}</div>
                          <div><strong>摘要</strong> ${escapeHtml(generation.digest || "暂无")}</div>
                        </div>
                        <details>
                          <summary>展开审稿风险与建议</summary>
                          <pre>${escapeHtml(JSON.stringify(generation.review || {}, null, 2))}</pre>
                        </details>
                        <details open>
                          <summary>展开 HTML 预览</summary>
                          <div class="article-preview-shell" data-generation-html="${escapeHtml(generation.generation_id)}"></div>
                        </details>
                        <details>
                          <summary>展开原始 Markdown</summary>
                          <pre>${escapeHtml(generation.markdown_content || "暂无")}</pre>
                        </details>
                      </div>
                    `).join("") : '<div class="hint">当前任务还没有 generation。</div>'}
                  </div>
                </div>

                ${renderGenerationDiff(workspace.generations)}

                <div class="detail-card">
                  <h3>审计轨迹</h3>
                  <div class="audit-list">
                    ${workspace.audits.length ? workspace.audits.map((log) => `
                      <div class="audit-card">
                        <div><strong>${escapeHtml(log.action)}</strong></div>
                        <div class="meta">${escapeHtml(formatDate(log.created_at))} · ${escapeHtml(log.operator)}</div>
                        <pre>${escapeHtml(JSON.stringify(log.payload || {}, null, 2))}</pre>
                      </div>
                    `).join("") : '<div class="hint">暂无审计日志。</div>'}
                  </div>
                </div>
              `;

              const compareLeft = document.getElementById("compare-left");
              const compareRight = document.getElementById("compare-right");
              if (compareLeft && compareRight) {
                const rerenderDiff = () => updateDiffView(workspace.generations);
                compareLeft.addEventListener("change", rerenderDiff);
                compareRight.addEventListener("change", rerenderDiff);
                updateDiffView(workspace.generations);
              }
              hydrateArticlePreview(workspaceEl, workspace.generations);

              if (latestReview && latestReview.final_decision) {
                setStatus(`已加载 · 最新结论 ${latestReview.final_decision}`);
              } else {
                setStatus(`已加载 · ${workspace.status}`);
              }
            };

            const fetchWorkspace = async (taskId) => {
              if (!taskId) throw new Error("请先输入 task_id");
              workspaceEl.setAttribute("aria-busy", "true");
              try {
                const data = await request("GET", `/api/v1/tasks/${taskId}/workspace`);
                renderWorkspace(data);
                renderOutput(data);
                scrollWorkspaceIntoView();
                return data;
              } finally {
                workspaceEl.setAttribute("aria-busy", "false");
              }
            };

            const setTaskId = (taskId) => {
              taskEl.value = taskId;
              saveDraft();
            };

            const renderRecentBoard = (tasks) => {
              renderOverview(Array.isArray(tasks) ? tasks : []);
              if (!Array.isArray(tasks) || tasks.length === 0) {
                recentSummaryEl.innerHTML = "";
                recentListEl.innerHTML = '<div class="hint">当前筛选条件下没有任务。</div>';
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

              recentSummaryEl.innerHTML = orderedStatuses
                .map((item) => `<span class="pill">${escapeHtml(statusLabel(item))} · ${escapeHtml(counts[item])}</span>`)
                .join("");

              recentListEl.innerHTML = orderedStatuses
                .map((groupStatus) => `
                  <section class="group-block">
                    <div class="group-title">
                      <h3>${escapeHtml(statusLabel(groupStatus))}</h3>
                      <span>${escapeHtml(counts[groupStatus])} 个任务</span>
                    </div>
                    <div class="board">
                      ${tasks
                        .filter((task) => task.status === groupStatus)
                        .map((task) => `
                          <div class="task-card">
                            <h3>${escapeHtml(task.title || "未命名任务")}</h3>
                            <div class="hint">${escapeHtml(nextStepText(task))}</div>
                            <div class="meta">
                              <div><strong>task_id</strong> ${escapeHtml(task.task_id)}</div>
                              <div><strong>状态</strong> ${escapeHtml(task.status)} · ${escapeHtml(task.progress)}%</div>
                              <div><strong>草稿</strong> ${escapeHtml(task.wechat_media_id || "暂无")}</div>
                              <div><strong>更新时间</strong> ${escapeHtml(formatDate(task.updated_at))}</div>
                              <div><strong>链接</strong> ${escapeHtml(truncate(task.source_url, 88))}</div>
                            </div>
                            <div class="task-actions">
                              <button data-action="workspace" data-task-id="${escapeHtml(task.task_id)}">查看工作台</button>
                              <button data-action="phase3" data-task-id="${escapeHtml(task.task_id)}" class="secondary">入队 P3</button>
                              <button data-action="phase4" data-task-id="${escapeHtml(task.task_id)}" class="secondary">执行 P4</button>
                              <button data-action="approve" data-task-id="${escapeHtml(task.task_id)}" class="secondary">人工通过</button>
                              <button data-action="reject" data-task-id="${escapeHtml(task.task_id)}" class="danger">驳回重写</button>
                              <button data-action="allow-push" data-task-id="${escapeHtml(task.task_id)}" class="secondary">允许推稿</button>
                              <button data-action="block-push" data-task-id="${escapeHtml(task.task_id)}" class="danger">禁止推稿</button>
                              <button data-action="push" data-task-id="${escapeHtml(task.task_id)}" class="warn">推草稿</button>
                            </div>
                          </div>
                        `)
                        .join("")}
                    </div>
                  </section>
                `)
                .join("");
            };

            const refreshRecent = async () => {
              setPanelsBusy(true);
              const params = new URLSearchParams();
              try {
                params.set("limit", String(Math.min(Math.max(Number(recentLimitEl.value) || 18, 1), 50)));
                if (recentActiveEl.checked) {
                  params.set("active_only", "true");
                }
                if (recentStatusEl.value) {
                  params.set("status", recentStatusEl.value);
                }
                const tasks = await request("GET", `/api/v1/tasks?${params.toString()}`);
                renderRecentBoard(tasks);
              } finally {
                setPanelsBusy(false);
              }
            };

            const buildIngestPayload = () => {
              const url = urlEl.value.trim();
              if (!url) throw new Error("请先输入文章链接");
              return {
                url,
                source: "admin-console",
                device_id: deviceEl.value.trim() || "phase5-console",
                trigger: "manual",
                note: "phase5-console",
              };
            };
            const buildManualReviewPayload = () => ({
              operator: deviceEl.value.trim() || "phase5-console",
              note: reviewNoteEl.value.trim() || null,
            });

            document.getElementById("queue-url").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "入队中...", async () => {
                setStatus("入队中");
                const result = await request("POST", "/internal/v1/phase4/ingest-and-enqueue", buildIngestPayload());
                setTaskId(result.task_id);
                renderOutput(result);
                await refreshRecent();
                setStatus(result.status || "queued");
              });
            });

            document.getElementById("run-url").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "执行中...", async () => {
                setStatus("执行中");
                const result = await request("POST", "/internal/v1/phase4/ingest-and-run", buildIngestPayload());
                setTaskId(result.task_id);
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(result.task_id);
              });
            });

            document.getElementById("load-workspace").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "加载中...", async () => {
                await fetchWorkspace(taskEl.value.trim());
              });
            });

            document.getElementById("queue-phase3").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "入队中...", async () => {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("入队 Phase3");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/enqueue-phase3`);
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              });
            });

            document.getElementById("run-phase4").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "执行中...", async () => {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("执行 Phase4");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/run-phase4`);
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              });
            });

            document.getElementById("queue-phase4").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "入队中...", async () => {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("入队 Phase4");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/enqueue-phase4`);
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              });
            });

            document.getElementById("approve-generation").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "通过中...", async () => {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("人工通过");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/approve-latest-generation`, buildManualReviewPayload());
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              });
            });

            document.getElementById("reject-generation").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "退回中...", async () => {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("人工驳回重写");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/reject-latest-generation`, buildManualReviewPayload());
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              });
            });

            document.getElementById("allow-push").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "放行中...", async () => {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("允许推稿");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/allow-wechat-draft-push`, buildManualReviewPayload());
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              });
            });

            document.getElementById("block-push").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "禁止中...", async () => {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("禁止推草稿");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/block-wechat-draft-push`, buildManualReviewPayload());
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              });
            });

            document.getElementById("push-draft").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "推送中...", async () => {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("推送草稿中");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/push-wechat-draft`);
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              });
            });

            document.getElementById("clear").addEventListener("click", () => {
              setStatus("空闲");
              renderOutput("等待输入...");
              workspaceEl.innerHTML = '<div class="hint">工作台已清空。</div>';
            });

            document.getElementById("refresh-recent").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "刷新中...", async () => {
                setStatus("刷新列表中");
                await refreshRecent();
                setStatus("空闲");
              });
            });

            [recentStatusEl, recentLimitEl, recentActiveEl].forEach((element) => {
              element.addEventListener("change", async () => {
                try {
                  setStatus("刷新列表中");
                  await refreshRecent();
                  setStatus("空闲");
                } catch (error) {
                  setStatus("失败");
                  renderOutput(error.message || String(error));
                }
              });
            });

            recentListEl.addEventListener("click", async (event) => {
              const button = event.target.closest("button[data-action]");
              if (!button) return;
              const taskId = button.getAttribute("data-task-id");
              const action = button.getAttribute("data-action");
              if (!taskId || !action) return;
              setTaskId(taskId);

              withButtonBusy(button, "处理中...", async () => {
                if (action === "workspace") {
                  await fetchWorkspace(taskId);
                  return;
                }
                if (action === "phase3") {
                  setStatus("入队 Phase3");
                  const result = await request("POST", `/internal/v1/tasks/${taskId}/enqueue-phase3`);
                  renderOutput(result);
                  await refreshRecent();
                  await fetchWorkspace(taskId);
                  return;
                }
                if (action === "phase4") {
                  setStatus("执行 Phase4");
                  const result = await request("POST", `/internal/v1/tasks/${taskId}/run-phase4`);
                  renderOutput(result);
                  await refreshRecent();
                  await fetchWorkspace(taskId);
                  return;
                }
                if (action === "approve") {
                  setStatus("人工通过");
                  const result = await request("POST", `/internal/v1/tasks/${taskId}/approve-latest-generation`, buildManualReviewPayload());
                  renderOutput(result);
                  await refreshRecent();
                  await fetchWorkspace(taskId);
                  return;
                }
                if (action === "reject") {
                  setStatus("人工驳回重写");
                  const result = await request("POST", `/internal/v1/tasks/${taskId}/reject-latest-generation`, buildManualReviewPayload());
                  renderOutput(result);
                  await refreshRecent();
                  await fetchWorkspace(taskId);
                  return;
                }
                if (action === "allow-push") {
                  setStatus("允许推稿");
                  const result = await request("POST", `/internal/v1/tasks/${taskId}/allow-wechat-draft-push`, buildManualReviewPayload());
                  renderOutput(result);
                  await refreshRecent();
                  await fetchWorkspace(taskId);
                  return;
                }
                if (action === "block-push") {
                  setStatus("禁止推草稿");
                  const result = await request("POST", `/internal/v1/tasks/${taskId}/block-wechat-draft-push`, buildManualReviewPayload());
                  renderOutput(result);
                  await refreshRecent();
                  await fetchWorkspace(taskId);
                  return;
                }
                if (action === "push") {
                  setStatus("推送草稿中");
                  const result = await request("POST", `/internal/v1/tasks/${taskId}/push-wechat-draft`);
                  renderOutput(result);
                  await refreshRecent();
                  await fetchWorkspace(taskId);
                }
              });
            });

            loadDraft();
            renderOverview([]);
            refreshRecent().catch((error) => {
              renderOverview([]);
              recentListEl.innerHTML = `<div class="hint">${escapeHtml(error.message || "最近任务加载失败，请稍后重试。")}</div>`;
              renderOutput(error.message || String(error));
            });
          </script>
        </body>
        </html>
        """
    )
    return (
        html.replace("__ADMIN_NAV_STYLES__", admin_section_nav_styles()).replace(
            "__ADMIN_SECTION_NAV__", admin_section_nav("review")
        )
    )


@router.get("/admin/phase6", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def phase6_console() -> str:
    html = dedent(
        """\
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>Phase 6 反馈台</title>
          <style>
            :root {
              --bg: #edf2ec;
              --panel: rgba(250, 255, 248, 0.92);
              --line: #bdd0be;
              --text: #1e271d;
              --muted: #5d6b5e;
              --accent: #2b6f58;
              --accent-dark: #1b4b3b;
              --danger: #9b4130;
              --warn: #a87418;
              --ink: #163028;
              --shadow: 0 18px 46px rgba(24, 42, 29, 0.1);
            }
            * { box-sizing: border-box; }
            body {
              margin: 0;
              line-height: 1.5;
              color: var(--text);
              font-family: "PingFang SC", "Noto Serif SC", serif;
              background:
                radial-gradient(circle at top left, rgba(243, 250, 214, 0.55), transparent 24%),
                radial-gradient(circle at right bottom, rgba(197, 234, 219, 0.45), transparent 28%),
                linear-gradient(140deg, #e9eee7 0%, #f3f6f0 42%, #e7eee5 100%);
              min-height: 100vh;
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
              max-width: 1280px;
              margin: 0 auto;
              padding: 32px 20px 52px;
            }
            .hero {
              display: grid;
              gap: 14px;
              padding: 24px;
              border: 1px solid var(--line);
              border-radius: 28px;
              background: linear-gradient(135deg, rgba(252, 255, 250, 0.94), rgba(244, 249, 242, 0.9));
              box-shadow: var(--shadow);
              backdrop-filter: blur(10px);
              margin-bottom: 20px;
            }
            .hero-grid {
              display: grid;
              grid-template-columns: minmax(0, 1.24fr) minmax(320px, 0.94fr);
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
              background: rgba(43, 111, 88, 0.12);
              color: var(--accent-dark);
              font-size: 12px;
              letter-spacing: 0.08em;
            }
            .hero h1 {
              margin: 0;
              font-size: 42px;
              line-height: 1.04;
            }
            .hero p {
              margin: 0;
              max-width: 820px;
              color: var(--muted);
              line-height: 1.75;
            }
            .hero-status-card {
              display: grid;
              gap: 14px;
              padding: 18px;
              border-radius: 24px;
              border: 1px solid rgba(43, 111, 88, 0.14);
              background: linear-gradient(160deg, rgba(255, 255, 252, 0.95), rgba(244, 249, 242, 0.92));
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
              border: 1px solid rgba(22, 48, 40, 0.08);
              background: rgba(255, 255, 252, 0.82);
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
              background: linear-gradient(135deg, rgba(43, 111, 88, 0.1), rgba(252, 255, 250, 0.96));
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
              background: rgba(250, 255, 248, 0.88);
              box-shadow: 0 14px 32px rgba(24, 42, 29, 0.08);
            }
            .overview-card.highlight {
              grid-column: span 2;
              background: linear-gradient(135deg, rgba(43, 111, 88, 0.1), rgba(252, 255, 250, 0.96));
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
              grid-template-columns: 380px minmax(0, 1fr);
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
              border-radius: 24px;
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
            .grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
              gap: 12px;
            }
            .grid.single {
              grid-template-columns: 1fr;
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
            input, textarea, button, select {
              width: 100%;
              font: inherit;
              border-radius: 14px;
            }
            input, textarea, select {
              padding: 12px 14px;
              background: #fffefb;
              color: var(--text);
              border: 1px solid var(--line);
            }
            input:focus-visible,
            textarea:focus-visible,
            select:focus-visible,
            button:focus-visible,
            a:focus-visible,
            summary:focus-visible {
              outline: 2px solid rgba(43, 111, 88, 0.2);
              outline-offset: 3px;
            }
            textarea {
              min-height: 120px;
              resize: vertical;
            }
            button {
              border: none;
              cursor: pointer;
              padding: 12px 16px;
              background: var(--accent);
              color: #f7fdf8;
              transition: transform 0.12s ease, background 0.12s ease;
            }
            button:hover {
              background: var(--accent-dark);
              transform: translateY(-1px);
            }
            button.secondary {
              background: #d2e1d5;
              color: var(--ink);
            }
            button.danger {
              background: var(--danger);
              color: #fff7f3;
            }
            button.warn {
              background: var(--warn);
              color: #fff9ea;
            }
            button[aria-busy="true"] {
              opacity: 0.82;
              cursor: progress;
            }
            .actions {
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: 10px;
              margin-top: 14px;
            }
            .actions.compact {
              grid-template-columns: repeat(3, minmax(0, 1fr));
            }
            .action-blocks {
              display: grid;
              gap: 10px;
              margin-top: 14px;
            }
            .action-block {
              border: 1px solid var(--line);
              border-radius: 18px;
              padding: 12px;
              background: rgba(255, 254, 251, 0.84);
            }
            .action-block h3 {
              margin: 0 0 10px;
              font-size: 13px;
              color: var(--muted);
            }
            .action-grid {
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: 10px;
            }
            .status {
              display: inline-flex;
              padding: 7px 12px;
              border-radius: 999px;
              background: rgba(43, 111, 88, 0.14);
              color: var(--accent-dark);
              font-size: 12px;
            }
            .status.warn {
              background: rgba(168, 116, 24, 0.18);
              color: #85570f;
            }
            .status.danger {
              background: rgba(155, 65, 48, 0.12);
              color: var(--danger);
            }
            pre {
              margin: 0;
              min-height: 240px;
              padding: 16px;
              border-radius: 18px;
              background: #163028;
              color: #eef8f1;
              white-space: pre-wrap;
              word-break: break-word;
              line-height: 1.65;
              overflow: auto;
            }
            .hint {
              margin: 0;
              color: var(--muted);
              font-size: 13px;
              line-height: 1.7;
            }
            .list {
              display: grid;
              align-content: start;
              grid-auto-rows: max-content;
              gap: 12px;
            }
            .list[aria-busy="true"] {
              opacity: 0.78;
            }
            .card {
              border: 1px solid var(--line);
              border-radius: 18px;
              padding: 14px;
              background: #fffefb;
              display: grid;
              align-content: start;
              gap: 8px;
              min-width: 0;
            }
            .card h3 {
              margin: 0;
              font-size: 16px;
              overflow-wrap: anywhere;
            }
            .meta {
              display: grid;
              gap: 4px;
              font-size: 13px;
              color: var(--muted);
              line-height: 1.6;
              overflow-wrap: anywhere;
            }
            .pill-row {
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
            }
            .pill {
              display: inline-flex;
              align-items: center;
              padding: 4px 10px;
              border-radius: 999px;
              background: #e4efe6;
              color: var(--ink);
              font-size: 12px;
              overflow-wrap: anywhere;
            }
            .fold {
              border: 1px dashed var(--line);
              border-radius: 18px;
              padding: 14px;
              background: rgba(255, 254, 251, 0.72);
            }
            .fold + .fold {
              margin-top: 12px;
            }
            .fold summary {
              cursor: pointer;
              color: var(--muted);
              font-size: 13px;
            }
            .tool-note {
              margin-top: 10px;
            }
            __ADMIN_NAV_STYLES__
            @media (max-width: 1040px) {
              .hero-grid { grid-template-columns: 1fr; }
              .overview-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
              .overview-card.highlight { grid-column: span 2; }
            }
            @media (max-width: 980px) {
              .layout { grid-template-columns: 1fr; }
            }
            @media (max-width: 720px) {
              main { padding: 22px 14px 36px; }
              .panel { padding: 16px; border-radius: 20px; }
              .hero h1 { font-size: 30px; }
              .hero-summary,
              .overview-strip,
              .actions,
              .actions.compact,
              .action-grid,
              .grid {
                grid-template-columns: 1fr;
              }
              .overview-card.highlight { grid-column: span 1; }
            }
          </style>
        </head>
        <body>
          <a class="skip-link" href="#feedback-region">跳到反馈主区</a>
          <main>
            __ADMIN_SECTION_NAV__
            <section class="hero">
              <div class="hero-grid">
                <div class="hero-copy">
                  <span class="eyebrow">PHASE 6 FEEDBACK LOOP</span>
                  <h1>反馈台</h1>
                  <p>这里负责回收任务反馈、观察 prompt 实验表现，并沉淀已经验证过的写法资产。先锁定任务，再决定是查历史、补录反馈，还是把结论沉淀下来。</p>
                </div>
                <aside class="hero-status-card" aria-label="反馈页状态">
                  <span class="status" id="status">等待输入</span>
                  <p class="hero-status-copy" id="flash-message" role="status" aria-live="polite" aria-atomic="true">默认复用后台会话。先补 task_id，再选择“查反馈”“同步”或“导入”。</p>
                  <div class="hero-summary" aria-label="首屏提示">
                    <div class="hero-summary-card">
                      <strong>这页负责什么</strong>
                      <span>把任务表现、实验趋势和复用资产串成一个反馈闭环。</span>
                    </div>
                    <div class="hero-summary-card">
                      <strong>需要准备什么</strong>
                      <span>task_id，以及必要时的 generation_id 和操作人标识；默认复用后台会话。</span>
                    </div>
                    <div class="hero-summary-card wide">
                      <strong>当前建议</strong>
                      <span id="hero-focus">先补 task_id，再看当前任务有没有已有反馈。</span>
                    </div>
                  </div>
                </aside>
              </div>
            </section>

            <section class="overview-strip" aria-label="反馈概览">
              <article class="overview-card">
                <strong>当前任务反馈</strong>
                <span id="overview-feedback-count">0</span>
                <p>按当前 task_id 回收到的反馈快照数量。</p>
              </article>
              <article class="overview-card">
                <strong>实验榜样本</strong>
                <span id="overview-experiment-count">0</span>
                <p>当前页已拉下来的 prompt 实验排行条目数。</p>
              </article>
              <article class="overview-card">
                <strong>风格资产</strong>
                <span id="overview-asset-count">0</span>
                <p>当前页已拉下来的可复用写法资产数量。</p>
              </article>
              <article class="overview-card highlight">
                <strong>当前优先</strong>
                <span id="overview-focus">先补 task_id，再看当前任务有没有已有反馈。</span>
                <p id="overview-focus-note">没有 task_id 时，只有实验榜和资产库能独立查询；导入与同步都需要任务上下文。</p>
              </article>
            </section>

            <section class="layout" id="feedback-region">
              <div class="stack">
                <section class="panel">
                  <h2>先准备</h2>
                  <p class="panel-intro">这一列负责任务上下文。页面默认复用当前后台会话；查实验、查资产可以独立执行，但导入反馈、同步反馈、沉淀资产最好先带上当前任务。如果停留太久后提示未授权，刷新页面重新进入后台即可。</p>
                  <div class="grid single">
                    <div class="field">
                      <label for="task-id">Task ID</label>
                      <input id="task-id" type="text" placeholder="f703c3ef-..." aria-describedby="task-id-hint" />
                    </div>
                    <p class="field-hint" id="task-id-hint">建议先锁定 task_id，再看反馈快照和后续动作。没有 task_id 时，手工导入和同步会失败。</p>
                    <div class="grid">
                      <div class="field">
                        <label for="generation-id">Generation ID（可选）</label>
                        <input id="generation-id" type="text" placeholder="默认取 latest accepted / latest" aria-describedby="generation-id-hint" />
                      </div>
                      <div class="field">
                        <label for="operator">操作人</label>
                        <input id="operator" type="text" value="admin-console" aria-describedby="operator-hint" />
                      </div>
                    </div>
                    <p class="field-hint" id="generation-id-hint">不填时默认取最新 accepted generation；如果任务还没 accepted，会回退到最近一次 generation。</p>
                    <p class="field-hint" id="operator-hint">会写入导入记录和资产审计日志，建议填当前值班人或操作来源。</p>
                  </div>
                  <div class="action-blocks">
                    <article class="action-block">
                      <h3>先看现状</h3>
                      <div class="action-grid">
                        <button id="query-feedback" class="secondary">查反馈</button>
                        <button id="refresh-experiments" class="secondary">查实验</button>
                        <button id="refresh-assets" class="secondary">查资产</button>
                        <button id="clear-output" class="danger">清空输出</button>
                      </div>
                    </article>
                  </div>
                </section>

                <section class="panel">
                  <h2>自动同步</h2>
                  <p class="panel-intro">这一步只处理已经成功入草稿的任务。建议先查反馈确认哪些窗口还空着，再决定立即同步、单任务入队，还是扫最近草稿批量入队。</p>
                  <div class="grid">
                    <div class="field">
                      <label for="sync-day-offsets">同步窗口（逗号分隔）</label>
                      <input id="sync-day-offsets" type="text" value="1,3,7" aria-describedby="sync-day-offsets-hint" />
                    </div>
                    <div class="field">
                      <label for="sync-limit">扫描最近草稿数</label>
                      <input id="sync-limit" type="number" min="1" max="100" value="20" aria-describedby="sync-limit-hint" />
                    </div>
                  </div>
                  <p class="field-hint" id="sync-day-offsets-hint">通常用 `1,3,7`，分别对应 T+1、T+3、T+7 反馈窗口。</p>
                  <p class="field-hint" id="sync-limit-hint">只对“扫描入队”生效，用来限制最近要扫多少条已入草稿任务。</p>
                  <div class="actions compact">
                    <button id="run-feedback-sync">立即同步</button>
                    <button id="queue-feedback-sync" class="secondary">单任务入队</button>
                    <button id="queue-recent-feedback-sync" class="secondary">扫描入队</button>
                  </div>
                </section>

                <section class="panel">
                  <h2>导入反馈</h2>
                  <p class="panel-intro">当微信后台数据需要人工抄录时，用这里补 T+1、T+3、T+7 的快照。备注里最好写清楚数据来源和时间，方便后续复盘。</p>
                  <div class="grid">
                    <div class="field">
                      <label for="day-offset">观察窗口</label>
                      <select id="day-offset">
                        <option value="1">T+1</option>
                        <option value="3">T+3</option>
                        <option value="7">T+7</option>
                      </select>
                    </div>
                    <div class="field">
                      <label for="snapshot-at">快照时间（ISO，可选）</label>
                      <input id="snapshot-at" type="text" placeholder="2026-03-08T10:00:00+08:00" />
                    </div>
                    <div class="field">
                      <label for="read-count">阅读数</label>
                      <input id="read-count" type="number" min="0" placeholder="1200" />
                    </div>
                    <div class="field">
                      <label for="like-count">点赞数</label>
                      <input id="like-count" type="number" min="0" placeholder="86" />
                    </div>
                    <div class="field">
                      <label for="share-count">转发数</label>
                      <input id="share-count" type="number" min="0" placeholder="14" />
                    </div>
                    <div class="field">
                      <label for="comment-count">评论数</label>
                      <input id="comment-count" type="number" min="0" placeholder="3" />
                    </div>
                    <div class="field">
                      <label for="click-rate">点击率（可选）</label>
                      <input id="click-rate" type="number" min="0" step="0.0001" placeholder="0.1825" />
                    </div>
                    <div class="field">
                      <label for="media-id">media_id（可选）</label>
                      <input id="media-id" type="text" placeholder="默认回填最近草稿 media_id" />
                    </div>
                  </div>
                  <div class="field" style="margin-top: 12px;">
                    <label for="feedback-notes">导入备注</label>
                    <textarea id="feedback-notes" placeholder="例如：后台手工抄录 T+1 数据"></textarea>
                  </div>
                  <div class="actions">
                    <button id="import-feedback">导入反馈</button>
                  </div>
                </section>

                <section class="panel">
                  <h2>辅助工具</h2>
                  <p class="panel-intro">低频动作放到这里，避免打断主路径。只有在字段齐全、确认要批量处理或沉淀模板时再展开。</p>
                  <details class="fold">
                    <summary>批量导入 CSV</summary>
                    <div style="margin-top: 12px;">
                      <label for="feedback-csv">CSV 内容</label>
                      <textarea id="feedback-csv" placeholder="task_id,generation_id,day_offset,read_count,like_count,share_count,comment_count,click_rate,notes&#10;f703c3ef-e358-48ab-936d-187418c584c5,,1,1666,101,18,6,0.2031,第一批回填"></textarea>
                    </div>
                    <div class="actions">
                      <button id="import-feedback-csv" class="secondary">导入 CSV</button>
                    </div>
                    <p class="hint tool-note">支持常用列；不带 `task_id` 时，会默认使用上面的当前 `task_id`。</p>
                  </details>
                  <details class="fold">
                    <summary>新建风格资产</summary>
                    <div class="grid" style="margin-top: 12px;">
                      <div class="field">
                        <label for="asset-type">资产类型</label>
                        <input id="asset-type" type="text" value="opening_hook" />
                      </div>
                      <div class="field">
                        <label for="asset-title">标题</label>
                        <input id="asset-title" type="text" placeholder="反直觉开头模板" />
                      </div>
                      <div class="field">
                        <label for="asset-tags">标签（逗号分隔）</label>
                        <input id="asset-tags" type="text" placeholder="技术科普,误区纠偏" />
                      </div>
                      <div class="field">
                        <label for="asset-weight">权重</label>
                        <input id="asset-weight" type="number" min="0.1" step="0.1" value="1.0" />
                      </div>
                    </div>
                    <div class="field" style="margin-top: 12px;">
                      <label for="asset-content">资产内容</label>
                      <textarea id="asset-content" placeholder="写下经过验证的标题模板、开头结构、段落骨架或转场句式"></textarea>
                    </div>
                    <div class="field" style="margin-top: 12px;">
                      <label for="asset-notes">备注</label>
                      <textarea id="asset-notes" placeholder="可记录来源任务、适用题材、风险提醒"></textarea>
                    </div>
                    <div class="actions">
                      <button id="create-asset">新建资产</button>
                    </div>
                    <p class="hint tool-note">只把已经验证过、会重复用到的写法沉淀下来。</p>
                  </details>
                </section>
              </div>

              <div class="stack">
                <section class="panel">
                  <h2>输出与提示</h2>
                  <p class="panel-intro">这里保留最近一次请求返回，方便复制排错、核对导入结果，或确认自动同步到底做了什么。</p>
                  <pre id="output">等待输入...</pre>
                </section>

                <section class="panel">
                  <h2>任务反馈快照</h2>
                  <p class="panel-intro">按当前 task_id 展示已经回收到的反馈快照。空态时会提醒你下一步该查同步还是补录。</p>
                  <div class="list" id="task-feedback-list" aria-busy="false">
                    <div class="hint">先输入 task_id，再点击“查反馈”。</div>
                  </div>
                </section>

                <section class="panel">
                  <h2>Prompt 实验榜</h2>
                  <p class="panel-intro">比较不同 prompt 版本在各观察窗口里的稳定性，先看哪套更稳，再决定是否要固化成资产或继续观察。</p>
                  <div class="list" id="experiment-list" aria-busy="false">
                    <div class="hint">点击“查实验”拉一版最新样本。</div>
                  </div>
                </section>

                <section class="panel">
                  <h2>风格资产库</h2>
                  <p class="panel-intro">这里只保留已经验证过、值得复用的结构和句式，不收临时想法。先看历史资产，再决定是否新增。</p>
                  <div class="list" id="style-asset-list" aria-busy="false">
                    <div class="hint">点击“查资产”拉一版当前沉淀。</div>
                  </div>
                </section>
              </div>
            </section>
          </main>

          <script>
            const taskIdEl = document.getElementById("task-id");
            const generationIdEl = document.getElementById("generation-id");
            const operatorEl = document.getElementById("operator");
            const syncDayOffsetsEl = document.getElementById("sync-day-offsets");
            const syncLimitEl = document.getElementById("sync-limit");
            const dayOffsetEl = document.getElementById("day-offset");
            const snapshotAtEl = document.getElementById("snapshot-at");
            const readCountEl = document.getElementById("read-count");
            const likeCountEl = document.getElementById("like-count");
            const shareCountEl = document.getElementById("share-count");
            const commentCountEl = document.getElementById("comment-count");
            const clickRateEl = document.getElementById("click-rate");
            const mediaIdEl = document.getElementById("media-id");
            const feedbackNotesEl = document.getElementById("feedback-notes");
            const feedbackCsvEl = document.getElementById("feedback-csv");
            const assetTypeEl = document.getElementById("asset-type");
            const assetTitleEl = document.getElementById("asset-title");
            const assetTagsEl = document.getElementById("asset-tags");
            const assetWeightEl = document.getElementById("asset-weight");
            const assetContentEl = document.getElementById("asset-content");
            const assetNotesEl = document.getElementById("asset-notes");
            const outputEl = document.getElementById("output");
            const statusEl = document.getElementById("status");
            const flashMessageEl = document.getElementById("flash-message");
            const heroFocusEl = document.getElementById("hero-focus");
            const taskFeedbackListEl = document.getElementById("task-feedback-list");
            const experimentListEl = document.getElementById("experiment-list");
            const styleAssetListEl = document.getElementById("style-asset-list");
            const overviewFeedbackCountEl = document.getElementById("overview-feedback-count");
            const overviewExperimentCountEl = document.getElementById("overview-experiment-count");
            const overviewAssetCountEl = document.getElementById("overview-asset-count");
            const overviewFocusEl = document.getElementById("overview-focus");
            const overviewFocusNoteEl = document.getElementById("overview-focus-note");
            let currentTaskFeedbackCount = 0;
            let currentExperimentItems = [];
            let currentAssetItems = [];
            const SESSION_EXPIRED_MESSAGE = "后台会话已失效，请刷新页面重新进入后台。";

            const escapeHtml = (value) => String(value ?? "")
              .replaceAll("&", "&amp;")
              .replaceAll("<", "&lt;")
              .replaceAll(">", "&gt;")
              .replaceAll('"', "&quot;");
            const truncate = (value, length = 16) => {
              const text = String(value ?? "");
              if (!text || text.length <= length) return text || "当前任务";
              return `${text.slice(0, length)}...`;
            };

            const formatDate = (value) => {
              if (!value) return "未知";
              const date = new Date(value);
              if (Number.isNaN(date.getTime())) return String(value);
              return date.toLocaleString("zh-CN", { hour12: false });
            };

            const setStatus = (value, tone = "", message = value) => {
              statusEl.textContent = value;
              statusEl.className = `status ${tone}`.trim();
              if (flashMessageEl) {
                flashMessageEl.textContent = message;
              }
            };
            const renderOutput = (value) => {
              outputEl.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
            };
            const apiUrl = (path) => new URL(path, window.location.origin).toString();
            const setListBusy = (element, busy, loadingText = "") => {
              if (!element) return;
              element.setAttribute("aria-busy", busy ? "true" : "false");
              if (busy && loadingText) {
                element.innerHTML = `<div class="hint">${escapeHtml(loadingText)}</div>`;
              }
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
            const renderOverview = () => {
              const taskId = taskIdEl.value.trim();
              overviewFeedbackCountEl.textContent = String(currentTaskFeedbackCount);
              overviewExperimentCountEl.textContent = String(currentExperimentItems.length);
              overviewAssetCountEl.textContent = String(currentAssetItems.length);
              let focus = "先补 task_id，再看当前任务有没有已有反馈。";
              let note = "没有 task_id 时，只有实验榜和资产库能独立查询；导入与同步都需要任务上下文。";
              if (!taskId) {
                focus = "可以先查实验榜和资产库，但要补反馈或做同步前，先补上 task_id。";
                note = "task_id 决定反馈快照、自动同步和资产来源归属。";
              } else if (currentTaskFeedbackCount === 0) {
                focus = `当前任务 ${truncate(taskId, 12)} 还没看到反馈，先查反馈，再决定同步还是手工导入。`;
                note = "同步只处理已入草稿任务；如果数据来自微信后台手工抄录，用“导入反馈”最直接。";
              } else if (!currentExperimentItems.length) {
                focus = "已有任务反馈，接着刷新实验榜，看哪套 prompt 更稳。";
                note = "实验榜适合判断是否继续用当前 prompt，或者要不要把结论固化成资产。";
              } else if (!currentAssetItems.length) {
                focus = "实验榜已经加载，可以把稳定写法沉淀成风格资产。";
                note = "只记录已经验证过、会重复复用的结构或句式，避免把临时想法写进资产库。";
              } else {
                focus = "反馈、实验和资产都已就绪，可以围绕当前任务做完整复盘。";
                note = "优先看早期反馈，再结合实验榜判断是否要补新资产或调整后续策略。";
              }
              overviewFocusEl.textContent = focus;
              overviewFocusNoteEl.textContent = note;
              if (heroFocusEl) {
                heroFocusEl.textContent = focus;
              }
            };

            const loadDraft = () => {
              taskIdEl.value = localStorage.getItem("phase6_console_task_id") || "";
              generationIdEl.value = localStorage.getItem("phase6_console_generation_id") || "";
              operatorEl.value = localStorage.getItem("phase6_console_operator") || "admin-console";
              syncDayOffsetsEl.value = localStorage.getItem("phase6_console_sync_day_offsets") || "1,3,7";
              syncLimitEl.value = localStorage.getItem("phase6_console_sync_limit") || "20";
            };

            const saveDraft = () => {
              localStorage.setItem("phase6_console_task_id", taskIdEl.value.trim());
              localStorage.setItem("phase6_console_generation_id", generationIdEl.value.trim());
              localStorage.setItem("phase6_console_operator", operatorEl.value.trim());
              localStorage.setItem("phase6_console_sync_day_offsets", syncDayOffsetsEl.value.trim());
              localStorage.setItem("phase6_console_sync_limit", syncLimitEl.value.trim());
            };

            const request = async (method, path, body) => {
              saveDraft();
              const headers = {};
              if (body !== undefined) {
                headers["Content-Type"] = "application/json";
              }
              const response = await fetch(apiUrl(path), {
                method,
                headers,
                credentials: "same-origin",
                body: body === undefined ? undefined : JSON.stringify(body)
              });
              const text = await response.text();
              let payload = text;
              try { payload = JSON.parse(text); } catch (_) {}
              if (!response.ok) {
                if (response.status === 401) {
                  throw new Error(SESSION_EXPIRED_MESSAGE);
                }
                throw new Error(typeof payload === "string" ? payload : JSON.stringify(payload, null, 2));
              }
              return payload;
            };

            const parseNumber = (value) => {
              const normalized = String(value ?? "").trim();
              if (!normalized) return undefined;
              const parsed = Number(normalized);
              return Number.isFinite(parsed) ? parsed : undefined;
            };

            const parseDayOffsets = () => String(syncDayOffsetsEl.value || "")
              .split(",")
              .map((item) => Number(item.trim()))
              .filter((value) => Number.isInteger(value) && value >= 0);

            const buildFeedbackPayload = () => ({
              generation_id: generationIdEl.value.trim() || undefined,
              day_offset: Number(dayOffsetEl.value),
              snapshot_at: snapshotAtEl.value.trim() || undefined,
              wechat_media_id: mediaIdEl.value.trim() || undefined,
              read_count: parseNumber(readCountEl.value),
              like_count: parseNumber(likeCountEl.value),
              share_count: parseNumber(shareCountEl.value),
              comment_count: parseNumber(commentCountEl.value),
              click_rate: parseNumber(clickRateEl.value),
              notes: feedbackNotesEl.value.trim() || undefined,
              imported_by: operatorEl.value.trim() || "admin-console",
              operator: operatorEl.value.trim() || "admin-console"
            });

            const buildStyleAssetPayload = () => ({
              asset_type: assetTypeEl.value.trim(),
              title: assetTitleEl.value.trim(),
              content: assetContentEl.value.trim(),
              tags: assetTagsEl.value.split(",").map((item) => item.trim()).filter(Boolean),
              weight: parseNumber(assetWeightEl.value),
              notes: assetNotesEl.value.trim() || undefined,
              source_task_id: taskIdEl.value.trim() || undefined,
              source_generation_id: generationIdEl.value.trim() || undefined,
              operator: operatorEl.value.trim() || "admin-console"
            });

            const buildFeedbackSyncPayload = () => ({
              day_offsets: parseDayOffsets(),
              operator: operatorEl.value.trim() || "admin-console"
            });

            const buildFeedbackCsvPayload = () => ({
              csv_text: feedbackCsvEl.value,
              default_task_id: taskIdEl.value.trim() || undefined,
              imported_by: operatorEl.value.trim() || "admin-console",
              operator: operatorEl.value.trim() || "admin-console"
            });

            const buildRecentFeedbackSyncPayload = () => ({
              limit: parseNumber(syncLimitEl.value) || 20,
              day_offsets: parseDayOffsets(),
              operator: operatorEl.value.trim() || "admin-console"
            });

            const renderTaskFeedback = (payload) => {
              const items = payload?.metrics || [];
              currentTaskFeedbackCount = items.length;
              if (!items.length) {
                taskFeedbackListEl.innerHTML = '<div class="hint">当前任务还没有反馈记录。先确认是否已经入草稿，再决定用“立即同步”还是“导入反馈”。</div>';
                renderOverview();
                return;
              }
              taskFeedbackListEl.innerHTML = items.map((item) => `
                <article class="card">
                  <h3>${escapeHtml(`T+${item.day_offset} / ${item.prompt_version}`)}</h3>
                  <div class="pill-row">
                    <span class="pill">generation: ${escapeHtml(item.generation_id)}</span>
                    <span class="pill">media_id: ${escapeHtml(item.wechat_media_id || "-")}</span>
                  </div>
                  <div class="meta">
                    <div>快照时间: ${escapeHtml(formatDate(item.snapshot_at))}</div>
                    <div>阅读 / 点赞 / 转发 / 评论: ${escapeHtml(item.read_count ?? "-")} / ${escapeHtml(item.like_count ?? "-")} / ${escapeHtml(item.share_count ?? "-")} / ${escapeHtml(item.comment_count ?? "-")}</div>
                    <div>点击率: ${escapeHtml(item.click_rate ?? "-")}</div>
                    <div>导入来源: ${escapeHtml(item.source_type)} / ${escapeHtml(item.imported_by)}</div>
                    <div>备注: ${escapeHtml(item.notes || "-")}</div>
                  </div>
                </article>
              `).join("");
              renderOverview();
            };

            const renderExperiments = (items) => {
              currentExperimentItems = Array.isArray(items) ? items : [];
              if (!currentExperimentItems.length) {
                experimentListEl.innerHTML = '<div class="hint">还没有实验样本。等有更多反馈回流后，再来比较哪套 prompt 更稳。</div>';
                renderOverview();
                return;
              }
              experimentListEl.innerHTML = currentExperimentItems.map((item) => `
                <article class="card">
                  <h3>${escapeHtml(`${item.prompt_type} / ${item.prompt_version}`)}</h3>
                  <div class="pill-row">
                    <span class="pill">窗口 T+${escapeHtml(item.day_offset)}</span>
                    <span class="pill">样本 ${escapeHtml(item.sample_count)}</span>
                    <span class="pill">最高阅读 ${escapeHtml(item.best_read_count ?? "-")}</span>
                  </div>
                  <div class="meta">
                    <div>平均阅读: ${escapeHtml(item.avg_read_count ?? "-")}</div>
                    <div>平均点赞: ${escapeHtml(item.avg_like_count ?? "-")}</div>
                    <div>平均转发: ${escapeHtml(item.avg_share_count ?? "-")}</div>
                    <div>平均评论: ${escapeHtml(item.avg_comment_count ?? "-")}</div>
                    <div>平均点击率: ${escapeHtml(item.avg_click_rate ?? "-")}</div>
                    <div>最近快照: ${escapeHtml(formatDate(item.latest_metric_at))}</div>
                    <div>最近任务: ${escapeHtml(item.last_task_id || "-")}</div>
                  </div>
                </article>
              `).join("");
              renderOverview();
            };

            const renderStyleAssets = (items) => {
              currentAssetItems = Array.isArray(items) ? items : [];
              if (!currentAssetItems.length) {
                styleAssetListEl.innerHTML = '<div class="hint">还没有风格资产。先看实验榜和真实反馈，再把稳定写法沉淀下来。</div>';
                renderOverview();
                return;
              }
              styleAssetListEl.innerHTML = currentAssetItems.map((item) => `
                <article class="card">
                  <h3>${escapeHtml(item.title)}</h3>
                  <div class="pill-row">
                    <span class="pill">${escapeHtml(item.asset_type)}</span>
                    <span class="pill">状态 ${escapeHtml(item.status)}</span>
                    <span class="pill">权重 ${escapeHtml(item.weight)}</span>
                  </div>
                  <div class="meta">
                    <div>标签: ${escapeHtml((item.tags || []).join(", ") || "-")}</div>
                    <div>来源任务: ${escapeHtml(item.source_task_id || "-")}</div>
                    <div>来源 generation: ${escapeHtml(item.source_generation_id || "-")}</div>
                    <div>内容: ${escapeHtml(item.content)}</div>
                    <div>备注: ${escapeHtml(item.notes || "-")}</div>
                  </div>
                </article>
              `).join("");
              renderOverview();
            };

            const queryTaskFeedback = async () => {
              const taskId = taskIdEl.value.trim();
              if (!taskId) throw new Error("请先输入 task_id");
              setListBusy(taskFeedbackListEl, true, "正在查询当前任务反馈...");
              try {
                const payload = await request("GET", `/api/v1/tasks/${taskId}/feedback`);
                renderTaskFeedback(payload);
                return payload;
              } finally {
                setListBusy(taskFeedbackListEl, false);
              }
            };

            const refreshExperiments = async () => {
              setListBusy(experimentListEl, true, "正在查询 prompt 实验榜...");
              try {
                const items = await request("GET", "/api/v1/feedback/experiments?limit=12");
                renderExperiments(items);
                return items;
              } finally {
                setListBusy(experimentListEl, false);
              }
            };

            const refreshStyleAssets = async () => {
              setListBusy(styleAssetListEl, true, "正在查询风格资产...");
              try {
                const items = await request("GET", "/api/v1/feedback/style-assets?limit=12");
                renderStyleAssets(items);
                return items;
              } finally {
                setListBusy(styleAssetListEl, false);
              }
            };

            document.getElementById("query-feedback").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "查询中...", async () => {
                saveDraft();
                setStatus("查反馈", "", "正在查询当前任务的反馈快照。");
                const payload = await queryTaskFeedback();
                renderOutput(payload);
                setStatus("已完成", "", "任务反馈已更新，可以决定是否同步、补录或继续看实验榜。");
              });
            });

            document.getElementById("refresh-experiments").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "查询中...", async () => {
                saveDraft();
                setStatus("查实验", "", "正在刷新 prompt 实验榜。");
                const items = await refreshExperiments();
                renderOutput(items);
                setStatus("已完成", "", "实验榜已更新，可以对比哪套 prompt 更稳。");
              });
            });

            document.getElementById("refresh-assets").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "查询中...", async () => {
                saveDraft();
                setStatus("查资产", "", "正在刷新风格资产库。");
                const items = await refreshStyleAssets();
                renderOutput(items);
                setStatus("已完成", "", "风格资产已更新，可以判断是否还需要新增沉淀。");
              });
            });

            document.getElementById("import-feedback").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "导入中...", async () => {
                saveDraft();
                const taskId = taskIdEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("导入中", "", "正在写入手工补录反馈，并回刷当前任务与实验榜。");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/import-feedback`, buildFeedbackPayload());
                renderOutput(result);
                await queryTaskFeedback();
                await refreshExperiments();
                setStatus("导入完成", "", "反馈已补录完成，当前任务和实验榜都已回刷。");
              });
            });

            document.getElementById("run-feedback-sync").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "同步中...", async () => {
                saveDraft();
                const taskId = taskIdEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("同步中", "", "正在为当前任务拉取自动反馈，并回刷反馈快照与实验榜。");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/run-feedback-sync`, buildFeedbackSyncPayload());
                renderOutput(result);
                await queryTaskFeedback();
                await refreshExperiments();
                setStatus(`同步完成 (${result.imported_count})`, "", `自动同步完成，新增 ${result.imported_count} 条反馈记录。`);
              });
            });

            document.getElementById("queue-feedback-sync").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "入队中...", async () => {
                saveDraft();
                const taskId = taskIdEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("入队中", "", "正在把当前任务的反馈同步动作送入队列。");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/enqueue-feedback-sync`, buildFeedbackSyncPayload());
                renderOutput(result);
                setStatus(result.enqueued ? "已入队" : "已在队列中", "", result.enqueued ? "当前任务的反馈同步已入队。" : "当前任务已经在反馈同步队列里。");
              });
            });

            document.getElementById("queue-recent-feedback-sync").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "扫描中...", async () => {
                saveDraft();
                setStatus("扫描中", "", "正在扫描最近已入草稿任务，并把缺反馈的任务入队。");
                const result = await request("POST", "/internal/v1/feedback/enqueue-recent-sync", buildRecentFeedbackSyncPayload());
                renderOutput(result);
                setStatus(`已扫描 ${result.requested_count} 个任务`, "", `最近草稿扫描完成，共入队 ${result.enqueued_count} 个任务。`);
              });
            });

            document.getElementById("import-feedback-csv").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "导入中...", async () => {
                saveDraft();
                if (!feedbackCsvEl.value.trim()) throw new Error("请先粘贴 CSV 内容");
                setStatus("批量导入中", "", "正在按 CSV 批量写入反馈，并回刷实验榜。");
                const result = await request("POST", "/internal/v1/feedback/import-csv", buildFeedbackCsvPayload());
                renderOutput(result);
                if (taskIdEl.value.trim()) {
                  await queryTaskFeedback();
                }
                await refreshExperiments();
                setStatus(`批量导入完成 (${result.imported_count})`, "", `CSV 导入完成，共写入 ${result.imported_count} 条反馈。`);
              });
            });

            document.getElementById("create-asset").addEventListener("click", (event) => {
              withButtonBusy(event.currentTarget, "创建中...", async () => {
                saveDraft();
                if (!assetTypeEl.value.trim() || !assetTitleEl.value.trim() || !assetContentEl.value.trim()) {
                  throw new Error("请填写资产类型、标题和内容");
                }
                setStatus("创建资产中", "", "正在创建风格资产，并回刷资产库。");
                const result = await request("POST", "/internal/v1/style-assets", buildStyleAssetPayload());
                renderOutput(result);
                await refreshStyleAssets();
                setStatus("创建完成", "", "风格资产已创建完成，可以继续整理其他稳定写法。");
              });
            });

            document.getElementById("clear-output").addEventListener("click", () => {
              setStatus("已清空", "", "已清空最近一次输出；当前列表内容会保留。");
              renderOutput("等待输入...");
            });

            [taskIdEl, generationIdEl, operatorEl, syncDayOffsetsEl, syncLimitEl].forEach((element) => {
              const eventName = element === taskIdEl ? "input" : "change";
              element.addEventListener(eventName, () => {
                if (element === taskIdEl) {
                  currentTaskFeedbackCount = 0;
                  taskFeedbackListEl.innerHTML = '<div class="hint">task_id 已变更。点击“查反馈”加载这条任务的反馈快照。</div>';
                }
                saveDraft();
                renderOverview();
              });
            });

            loadDraft();
            renderOverview();
            Promise.allSettled([refreshExperiments(), refreshStyleAssets()]).then((results) => {
              const failed = results.find((item) => item.status === "rejected");
              if (!failed) return;
              setStatus("加载失败", "warn", failed.reason?.message || "初始数据加载失败，详见输出区域。");
              renderOutput(failed.reason?.message || "初始数据加载失败。");
            });
          </script>
        </body>
        </html>
        """
    )
    return (
        html.replace("__ADMIN_NAV_STYLES__", admin_section_nav_styles()).replace(
            "__ADMIN_SECTION_NAV__", admin_section_nav("feedback")
        )
    )
