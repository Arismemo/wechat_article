from __future__ import annotations

from textwrap import dedent

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

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
    return dedent(
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
              font-family: "PingFang SC", "Noto Serif SC", serif;
              color: var(--text);
              background:
                radial-gradient(circle at top left, rgba(255, 233, 191, 0.55), transparent 24%),
                radial-gradient(circle at bottom right, rgba(182, 224, 209, 0.45), transparent 28%),
                linear-gradient(140deg, #f0e8db 0%, #f7f3eb 42%, #ece4d7 100%);
              min-height: 100vh;
            }
            main {
              max-width: 1280px;
              margin: 0 auto;
              padding: 32px 20px 52px;
            }
            .hero {
              display: grid;
              gap: 10px;
              margin-bottom: 20px;
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
            .grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
              gap: 12px;
            }
            .grid.single {
              grid-template-columns: 1fr;
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
            @media (max-width: 1024px) {
              .layout {
                grid-template-columns: 1fr;
              }
            }
            @media (max-width: 720px) {
              main { padding: 22px 14px 36px; }
              .panel { padding: 16px; border-radius: 20px; }
              .hero h1 { font-size: 30px; }
              .actions { grid-template-columns: 1fr; }
              .action-grid { grid-template-columns: 1fr; }
              .task-actions { flex-direction: column; }
              .task-actions button { width: 100%; }
            }
          </style>
        </head>
        <body>
          <main>
            <section class="hero">
              <span class="eyebrow">PHASE 5 ADMIN CONSOLE</span>
              <h1>任务看板、人工审核与手动干预</h1>
              <p>看任务，做决定，推草稿。不翻日志，也能完成日常审核。</p>
            </section>

            <section class="layout">
              <div class="stack">
                <section class="panel">
                  <h2>认证与操作</h2>
                  <div class="grid single">
                    <div>
                      <label for="token">Bearer Token</label>
                      <input id="token" type="password" placeholder="输入 API_BEARER_TOKEN" />
                    </div>
                    <div>
                      <label for="device">device_id</label>
                      <input id="device" type="text" value="phase5-console" />
                    </div>
                    <div>
                      <label for="url">微信文章链接</label>
                      <input id="url" type="url" placeholder="https://mp.weixin.qq.com/s/..." />
                    </div>
                    <div>
                      <label for="task">task_id</label>
                      <input id="task" type="text" placeholder="f703c3ef-..." />
                    </div>
                    <div>
                      <label for="review-note">人工审核备注</label>
                      <textarea id="review-note" placeholder="会写入 audit log，例如：结构已达标，可人工放行；或：观点重复，退回重写。"></textarea>
                    </div>
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
                  <p class="hint">先加载详情，再决定：重跑、通过、驳回，或者推稿。</p>
                </section>

                <section class="panel">
                  <h2>最短操作</h2>
                  <div class="meta">
                    <div>1. 刷新最近任务，点一条卡片。</div>
                    <div>2. 右边先看状态、最新一稿和风险。</div>
                    <div>3. 可用就通过，不行就驳回或重跑。</div>
                    <div>4. 最后再决定是否推草稿。</div>
                  </div>
                  <details class="fold">
                    <summary>展开完整规则</summary>
                    <div class="meta">
                      <div>研究层明显缺信息时，先入队 Phase3；Brief 已够但稿子不行时，直接重跑 Phase4。</div>
                      <div>已推草稿的版本不允许再驳回；人工审核备注会写入 audit log。</div>
                      <div>只有 latest generation 已 accepted 且推草稿许可允许时，才推微信草稿箱。</div>
                    </div>
                  </details>
                </section>

                <section class="panel">
                  <h2>任务看板</h2>
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
                  <p class="hint">默认先把还没收口的任务放到前面。</p>
                  <div class="summary-strip" id="recent-summary"></div>
                  <div class="board" id="recent-list">
                    <div class="hint">等待加载最近任务...</div>
                  </div>
                </section>
              </div>

              <div class="stack">
                <section class="panel">
                  <span class="status" id="status">空闲</span>
                  <h2>任务工作台</h2>
                  <div class="workspace" id="workspace">
                    <div class="hint">先输入 Bearer Token，再加载 task_id 或刷新最近任务。</div>
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
            const tokenEl = document.getElementById("token");
            const urlEl = document.getElementById("url");
            const taskEl = document.getElementById("task");
            const reviewNoteEl = document.getElementById("review-note");
            const deviceEl = document.getElementById("device");
            const outputEl = document.getElementById("output");
            const statusEl = document.getElementById("status");
            const recentListEl = document.getElementById("recent-list");
            const recentSummaryEl = document.getElementById("recent-summary");
            const recentStatusEl = document.getElementById("recent-status-filter");
            const recentLimitEl = document.getElementById("recent-limit");
            const recentActiveEl = document.getElementById("recent-active-only");
            const workspaceEl = document.getElementById("workspace");
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

            const escapeHtml = (value) => {
              return String(value ?? "")
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#39;");
            };

            const loadDraft = () => {
              tokenEl.value = localStorage.getItem("phase5_console_token") || "";
              urlEl.value = localStorage.getItem("phase5_console_url") || "";
              taskEl.value = localStorage.getItem("phase5_console_task") || "";
              reviewNoteEl.value = localStorage.getItem("phase5_console_review_note") || "";
              recentStatusEl.value = localStorage.getItem("phase5_console_recent_status") || "";
              recentLimitEl.value = localStorage.getItem("phase5_console_recent_limit") || "18";
              recentActiveEl.checked = (localStorage.getItem("phase5_console_recent_active_only") || "true") !== "false";
            };

            const saveDraft = () => {
              localStorage.setItem("phase5_console_token", tokenEl.value.trim());
              localStorage.setItem("phase5_console_url", urlEl.value.trim());
              localStorage.setItem("phase5_console_task", taskEl.value.trim());
              localStorage.setItem("phase5_console_review_note", reviewNoteEl.value.trim());
              localStorage.setItem("phase5_console_recent_status", recentStatusEl.value);
              localStorage.setItem("phase5_console_recent_limit", recentLimitEl.value);
              localStorage.setItem("phase5_console_recent_active_only", recentActiveEl.checked ? "true" : "false");
            };

            const setStatus = (text) => {
              statusEl.textContent = text;
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

            const requireToken = () => {
              const token = tokenEl.value.trim();
              if (!token) throw new Error("请先输入 Bearer Token");
              return token;
            };
            const apiUrl = (path) => new URL(path, window.location.origin).toString();

            const request = async (method, path, body) => {
              saveDraft();
              const response = await fetch(apiUrl(path), {
                method,
                headers: {
                  "Authorization": `Bearer ${requireToken()}`,
                  "Content-Type": "application/json"
                },
                body: body ? JSON.stringify(body) : undefined,
              });
              const text = await response.text();
              let data;
              try {
                data = text ? JSON.parse(text) : {};
              } catch {
                data = { raw: text };
              }
              if (!response.ok) {
                throw new Error(data.detail || data.raw || `HTTP ${response.status}`);
              }
              return data;
            };

            const formatDate = (value) => value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "未知";
            const truncate = (value, limit = 220) => {
              const text = String(value || "");
              return text.length > limit ? `${text.slice(0, limit)}...` : text;
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
                          <div><strong>摘要</strong> ${escapeHtml(generation.digest || "暂无")}</div>
                        </div>
                        <details>
                          <summary>展开审稿风险与建议</summary>
                          <pre>${escapeHtml(JSON.stringify(generation.review || {}, null, 2))}</pre>
                        </details>
                        <details>
                          <summary>展开 Markdown 正文</summary>
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

              if (latestReview && latestReview.final_decision) {
                setStatus(`已加载 · 最新结论 ${latestReview.final_decision}`);
              } else {
                setStatus(`已加载 · ${workspace.status}`);
              }
            };

            const fetchWorkspace = async (taskId) => {
              if (!taskId) throw new Error("请先输入 task_id");
              const data = await request("GET", `/api/v1/tasks/${taskId}/workspace`);
              renderWorkspace(data);
              renderOutput(data);
              scrollWorkspaceIntoView();
              return data;
            };

            const setTaskId = (taskId) => {
              taskEl.value = taskId;
              saveDraft();
            };

            const renderRecentBoard = (tasks) => {
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
              const params = new URLSearchParams();
              params.set("limit", String(Math.min(Math.max(Number(recentLimitEl.value) || 18, 1), 50)));
              if (recentActiveEl.checked) {
                params.set("active_only", "true");
              }
              if (recentStatusEl.value) {
                params.set("status", recentStatusEl.value);
              }
              const tasks = await request("GET", `/api/v1/tasks?${params.toString()}`);
              renderRecentBoard(tasks);
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

            document.getElementById("queue-url").addEventListener("click", async () => {
              try {
                setStatus("入队中");
                const result = await request("POST", "/internal/v1/phase4/ingest-and-enqueue", buildIngestPayload());
                setTaskId(result.task_id);
                renderOutput(result);
                await refreshRecent();
                setStatus(result.status || "queued");
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("run-url").addEventListener("click", async () => {
              try {
                setStatus("执行中");
                const result = await request("POST", "/internal/v1/phase4/ingest-and-run", buildIngestPayload());
                setTaskId(result.task_id);
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(result.task_id);
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("load-workspace").addEventListener("click", async () => {
              try {
                await fetchWorkspace(taskEl.value.trim());
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("queue-phase3").addEventListener("click", async () => {
              try {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("入队 Phase3");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/enqueue-phase3`);
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("run-phase4").addEventListener("click", async () => {
              try {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("执行 Phase4");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/run-phase4`);
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("queue-phase4").addEventListener("click", async () => {
              try {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("入队 Phase4");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/enqueue-phase4`);
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("approve-generation").addEventListener("click", async () => {
              try {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("人工通过");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/approve-latest-generation`, buildManualReviewPayload());
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("reject-generation").addEventListener("click", async () => {
              try {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("人工驳回重写");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/reject-latest-generation`, buildManualReviewPayload());
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("allow-push").addEventListener("click", async () => {
              try {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("允许推稿");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/allow-wechat-draft-push`, buildManualReviewPayload());
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("block-push").addEventListener("click", async () => {
              try {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("禁止推草稿");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/block-wechat-draft-push`, buildManualReviewPayload());
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("push-draft").addEventListener("click", async () => {
              try {
                const taskId = taskEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("推送草稿中");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/push-wechat-draft`);
                renderOutput(result);
                await refreshRecent();
                await fetchWorkspace(taskId);
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("clear").addEventListener("click", () => {
              setStatus("空闲");
              renderOutput("等待输入...");
              workspaceEl.innerHTML = '<div class="hint">工作台已清空。</div>';
            });

            document.getElementById("refresh-recent").addEventListener("click", async () => {
              try {
                setStatus("刷新列表中");
                await refreshRecent();
                setStatus("空闲");
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
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

              try {
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
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            loadDraft();
            if (tokenEl.value.trim()) {
              refreshRecent().catch(() => {
                recentListEl.innerHTML = '<div class="hint">最近任务加载失败，请确认 Bearer Token 后重试。</div>';
              });
            } else {
              recentListEl.innerHTML = '<div class="hint">先输入 Bearer Token，再点“刷新最近任务”。</div>';
            }
          </script>
        </body>
        </html>
        """
    )


@router.get("/admin/phase6", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def phase6_console() -> str:
    return dedent(
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
              --ink: #163028;
              --shadow: 0 18px 46px rgba(24, 42, 29, 0.1);
            }
            * { box-sizing: border-box; }
            body {
              margin: 0;
              color: var(--text);
              font-family: "PingFang SC", "Noto Serif SC", serif;
              background:
                radial-gradient(circle at top left, rgba(243, 250, 214, 0.55), transparent 24%),
                radial-gradient(circle at right bottom, rgba(197, 234, 219, 0.45), transparent 28%),
                linear-gradient(140deg, #e9eee7 0%, #f3f6f0 42%, #e7eee5 100%);
              min-height: 100vh;
            }
            main {
              max-width: 1280px;
              margin: 0 auto;
              padding: 32px 20px 48px;
            }
            .hero {
              display: grid;
              gap: 10px;
              margin-bottom: 20px;
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
              font-size: 40px;
              line-height: 1.04;
            }
            .hero p {
              margin: 0;
              max-width: 860px;
              color: var(--muted);
              line-height: 1.75;
            }
            .layout {
              display: grid;
              grid-template-columns: 420px minmax(0, 1fr);
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
            .grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
              gap: 12px;
            }
            .grid.single {
              grid-template-columns: 1fr;
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
            button:hover { background: var(--accent-dark); transform: translateY(-1px); }
            button.secondary { background: #d2e1d5; color: var(--ink); }
            button.danger { background: var(--danger); color: #fff7f3; }
            .actions {
              display: flex;
              flex-wrap: wrap;
              gap: 10px;
              margin-top: 14px;
            }
            .actions button {
              width: auto;
              min-width: 140px;
            }
            .status {
              display: inline-block;
              padding: 6px 10px;
              border-radius: 999px;
              background: rgba(43, 111, 88, 0.14);
              color: var(--accent-dark);
              font-size: 12px;
              margin-bottom: 12px;
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
            .card {
              border: 1px solid var(--line);
              border-radius: 18px;
              padding: 14px;
              background: #fffefb;
              display: grid;
              align-content: start;
              gap: 8px;
              min-width: 0;
              position: relative;
              isolation: isolate;
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
            @media (max-width: 980px) {
              .layout { grid-template-columns: 1fr; }
            }
            @media (max-width: 720px) {
              main { padding: 22px 14px 36px; }
              .panel { padding: 16px; border-radius: 20px; }
              .hero h1 { font-size: 30px; }
              .actions { flex-direction: column; }
              .actions button { width: 100%; }
            }
          </style>
        </head>
        <body>
          <main>
            <section class="hero">
              <span class="eyebrow">PHASE 6 FEEDBACK LOOP</span>
              <h1>Phase 6 反馈台</h1>
              <p>这里回收发布后的数据：导入反馈、自动同步、看实验榜、存风格资产。</p>
            </section>

            <section class="layout">
              <div class="stack">
                <section class="panel">
                  <h2>认证与任务</h2>
                  <div class="grid single">
                    <div>
                      <label for="token">Bearer Token</label>
                      <input id="token" type="password" placeholder="输入 API_BEARER_TOKEN" />
                    </div>
                    <div>
                      <label for="task-id">Task ID</label>
                      <input id="task-id" type="text" placeholder="f703c3ef-..." />
                    </div>
                    <div>
                      <label for="generation-id">Generation ID（可选）</label>
                      <input id="generation-id" type="text" placeholder="默认取 latest accepted / latest" />
                    </div>
                    <div>
                      <label for="operator">操作人</label>
                      <input id="operator" type="text" value="admin-console" />
                    </div>
                  </div>
                  <div class="actions">
                    <button id="query-feedback" class="secondary">查反馈</button>
                    <button id="refresh-experiments" class="secondary">查实验</button>
                    <button id="refresh-assets" class="secondary">查资产</button>
                    <button id="clear-output" class="danger">清空</button>
                  </div>
                </section>

                <section class="panel">
                  <h2>自动同步</h2>
                  <div class="grid">
                    <div>
                      <label for="sync-day-offsets">同步窗口（逗号分隔）</label>
                      <input id="sync-day-offsets" type="text" value="1,3,7" />
                    </div>
                    <div>
                      <label for="sync-limit">扫描最近草稿数</label>
                      <input id="sync-limit" type="number" min="1" max="100" value="20" />
                    </div>
                  </div>
                  <div class="actions">
                    <button id="run-feedback-sync">立即同步</button>
                    <button id="queue-feedback-sync" class="secondary">入队同步</button>
                    <button id="queue-recent-feedback-sync" class="secondary">扫描入队</button>
                  </div>
                  <p class="hint">自动同步只处理已经成功入草稿的任务。</p>
                </section>

                <section class="panel">
                  <h2>导入反馈</h2>
                  <div class="grid">
                    <div>
                      <label for="day-offset">观察窗口</label>
                      <select id="day-offset">
                        <option value="1">T+1</option>
                        <option value="3">T+3</option>
                        <option value="7">T+7</option>
                      </select>
                    </div>
                    <div>
                      <label for="snapshot-at">快照时间（ISO，可选）</label>
                      <input id="snapshot-at" type="text" placeholder="2026-03-08T10:00:00+08:00" />
                    </div>
                    <div>
                      <label for="read-count">阅读数</label>
                      <input id="read-count" type="number" min="0" placeholder="1200" />
                    </div>
                    <div>
                      <label for="like-count">点赞数</label>
                      <input id="like-count" type="number" min="0" placeholder="86" />
                    </div>
                    <div>
                      <label for="share-count">转发数</label>
                      <input id="share-count" type="number" min="0" placeholder="14" />
                    </div>
                    <div>
                      <label for="comment-count">评论数</label>
                      <input id="comment-count" type="number" min="0" placeholder="3" />
                    </div>
                    <div>
                      <label for="click-rate">点击率（可选）</label>
                      <input id="click-rate" type="number" min="0" step="0.0001" placeholder="0.1825" />
                    </div>
                    <div>
                      <label for="media-id">media_id（可选）</label>
                      <input id="media-id" type="text" placeholder="默认回填最近草稿 media_id" />
                    </div>
                  </div>
                  <div style="margin-top: 12px;">
                    <label for="feedback-notes">导入备注</label>
                    <textarea id="feedback-notes" placeholder="例如：后台手工抄录 T+1 数据"></textarea>
                  </div>
                  <div class="actions">
                    <button id="import-feedback">导入</button>
                  </div>
                  <p class="hint">不填 Generation ID 时，默认取最新 accepted generation。</p>
                </section>

                <section class="panel">
                  <h2>更多工具</h2>
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
                      <div>
                        <label for="asset-type">资产类型</label>
                        <input id="asset-type" type="text" value="opening_hook" />
                      </div>
                      <div>
                        <label for="asset-title">标题</label>
                        <input id="asset-title" type="text" placeholder="反直觉开头模板" />
                      </div>
                      <div>
                        <label for="asset-tags">标签（逗号分隔）</label>
                        <input id="asset-tags" type="text" placeholder="技术科普,误区纠偏" />
                      </div>
                      <div>
                        <label for="asset-weight">权重</label>
                        <input id="asset-weight" type="number" min="0.1" step="0.1" value="1.0" />
                      </div>
                    </div>
                    <div style="margin-top: 12px;">
                      <label for="asset-content">资产内容</label>
                      <textarea id="asset-content" placeholder="写下经过验证的标题模板、开头结构、段落骨架或转场句式"></textarea>
                    </div>
                    <div style="margin-top: 12px;">
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
                  <h2>输出</h2>
                  <span class="status" id="status">空闲</span>
                  <pre id="output">等待输入...</pre>
                </section>

                <section class="panel">
                  <h2>任务反馈快照</h2>
                  <p class="hint">看这条任务已经回收到了哪些反馈。</p>
                  <div class="list" id="task-feedback-list">
                    <div class="hint">等待查询任务反馈...</div>
                  </div>
                </section>

                <section class="panel">
                  <h2>Prompt 实验榜</h2>
                  <p class="hint">看哪套 prompt 更稳。</p>
                  <div class="list" id="experiment-list">
                    <div class="hint">等待加载实验榜...</div>
                  </div>
                </section>

                <section class="panel">
                  <h2>风格资产库</h2>
                  <p class="hint">看哪些写法值得留下来复用。</p>
                  <div class="list" id="style-asset-list">
                    <div class="hint">等待加载风格资产...</div>
                  </div>
                </section>
              </div>
            </section>
          </main>

          <script>
            const tokenEl = document.getElementById("token");
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
            const taskFeedbackListEl = document.getElementById("task-feedback-list");
            const experimentListEl = document.getElementById("experiment-list");
            const styleAssetListEl = document.getElementById("style-asset-list");

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

            const setStatus = (value) => { statusEl.textContent = value; };
            const renderOutput = (value) => {
              outputEl.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
            };
            const apiUrl = (path) => new URL(path, window.location.origin).toString();

            const loadDraft = () => {
              tokenEl.value = localStorage.getItem("phase6_console_token") || "";
              taskIdEl.value = localStorage.getItem("phase6_console_task_id") || "";
              generationIdEl.value = localStorage.getItem("phase6_console_generation_id") || "";
              operatorEl.value = localStorage.getItem("phase6_console_operator") || "admin-console";
              syncDayOffsetsEl.value = localStorage.getItem("phase6_console_sync_day_offsets") || "1,3,7";
              syncLimitEl.value = localStorage.getItem("phase6_console_sync_limit") || "20";
            };

            const saveDraft = () => {
              localStorage.setItem("phase6_console_token", tokenEl.value.trim());
              localStorage.setItem("phase6_console_task_id", taskIdEl.value.trim());
              localStorage.setItem("phase6_console_generation_id", generationIdEl.value.trim());
              localStorage.setItem("phase6_console_operator", operatorEl.value.trim());
              localStorage.setItem("phase6_console_sync_day_offsets", syncDayOffsetsEl.value.trim());
              localStorage.setItem("phase6_console_sync_limit", syncLimitEl.value.trim());
            };

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
              if (!items.length) {
                taskFeedbackListEl.innerHTML = '<div class="hint">当前任务还没有反馈记录。</div>';
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
            };

            const renderExperiments = (items) => {
              if (!Array.isArray(items) || !items.length) {
                experimentListEl.innerHTML = '<div class="hint">还没有实验样本。</div>';
                return;
              }
              experimentListEl.innerHTML = items.map((item) => `
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
            };

            const renderStyleAssets = (items) => {
              if (!Array.isArray(items) || !items.length) {
                styleAssetListEl.innerHTML = '<div class="hint">还没有风格资产。</div>';
                return;
              }
              styleAssetListEl.innerHTML = items.map((item) => `
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
            };

            const queryTaskFeedback = async () => {
              const taskId = taskIdEl.value.trim();
              if (!taskId) throw new Error("请先输入 task_id");
              const payload = await request("GET", `/api/v1/tasks/${taskId}/feedback`);
              renderTaskFeedback(payload);
              return payload;
            };

            const refreshExperiments = async () => {
              const items = await request("GET", "/api/v1/feedback/experiments?limit=12");
              renderExperiments(items);
              return items;
            };

            const refreshStyleAssets = async () => {
              const items = await request("GET", "/api/v1/feedback/style-assets?limit=12");
              renderStyleAssets(items);
              return items;
            };

            document.getElementById("query-feedback").addEventListener("click", async () => {
              try {
                saveDraft();
                setStatus("查反馈");
                const payload = await queryTaskFeedback();
                renderOutput(payload);
                setStatus("完成");
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("refresh-experiments").addEventListener("click", async () => {
              try {
                saveDraft();
                setStatus("查实验");
                const items = await refreshExperiments();
                renderOutput(items);
                setStatus("完成");
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("refresh-assets").addEventListener("click", async () => {
              try {
                saveDraft();
                setStatus("查资产");
                const items = await refreshStyleAssets();
                renderOutput(items);
                setStatus("完成");
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("import-feedback").addEventListener("click", async () => {
              try {
                saveDraft();
                const taskId = taskIdEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("导入反馈中");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/import-feedback`, buildFeedbackPayload());
                renderOutput(result);
                await queryTaskFeedback();
                await refreshExperiments();
                setStatus("导入完成");
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("run-feedback-sync").addEventListener("click", async () => {
              try {
                saveDraft();
                const taskId = taskIdEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("自动同步反馈中");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/run-feedback-sync`, buildFeedbackSyncPayload());
                renderOutput(result);
                await queryTaskFeedback();
                await refreshExperiments();
                setStatus(`自动同步完成 (${result.imported_count})`);
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("queue-feedback-sync").addEventListener("click", async () => {
              try {
                saveDraft();
                const taskId = taskIdEl.value.trim();
                if (!taskId) throw new Error("请先输入 task_id");
                setStatus("反馈同步入队中");
                const result = await request("POST", `/internal/v1/tasks/${taskId}/enqueue-feedback-sync`, buildFeedbackSyncPayload());
                renderOutput(result);
                setStatus(result.enqueued ? "已入队" : "已在队列中");
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("queue-recent-feedback-sync").addEventListener("click", async () => {
              try {
                saveDraft();
                setStatus("扫描最近草稿中");
                const result = await request("POST", "/internal/v1/feedback/enqueue-recent-sync", buildRecentFeedbackSyncPayload());
                renderOutput(result);
                setStatus(`已扫描 ${result.requested_count} 个任务，入队 ${result.enqueued_count} 个`);
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("import-feedback-csv").addEventListener("click", async () => {
              try {
                saveDraft();
                if (!feedbackCsvEl.value.trim()) throw new Error("请先粘贴 CSV 内容");
                setStatus("批量导入中");
                const result = await request("POST", "/internal/v1/feedback/import-csv", buildFeedbackCsvPayload());
                renderOutput(result);
                if (taskIdEl.value.trim()) {
                  await queryTaskFeedback();
                }
                await refreshExperiments();
                setStatus(`批量导入完成 (${result.imported_count})`);
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("create-asset").addEventListener("click", async () => {
              try {
                saveDraft();
                if (!assetTypeEl.value.trim() || !assetTitleEl.value.trim() || !assetContentEl.value.trim()) {
                  throw new Error("请填写资产类型、标题和内容");
                }
                setStatus("创建风格资产");
                const result = await request("POST", "/internal/v1/style-assets", buildStyleAssetPayload());
                renderOutput(result);
                await refreshStyleAssets();
                setStatus("创建完成");
              } catch (error) {
                setStatus("失败");
                renderOutput(error.message || String(error));
              }
            });

            document.getElementById("clear-output").addEventListener("click", () => {
              setStatus("空闲");
              renderOutput("等待输入...");
            });

            loadDraft();
            if (tokenEl.value.trim()) {
              Promise.allSettled([refreshExperiments(), refreshStyleAssets()]).catch(() => {});
            }
          </script>
        </body>
        </html>
        """
    )
