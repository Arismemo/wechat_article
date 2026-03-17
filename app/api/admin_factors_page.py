"""因子库管理页面 — 独立 HTML 页面。"""

from __future__ import annotations

from textwrap import dedent

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.api.admin_ui import admin_overview_card, admin_overview_strip, render_admin_page
from app.core.security import verify_admin_basic_auth

router = APIRouter()


@router.get("/admin/factors", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def admin_factors_page() -> str:
    overview_html = admin_overview_strip(
        "因子库概览",
        "".join([
            admin_overview_card("有效因子", "0", "已入库可用于写稿的因子。", value_id="stat-active"),
            admin_overview_card("草稿", "0", "创建但尚未激活的因子。", value_id="stat-draft"),
            admin_overview_card("待审核", "0", "等待人工审核的因子。", highlight=True, value_id="stat-pending"),
            admin_overview_card("使用次数", "0", "因子被用于任务的累计次数。", value_id="stat-usage"),
        ]),
    )

    html = dedent("""\
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>因子库</title>
      <style>
        __ADMIN_SHARED_STYLES__

        /* ── 因子库页面专用样式 ── */
        .factors-shell { display: grid; gap: 20px; }
        .factors-grid {
          display: grid;
          grid-template-columns: minmax(0, 1.6fr) minmax(320px, .9fr);
          gap: 20px; align-items: start;
        }
        /* 维度颜色 */
        .dim-opening   { --dim-color: #7c3aed; --dim-bg: rgba(124,58,237,.1); }
        .dim-structure  { --dim-color: #3b82f6; --dim-bg: rgba(59,130,246,.1); }
        .dim-rhetoric   { --dim-color: #10b981; --dim-bg: rgba(16,185,129,.1); }
        .dim-rhythm     { --dim-color: #f97316; --dim-bg: rgba(249,115,22,.1); }
        .dim-layout     { --dim-color: #ec4899; --dim-bg: rgba(236,72,153,.1); }
        .dim-closing    { --dim-color: #06b6d4; --dim-bg: rgba(6,182,212,.1); }

        .dim-badge {
          display: inline-flex; align-items: center;
          padding: 3px 10px; border-radius: 999px;
          font-size: 11px; font-weight: 700;
          background: var(--dim-bg, var(--primary-soft));
          color: var(--dim-color, var(--primary));
        }
        .status-badge {
          display: inline-flex; align-items: center;
          padding: 3px 8px; border-radius: 999px;
          font-size: 11px; font-weight: 600;
        }
        .status-badge.active  { background: var(--success-soft); color: #059669; }
        .status-badge.draft   { background: var(--bg-input); color: var(--text-secondary); border: 1px solid var(--border); }
        .status-badge.pending { background: var(--warning-soft); color: #B45309; }
        .status-badge.deprecated { background: var(--danger-soft); color: var(--danger); }

        /* 因子卡片网格 */
        .factor-cards {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 12px;
        }
        .factor-card {
          display: grid; gap: 10px; padding: 16px;
          border: 1px solid var(--border); border-radius: var(--radius-md);
          background: var(--bg-card); box-shadow: var(--shadow-card);
          cursor: pointer;
          transition: all var(--transition);
        }
        .factor-card:hover {
          border-color: var(--primary);
          box-shadow: 0 4px 12px rgba(59,130,246,.08);
          transform: translateY(-2px);
        }
        .factor-card-head {
          display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;
        }
        .factor-card h4 { margin: 0; font-size: 15px; font-weight: 700; line-height: 1.4; }
        .factor-card-badges { display: flex; flex-wrap: wrap; gap: 6px; }
        .factor-card-desc {
          margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.7;
          display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
        }
        .factor-card-footer {
          display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
          font-size: 12px; color: var(--text-secondary);
          border-top: 1px solid var(--border-light); padding-top: 8px;
        }
        .factor-card-tags {
          display: flex; flex-wrap: wrap; gap: 4px;
        }
        .factor-tag {
          display: inline-flex; padding: 2px 6px; border-radius: 4px;
          background: var(--bg-input); border: 1px solid var(--border);
          font-size: 11px; color: var(--text-secondary);
        }

        /* 待审核卡片 */
        .pending-card {
          display: grid; gap: 10px; padding: 14px;
          border: 1px dashed rgba(245,158,11,.4); border-radius: var(--radius-md);
          border-left: 4px solid var(--warning);
          background: linear-gradient(135deg, var(--warning-soft), var(--bg-card));
        }
        .pending-card h4 { margin: 0; font-size: 14px; font-weight: 600; line-height: 1.4; }
        .pending-card-desc {
          margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.7;
          display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
        }
        .pending-card-actions { display: flex; flex-wrap: wrap; gap: 6px; }
        .pending-card-source {
          margin: 0; font-size: 12px; color: var(--text-secondary);
        }
        .pending-card-source a { color: var(--primary); text-decoration: none; }
        .pending-card-source a:hover { text-decoration: underline; }

        /* 提取面板 */
        .extract-panel {
          padding: 16px; border-radius: var(--radius-md);
          border: 1px solid var(--border); background: var(--bg-card);
          box-shadow: var(--shadow-card);
        }
        .extract-panel summary {
          cursor: pointer; font-size: 15px; font-weight: 700; color: var(--text);
          list-style: none; display: flex; align-items: center; gap: 8px;
        }
        .extract-panel summary::before { content: '▶'; font-size: 11px; transition: transform var(--transition); }
        .extract-panel[open] summary::before { transform: rotate(90deg); }
        .extract-panel-body { display: grid; gap: 14px; margin-top: 14px; }
        .extract-input-row {
          display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center;
        }
        .extract-results { display: grid; gap: 8px; }
        .extract-result-card {
          display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 12px;
          align-items: start; padding: 12px;
          border: 1px solid var(--border); border-radius: var(--radius-sm);
          background: var(--bg-input);
        }
        .extract-result-card input[type="checkbox"] { width: auto; min-height: auto; margin-top: 4px; }
        .extract-result-info { display: grid; gap: 4px; }
        .extract-result-head { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
        .extract-result-head strong { font-size: 14px; }
        .extract-confidence { font-size: 11px; color: var(--text-secondary); }

        /* 筛选栏 */
        .factors-filter {
          display: grid; grid-template-columns: auto minmax(0, 1fr) 200px; gap: 10px; align-items: center;
          margin-bottom: 14px;
        }
        .dim-tabs { display: flex; flex-wrap: wrap; gap: 6px; }
        .dim-tab {
          padding: 5px 12px; border-radius: 999px;
          border: 1px solid var(--border); background: var(--bg-card);
          color: var(--text-secondary); font-size: 12px; font-weight: 600;
          cursor: pointer; transition: all var(--transition);
        }
        .dim-tab:hover { border-color: var(--primary); color: var(--primary); }
        .dim-tab.active { background: var(--primary); border-color: var(--primary); color: #fff; }
        .status-tabs { display: flex; gap: 6px; }

        /* 弹窗 */
        .modal-overlay {
          display: none; position: fixed; inset: 0; z-index: 100;
          background: rgba(0,0,0,.4); backdrop-filter: blur(4px);
          align-items: center; justify-content: center;
        }
        .modal-overlay.open { display: flex; }
        .modal-box {
          width: 90%; max-width: 640px; max-height: 90vh;
          background: var(--bg-card); border-radius: var(--radius-lg);
          border: 1px solid var(--border); box-shadow: var(--shadow-elevated);
          display: grid; grid-template-rows: auto minmax(0, 1fr) auto;
          overflow: hidden;
        }
        .modal-header {
          display: flex; justify-content: space-between; align-items: center;
          padding: 16px 20px; border-bottom: 1px solid var(--border);
        }
        .modal-header h3 { margin: 0; font-size: 18px; font-weight: 700; }
        .modal-close {
          width: 32px; height: 32px; border-radius: var(--radius-sm);
          border: 1px solid var(--border); background: var(--bg-input);
          cursor: pointer; display: flex; align-items: center; justify-content: center;
          font-size: 16px; color: var(--text-secondary); transition: all var(--transition);
        }
        .modal-close:hover { border-color: var(--danger); color: var(--danger); }
        .modal-body { padding: 20px; overflow-y: auto; display: grid; gap: 14px; }
        .modal-footer {
          display: flex; justify-content: flex-end; gap: 8px;
          padding: 16px 20px; border-top: 1px solid var(--border);
        }

        /* Empty */
        .factors-empty {
          display: grid; place-items: center; text-align: center;
          padding: 40px; border: 1px dashed var(--border); border-radius: var(--radius-md);
          color: var(--text-secondary); line-height: 1.8;
        }
        .factors-empty-icon { font-size: 40px; margin-bottom: 8px; }
        .factors-empty-actions { display: flex; gap: 8px; margin-top: 12px; }

        /* 响应式 */
        @media (max-width: 1280px) {
          .factors-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 720px) {
          .factors-filter { grid-template-columns: 1fr; }
          .factor-cards { grid-template-columns: 1fr; }
        }
      </style>
    </head>
    <body>
      <div class="factors-shell shell">
        <section class="hero">
          <div class="hero-grid">
            <div class="hero-copy">
              <span class="eyebrow">Factor Library</span>
              <h1>文章因子库</h1>
              <p>从优质文章中提取原子化写作技法，在创作时注入到 Brief 和 Prompt 中，持续提升文章质量。</p>
              <div class="hero-links">
                <a href="/admin">回工作台</a>
                <a href="/admin/topics">选题情报台</a>
              </div>
            </div>
            <div class="hero-status-card">
              <p class="hero-status-copy">工作流：贴入文章链接提取因子 → 人工审核入库 → 在创建任务时选择因子 → 效果反馈闭环。</p>
              <div class="hero-summary">
                <div class="hero-summary-card">
                  <strong>提取因子</strong>
                  <span>从文章中 AI 自动提取</span>
                </div>
                <div class="hero-summary-card">
                  <strong>人工审核</strong>
                  <span>确认因子质量后入库</span>
                </div>
                <div class="hero-summary-card wide">
                  <strong>注入写稿</strong>
                  <span>双轨注入（指令 + Few-shot 示例）到 Phase4 写稿 Prompt。</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        __FACTORS_OVERVIEW__

        <section class="factors-grid">
          <!-- 左栏：因子库 -->
          <div class="stack">
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>因子库</h2>
                  <p class="panel-intro">浏览、搜索、编辑已入库的写作因子。</p>
                </div>
                <div class="panel-tools">
                  <button id="btn-create-factor" class="tiny-button" type="button">＋ 手动创建</button>
                </div>
              </div>

              <div class="factors-filter">
                <div class="dim-tabs" id="dim-tabs">
                  <button class="dim-tab active" data-dim="">全部</button>
                  <button class="dim-tab" data-dim="opening">开头</button>
                  <button class="dim-tab" data-dim="structure">结构</button>
                  <button class="dim-tab" data-dim="rhetoric">修辞</button>
                  <button class="dim-tab" data-dim="rhythm">节奏</button>
                  <button class="dim-tab" data-dim="layout">排版</button>
                  <button class="dim-tab" data-dim="closing">结尾</button>
                </div>
                <div class="status-tabs" id="status-tabs">
                  <button class="dim-tab active" data-status="">全部</button>
                  <button class="dim-tab" data-status="active">有效</button>
                  <button class="dim-tab" data-status="draft">草稿</button>
                  <button class="dim-tab" data-status="deprecated">废弃</button>
                </div>
                <input type="text" id="factor-search" placeholder="搜索因子名称、描述..." />
              </div>

              <div id="factor-cards" class="factor-cards">
                <div class="factors-empty">
                  <div class="factors-empty-icon">📦</div>
                  <div>正在加载因子库...</div>
                </div>
              </div>
            </section>
          </div>

          <!-- 右栏：待审核 -->
          <div class="stack">
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>待审核门禁</h2>
                  <p class="panel-intro">所有 AI 提取的因子需经人工确认后才能入库。</p>
                </div>
                <span id="pending-count" class="status-badge pending" style="display:none;">0</span>
              </div>

              <div id="pending-list">
                <div class="factors-empty" style="min-height:180px;">
                  <div>🎉 没有待审核的因子</div>
                  <div style="font-size:12px;">新提取的因子会出现在这里</div>
                </div>
              </div>
            </section>

            <!-- 提取面板 -->
            <details class="extract-panel" id="extract-panel">
              <summary>✨ 从文章中提取因子</summary>
              <div class="extract-panel-body">
                <div class="extract-input-row">
                  <input type="text" id="extract-url" placeholder="粘贴文章链接..." />
                  <button id="btn-extract" class="tiny-button" type="button">开始提取</button>
                </div>
                <div id="extract-status" style="display:none; color:var(--text-secondary); font-size:13px;"></div>
                <div id="extract-results" class="extract-results" style="display:none;"></div>
                <div id="extract-actions" style="display:none;">
                  <button id="btn-submit-extracted" class="tiny-button" type="button" disabled>提交到待审核 (0)</button>
                </div>
              </div>
            </details>
          </div>
        </section>
      </div>

      <!-- 编辑弹窗 -->
      <div class="modal-overlay" id="factor-modal">
        <div class="modal-box">
          <div class="modal-header">
            <h3 id="modal-title">创建因子</h3>
            <button class="modal-close" id="modal-close" type="button">✕</button>
          </div>
          <div class="modal-body">
            <div class="field">
              <label for="f-name">名称</label>
              <input type="text" id="f-name" placeholder="因子名称（4-50字）" />
            </div>
            <div class="field">
              <label>维度</label>
              <div class="dim-tabs" id="f-dim-tabs" style="margin-top:4px;">
                <button class="dim-tab" type="button" data-dim="opening">开头</button>
                <button class="dim-tab" type="button" data-dim="structure">结构</button>
                <button class="dim-tab" type="button" data-dim="rhetoric">修辞</button>
                <button class="dim-tab" type="button" data-dim="rhythm">节奏</button>
                <button class="dim-tab" type="button" data-dim="layout">排版</button>
                <button class="dim-tab" type="button" data-dim="closing">结尾</button>
              </div>
            </div>
            <div class="field">
              <label for="f-technique">技法描述（给 AI 的指令）</label>
              <textarea id="f-technique" rows="4" placeholder="描述这个写作技法，AI 会按此指令执行..."></textarea>
            </div>
            <div class="field">
              <label for="f-effect">效果说明（给人读的）</label>
              <input type="text" id="f-effect" placeholder="这个技法的预期效果..." />
            </div>
            <div class="field">
              <label for="f-example">示例片段（Few-shot 参考）</label>
              <textarea id="f-example" rows="3" placeholder="提供一段脱敏的示例文本..."></textarea>
            </div>
            <div class="field">
              <label for="f-anti-example">反面示例（可选）</label>
              <input type="text" id="f-anti-example" placeholder="不应该怎么写..." />
            </div>
            <div class="field">
              <label for="f-tags">标签（逗号分隔）</label>
              <input type="text" id="f-tags" placeholder="数据驱动, 悬念, 开头" />
            </div>
            <div class="field">
              <label for="f-conflict-group">冲突组（同组因子互斥）</label>
              <input type="text" id="f-conflict-group" placeholder="如 opening_style" />
            </div>
            <div class="field">
              <label for="f-source-url">来源文章链接</label>
              <input type="text" id="f-source-url" placeholder="https://..." />
            </div>
            <input type="hidden" id="f-id" />
          </div>
          <div class="modal-footer">
            <button class="secondary" id="modal-cancel" type="button">取消</button>
            <button id="modal-save" type="button">保存</button>
          </div>
        </div>
      </div>

      <script>
        __ADMIN_SHARED_SCRIPT_HELPERS__

        (() => {
          const DIM_LABELS = {
            opening: '开头', structure: '结构', rhetoric: '修辞',
            rhythm: '节奏', layout: '排版', closing: '结尾'
          };
          const STATUS_LABELS = { active: '有效', draft: '草稿', pending: '待审核', deprecated: '废弃', archived: '归档' };

          // ── 状态 ──
          const qs = {
            dimension: '', status: '', query: ''
          };

          // ── 工具 ──
          const esc = AdminUiShared.escapeHtml;
          const api = async (path, opts = {}) => {
            const res = await fetch(AdminUiShared.apiUrl(path), {
              method: opts.method || 'GET',
              headers: opts.body ? { 'Content-Type': 'application/json' } : undefined,
              body: opts.body ? JSON.stringify(opts.body) : undefined,
              credentials: 'same-origin'
            });
            const data = await AdminUiShared.parseJsonResponse(res);
            if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
            return data;
          };

          const dimBadge = (dim) => `<span class="dim-badge dim-${esc(dim)}">${esc(DIM_LABELS[dim] || dim)}</span>`;
          const statusBadge = (st) => `<span class="status-badge ${esc(st)}">${esc(STATUS_LABELS[st] || st)}</span>`;

          // ── 加载因子列表 ──
          const cardsEl = document.getElementById('factor-cards');
          const loadFactors = async () => {
            const params = new URLSearchParams();
            if (qs.dimension) params.set('dimension', qs.dimension);
            if (qs.status) params.set('status', qs.status);
            if (qs.query) params.set('query', qs.query);
            params.set('limit', '100');
            try {
              const factors = await api(`/api/v1/admin/factors/list?${params}`);
              if (!factors.length) {
                cardsEl.innerHTML = `<div class="factors-empty">
                  <div class="factors-empty-icon">📦</div>
                  <div>因子库还是空的</div>
                  <div class="factors-empty-actions">
                    <button class="tiny-button" onclick="document.getElementById('btn-create-factor').click()">手动创建</button>
                    <button class="secondary tiny-button" onclick="document.getElementById('extract-panel').open=true">从文章提取</button>
                  </div></div>`;
                return;
              }
              cardsEl.innerHTML = factors.map(f => `
                <article class="factor-card" data-factor-id="${esc(f.id)}">
                  <div class="factor-card-head">
                    <h4>${esc(f.name)}</h4>
                  </div>
                  <div class="factor-card-badges">
                    ${dimBadge(f.dimension)}
                    ${statusBadge(f.status)}
                  </div>
                  <p class="factor-card-desc">${esc(f.technique)}</p>
                  <div class="factor-card-footer">
                    <span>使用 ${f.usage_count} 次</span>
                    ${f.avg_effect_score != null ? `<span>效果 ${Number(f.avg_effect_score).toFixed(1)}</span>` : ''}
                    ${(f.tags || []).length ? `<div class="factor-card-tags">${(f.tags || []).map(t => `<span class="factor-tag">${esc(t)}</span>`).join('')}</div>` : ''}
                  </div>
                </article>
              `).join('');
            } catch (err) {
              cardsEl.innerHTML = `<div class="factors-empty"><div>加载失败：${esc(err.message)}</div></div>`;
            }
          };

          // ── 加载统计 ──
          const loadStats = async () => {
            try {
              const stats = await api('/api/v1/admin/factors/stats');
              document.getElementById('stat-active').textContent = String(stats.active || 0);
              document.getElementById('stat-draft').textContent = String(stats.draft || 0);
              document.getElementById('stat-pending').textContent = String(stats.pending || 0);
              const totalUsage = (stats.active || 0) + (stats.draft || 0);
              document.getElementById('stat-usage').textContent = String(totalUsage);
            } catch (_) {}
          };

          // ── 加载待审核 ──
          const pendingListEl = document.getElementById('pending-list');
          const pendingCountEl = document.getElementById('pending-count');
          const loadPending = async () => {
            try {
              const factors = await api('/api/v1/admin/factors/list?status=pending&limit=50');
              if (!factors.length) {
                pendingListEl.innerHTML = `<div class="factors-empty" style="min-height:180px;">
                  <div>🎉 没有待审核的因子</div>
                  <div style="font-size:12px;">新提取的因子会出现在这里</div></div>`;
                pendingCountEl.style.display = 'none';
                return;
              }
              pendingCountEl.textContent = `${factors.length} 待审核`;
              pendingCountEl.style.display = '';
              pendingListEl.innerHTML = factors.map(f => `
                <article class="pending-card" data-factor-id="${esc(f.id)}">
                  <div class="factor-card-head">
                    <h4>${esc(f.name)}</h4>
                    ${dimBadge(f.dimension)}
                  </div>
                  <p class="pending-card-desc">${esc(f.technique)}</p>
                  ${f.source_url ? `<p class="pending-card-source">来源：<a href="${esc(f.source_url)}" target="_blank" rel="noopener">原文 →</a></p>` : ''}
                  <div class="pending-card-actions">
                    <button class="tiny-button" style="background:var(--success);" data-approve="${esc(f.id)}">✓ 入库</button>
                    <button class="secondary tiny-button" data-edit-pending="${esc(f.id)}">✎ 编辑入库</button>
                    <button class="danger tiny-button" data-reject="${esc(f.id)}">✗ 驳回</button>
                  </div>
                </article>
              `).join('');
            } catch (err) {
              pendingListEl.innerHTML = `<div class="factors-empty">${esc(err.message)}</div>`;
            }
          };

          // ── 审核操作 ──
          pendingListEl.addEventListener('click', async (e) => {
            const approveId = e.target.closest('[data-approve]')?.dataset.approve;
            const rejectId = e.target.closest('[data-reject]')?.dataset.reject;
            const editPendingId = e.target.closest('[data-edit-pending]')?.dataset.editPending;

            if (approveId) {
              const btn = e.target.closest('button');
              AdminUiShared.setButtonBusy(btn, true);
              try {
                await api(`/api/v1/admin/factors/${approveId}/status`, { method: 'PATCH', body: { status: 'draft' } });
                await Promise.all([loadPending(), loadFactors(), loadStats()]);
              } catch (err) { alert('入库失败：' + err.message); }
              AdminUiShared.setButtonBusy(btn, false);
            } else if (rejectId) {
              const btn = e.target.closest('button');
              AdminUiShared.setButtonBusy(btn, true);
              try {
                await api(`/api/v1/admin/factors/${rejectId}`, { method: 'DELETE' });
                await Promise.all([loadPending(), loadStats()]);
              } catch (err) { alert('驳回失败：' + err.message); }
              AdminUiShared.setButtonBusy(btn, false);
            } else if (editPendingId) {
              openEditModal(editPendingId);
            }
          });

          // ── 筛选 ──
          document.getElementById('dim-tabs').addEventListener('click', (e) => {
            const btn = e.target.closest('.dim-tab');
            if (!btn) return;
            document.querySelectorAll('#dim-tabs .dim-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            qs.dimension = btn.dataset.dim || '';
            loadFactors();
          });
          document.getElementById('status-tabs').addEventListener('click', (e) => {
            const btn = e.target.closest('.dim-tab');
            if (!btn) return;
            document.querySelectorAll('#status-tabs .dim-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            qs.status = btn.dataset.status || '';
            loadFactors();
          });
          let searchTimer;
          document.getElementById('factor-search').addEventListener('input', (e) => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => { qs.query = e.target.value; loadFactors(); }, 300);
          });

          // ── 弹窗 ──
          const modal = document.getElementById('factor-modal');
          const openModal = () => modal.classList.add('open');
          const closeModal = () => { modal.classList.remove('open'); document.getElementById('f-id').value = ''; };
          document.getElementById('modal-close').addEventListener('click', closeModal);
          document.getElementById('modal-cancel').addEventListener('click', closeModal);
          modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

          let selectedDim = '';
          document.getElementById('f-dim-tabs').addEventListener('click', (e) => {
            const btn = e.target.closest('.dim-tab');
            if (!btn) return;
            document.querySelectorAll('#f-dim-tabs .dim-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedDim = btn.dataset.dim;
          });

          // 创建因子
          document.getElementById('btn-create-factor').addEventListener('click', () => {
            document.getElementById('modal-title').textContent = '创建因子';
            document.getElementById('f-id').value = '';
            document.getElementById('f-name').value = '';
            document.getElementById('f-technique').value = '';
            document.getElementById('f-effect').value = '';
            document.getElementById('f-example').value = '';
            document.getElementById('f-anti-example').value = '';
            document.getElementById('f-tags').value = '';
            document.getElementById('f-conflict-group').value = '';
            document.getElementById('f-source-url').value = '';
            document.querySelectorAll('#f-dim-tabs .dim-tab').forEach(b => b.classList.remove('active'));
            selectedDim = '';
            openModal();
          });

          // 编辑因子
          cardsEl.addEventListener('click', (e) => {
            const card = e.target.closest('.factor-card');
            if (!card) return;
            openEditModal(card.dataset.factorId);
          });

          const openEditModal = async (factorId) => {
            try {
              const f = await api(`/api/v1/admin/factors/${factorId}`);
              document.getElementById('modal-title').textContent = '编辑因子';
              document.getElementById('f-id').value = f.id;
              document.getElementById('f-name').value = f.name || '';
              document.getElementById('f-technique').value = f.technique || '';
              document.getElementById('f-effect').value = f.effect || '';
              document.getElementById('f-example').value = f.example_text || '';
              document.getElementById('f-anti-example').value = f.anti_example || '';
              document.getElementById('f-tags').value = (f.tags || []).join(', ');
              document.getElementById('f-conflict-group').value = f.conflict_group || '';
              document.getElementById('f-source-url').value = f.source_url || '';
              selectedDim = f.dimension;
              document.querySelectorAll('#f-dim-tabs .dim-tab').forEach(b => {
                b.classList.toggle('active', b.dataset.dim === f.dimension);
              });
              openModal();
            } catch (err) { alert('加载失败：' + err.message); }
          };

          // 保存因子
          document.getElementById('modal-save').addEventListener('click', async () => {
            const id = document.getElementById('f-id').value;
            const name = document.getElementById('f-name').value.trim();
            const technique = document.getElementById('f-technique').value.trim();
            if (!name || !technique || !selectedDim) {
              alert('请填写名称、选择维度并填写技法描述。');
              return;
            }
            const body = {
              name,
              dimension: selectedDim,
              technique,
              effect: document.getElementById('f-effect').value.trim() || null,
              example_text: document.getElementById('f-example').value.trim() || null,
              anti_example: document.getElementById('f-anti-example').value.trim() || null,
              tags: document.getElementById('f-tags').value.split(',').map(s => s.trim()).filter(Boolean),
              conflict_group: document.getElementById('f-conflict-group').value.trim() || null,
              source_url: document.getElementById('f-source-url').value.trim() || null,
            };
            const btn = document.getElementById('modal-save');
            AdminUiShared.setButtonBusy(btn, true);
            try {
              if (id) {
                await api(`/api/v1/admin/factors/${id}`, { method: 'PUT', body });
              } else {
                body.source_type = 'manual';
                body.status = 'draft';
                await api('/api/v1/admin/factors', { method: 'POST', body });
              }
              closeModal();
              await Promise.all([loadFactors(), loadPending(), loadStats()]);
            } catch (err) { alert('保存失败：' + err.message); }
            AdminUiShared.setButtonBusy(btn, false);
          });

          // ── 提取因子（模拟） ──
          const extractResultsEl = document.getElementById('extract-results');
          const extractStatusEl = document.getElementById('extract-status');
          const extractActionsEl = document.getElementById('extract-actions');
          const submitExtractedBtn = document.getElementById('btn-submit-extracted');

          document.getElementById('btn-extract').addEventListener('click', async () => {
            const url = document.getElementById('extract-url').value.trim();
            if (!url) { alert('请先粘贴文章链接。'); return; }

            const btn = document.getElementById('btn-extract');
            AdminUiShared.setButtonBusy(btn, true, '提取中...');
            extractStatusEl.style.display = '';
            extractStatusEl.textContent = '⏳ AI 正在分析文章，提取写作因子...';
            extractResultsEl.style.display = 'none';
            extractActionsEl.style.display = 'none';

            // 提取结果 — 当前版本模拟，后续接入 AI 提取 API
            await new Promise(resolve => setTimeout(resolve, 2000));

            const mockResults = [
              { name: '反直觉数据钩子', dimension: 'opening', technique: '开篇用一个违背常识的数据或事实作为钩子，制造读者的认知冲突。', confidence: 92 },
              { name: '日常类比降维', dimension: 'rhetoric', technique: '将专业概念用日常生活场景类比，让非专业读者秒懂复杂概念。', confidence: 88 },
              { name: '短句爆破节奏', dimension: 'rhythm', technique: '在情绪转折处连续使用3-5个短句，制造节奏的突然变化。', confidence: 75 },
            ];

            extractStatusEl.textContent = `✅ 提取完成，发现 ${mockResults.length} 个因子`;
            extractResultsEl.style.display = '';
            extractActionsEl.style.display = '';
            extractResultsEl.innerHTML = mockResults.map((r, i) => `
              <div class="extract-result-card">
                <input type="checkbox" checked data-extract-idx="${i}" />
                <div class="extract-result-info">
                  <div class="extract-result-head">
                    <strong>${esc(r.name)}</strong>
                    ${dimBadge(r.dimension)}
                    <span class="extract-confidence">置信度 ${r.confidence}%</span>
                  </div>
                  <p style="margin:0; color:var(--text-secondary); font-size:13px; line-height:1.6;">${esc(r.technique)}</p>
                </div>
              </div>
            `).join('');

            window._extractedFactors = mockResults;
            window._extractSourceUrl = url;
            updateSubmitCount();
            AdminUiShared.setButtonBusy(btn, false);
          });

          extractResultsEl.addEventListener('change', updateSubmitCount);
          function updateSubmitCount() {
            const checked = extractResultsEl.querySelectorAll('input[type="checkbox"]:checked').length;
            submitExtractedBtn.textContent = `提交到待审核 (${checked})`;
            submitExtractedBtn.disabled = checked === 0;
          }

          submitExtractedBtn.addEventListener('click', async () => {
            const checkboxes = extractResultsEl.querySelectorAll('input[type="checkbox"]:checked');
            if (!checkboxes.length) return;
            AdminUiShared.setButtonBusy(submitExtractedBtn, true, '提交中...');
            const sourceUrl = window._extractSourceUrl || '';
            try {
              for (const cb of checkboxes) {
                const idx = parseInt(cb.dataset.extractIdx);
                const f = window._extractedFactors[idx];
                await api('/api/v1/admin/factors', {
                  method: 'POST',
                  body: {
                    name: f.name,
                    dimension: f.dimension,
                    technique: f.technique,
                    source_url: sourceUrl,
                    source_type: 'ai_extracted',
                    status: 'pending',
                    tags: [],
                  }
                });
              }
              extractStatusEl.textContent = '✅ 已全部提交到待审核队列';
              extractResultsEl.style.display = 'none';
              extractActionsEl.style.display = 'none';
              document.getElementById('extract-url').value = '';
              await Promise.all([loadPending(), loadStats()]);
            } catch (err) { alert('提交失败：' + err.message); }
            AdminUiShared.setButtonBusy(submitExtractedBtn, false);
          });

          // ── 快捷键 ──
          document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeModal();
            if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
              e.preventDefault();
              document.getElementById('factor-search').focus();
            }
          });

          // ── 初始化 ──
          loadFactors();
          loadPending();
          loadStats();
        })();
      </script>
    </body>
    </html>
    """)

    html = html.replace("__FACTORS_OVERVIEW__", overview_html)
    return render_admin_page(html, "factors")
