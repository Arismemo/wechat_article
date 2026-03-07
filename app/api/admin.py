from __future__ import annotations

from textwrap import dedent

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter()


@router.get("/admin/phase2", response_class=HTMLResponse, tags=["admin"])
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

            const request = async (method, path, body) => {
              const token = tokenEl.value.trim();
              if (!token) throw new Error("缺少 Bearer Token");
              const response = await fetch(path, {
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
              trigger: "manual-ui"
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


@router.get("/admin/phase5", response_class=HTMLResponse, tags=["admin"])
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
              gap: 12px;
            }
            .task-card, .detail-card, .generation-card, .audit-card {
              background: #fffdf9;
              border: 1px solid var(--line);
              border-radius: 18px;
              padding: 14px;
            }
            .task-card h3, .detail-card h3, .generation-card h3 {
              margin: 0 0 8px;
              font-size: 16px;
              line-height: 1.45;
            }
            .task-card .meta, .detail-card .meta {
              display: grid;
              gap: 4px;
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
              gap: 12px;
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
            @media (max-width: 1024px) {
              .layout {
                grid-template-columns: 1fr;
              }
            }
            @media (max-width: 720px) {
              .hero h1 { font-size: 30px; }
              .actions { grid-template-columns: 1fr; }
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
              <p>这个工作台把最近任务、源文与 Brief、生成稿版本、审稿风险、审计轨迹和手动操作放到一页里。目标是做到不翻日志，也能完成查看、重跑、重生成和推草稿。</p>
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
                  </div>
                  <div class="actions">
                    <button id="queue-url">提交链接并入队 Phase4</button>
                    <button id="run-url">提交链接并同步执行 Phase4</button>
                    <button id="load-workspace" class="secondary">加载工作台</button>
                    <button id="queue-phase3" class="secondary">入队 Phase3</button>
                    <button id="run-phase4" class="secondary">同步执行 Phase4</button>
                    <button id="queue-phase4" class="secondary">入队 Phase4</button>
                    <button id="push-draft" class="warn">推送微信草稿</button>
                    <button id="clear" class="danger">清空输出</button>
                  </div>
                  <p class="hint">推荐 SOP：先加载工作台看最新状态和风险，再决定是回补 Phase3、重生成，还是直接推送草稿。`推送微信草稿` 只会推最新 accepted generation。</p>
                </section>

                <section class="panel">
                  <h2>人工审核 SOP</h2>
                  <div class="meta">
                    <div>1. 先看任务状态、风险分和最近一次审稿结论，确认是 `review_passed`、`needs_regenerate` 还是 `needs_manual_review`。</div>
                    <div>2. 再看源文摘要、Brief 新角度、最近两版生成稿，判断问题是研究输入不足，还是写稿结构和表达有偏差。</div>
                    <div>3. 如果研究层明显缺信息，先入队 Phase3；如果 Brief 已够，但稿子不行，直接重跑 Phase4。</div>
                    <div>4. 只有在 latest generation 为 accepted 且风险可接受时，才推微信草稿箱。</div>
                    <div>5. 最后核对审计轨迹，确认这次手动操作已经落日志，避免重复触发。</div>
                  </div>
                </section>

                <section class="panel">
                  <h2>最近任务</h2>
                  <div class="actions" style="margin-top: 0;">
                    <button id="refresh-recent" class="secondary">刷新最近任务</button>
                  </div>
                  <p class="hint">卡片按钮会直接填入 `task_id` 并执行对应动作。工作台详情会展示源文、Brief、生成稿版本与审计轨迹。</p>
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
            const deviceEl = document.getElementById("device");
            const outputEl = document.getElementById("output");
            const statusEl = document.getElementById("status");
            const recentListEl = document.getElementById("recent-list");
            const workspaceEl = document.getElementById("workspace");

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
            };

            const saveDraft = () => {
              localStorage.setItem("phase5_console_token", tokenEl.value.trim());
              localStorage.setItem("phase5_console_url", urlEl.value.trim());
              localStorage.setItem("phase5_console_task", taskEl.value.trim());
            };

            const setStatus = (text) => {
              statusEl.textContent = text;
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

            const request = async (method, path, body) => {
              saveDraft();
              const response = await fetch(path, {
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

            const renderWorkspace = (workspace) => {
              const latest = workspace.generations[0];
              const latestReview = latest?.review;
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
              return data;
            };

            const setTaskId = (taskId) => {
              taskEl.value = taskId;
              saveDraft();
            };

            const refreshRecent = async () => {
              const tasks = await request("GET", "/api/v1/tasks?limit=12");
              if (!Array.isArray(tasks) || tasks.length === 0) {
                recentListEl.innerHTML = '<div class="hint">最近没有任务。</div>';
                return;
              }
              recentListEl.innerHTML = tasks.map((task) => `
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
                    <button data-action="push" data-task-id="${escapeHtml(task.task_id)}" class="warn">推草稿</button>
                  </div>
                </div>
              `).join("");
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
