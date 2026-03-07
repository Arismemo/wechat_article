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
