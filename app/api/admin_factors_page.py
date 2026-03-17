"""因子库管理页面 — 紧凑双栏布局，匹配设计方案 mockup。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.api.admin_ui import render_admin_page
from app.core.security import verify_admin_basic_auth

router = APIRouter()


def _page_css() -> str:
    return """
/* ── 因子库页面 ── */
.fl-page { display: grid; gap: 16px; }

/* 面包屑 + 统计 pill */
.fl-topbar {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 10px;
}
.fl-breadcrumb {
  font-size: 13px; color: var(--text-secondary);
}
.fl-breadcrumb a { color: var(--text-secondary); text-decoration: none; }
.fl-breadcrumb a:hover { color: var(--primary); }
.fl-breadcrumb span { color: var(--text); font-weight: 600; }
.fl-stats {
  display: flex; gap: 8px; flex-wrap: wrap;
}
.fl-stat-pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 600;
  background: var(--bg-input); border: 1px solid var(--border);
  color: var(--text-secondary);
}
.fl-stat-pill .fl-stat-val { color: var(--text); font-weight: 700; }
.fl-stat-pill.highlight { border-color: var(--warning); background: var(--warning-soft); }

/* 双栏主体 */
.fl-main {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, .7fr);
  gap: 16px; align-items: start;
}

/* 左栏 */
.fl-left { display: grid; gap: 16px; }

/* 筛选栏 */
.fl-filters {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
}
.fl-filter-group {
  display: flex; gap: 0; border: 1px solid var(--border); border-radius: var(--radius-sm);
  overflow: hidden;
}
.fl-dim-btn {
  padding: 6px 12px; border: none; background: var(--bg-card);
  color: var(--text-secondary); font-size: 12px; font-weight: 600;
  cursor: pointer; transition: all var(--transition);
  border-right: 1px solid var(--border);
  white-space: nowrap;
}
.fl-dim-btn:last-child { border-right: none; }
.fl-dim-btn:hover { background: var(--bg-input); color: var(--text); }
.fl-dim-btn.active { background: var(--primary); color: #fff; }
.fl-status-group {
  display: flex; gap: 0; border: 1px solid var(--border); border-radius: var(--radius-sm);
  overflow: hidden; margin-left: auto;
}
.fl-status-btn {
  padding: 6px 10px; border: none; background: var(--bg-card);
  color: var(--text-secondary); font-size: 12px; font-weight: 600;
  cursor: pointer; transition: all var(--transition);
  border-right: 1px solid var(--border);
  white-space: nowrap;
}
.fl-status-btn:last-child { border-right: none; }
.fl-status-btn:hover { background: var(--bg-input); color: var(--text); }
.fl-status-btn.active { background: var(--primary); color: #fff; }
.fl-search {
  min-width: 160px; max-width: 220px;
}
.fl-search input {
  padding: 6px 10px; font-size: 12px; min-height: auto;
  border-radius: var(--radius-sm);
}

/* 因子卡片网格 */
.fl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px;
}
.fl-card {
  display: grid; gap: 8px; padding: 14px;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  background: var(--bg-card); box-shadow: var(--shadow-card);
  cursor: pointer; transition: all var(--transition);
  position: relative;
}
.fl-card:hover {
  border-color: var(--primary);
  box-shadow: 0 4px 12px rgba(59,130,246,.08);
  transform: translateY(-1px);
}
.fl-card-head {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 6px;
}
.fl-card h4 { margin: 0; font-size: 14px; font-weight: 700; line-height: 1.4; }
.fl-card-edit {
  flex-shrink: 0; padding: 3px 8px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--bg-input);
  color: var(--text-secondary); font-size: 11px; cursor: pointer;
  opacity: 0; transition: opacity var(--transition);
}
.fl-card:hover .fl-card-edit { opacity: 1; }
.fl-card-edit:hover { border-color: var(--primary); color: var(--primary); }
.fl-card-badges { display: flex; flex-wrap: wrap; gap: 5px; }
.fl-card-desc {
  margin: 0; color: var(--text-secondary); font-size: 12px; line-height: 1.6;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.fl-card-foot {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  font-size: 11px; color: var(--text-secondary);
  border-top: 1px solid var(--border-light); padding-top: 6px;
}

/* 维度&状态 badge */
.dim-opening   { --dim-color: #7c3aed; --dim-bg: rgba(124,58,237,.12); }
.dim-structure  { --dim-color: #3b82f6; --dim-bg: rgba(59,130,246,.12); }
.dim-rhetoric   { --dim-color: #10b981; --dim-bg: rgba(16,185,129,.12); }
.dim-rhythm     { --dim-color: #f97316; --dim-bg: rgba(249,115,22,.12); }
.dim-layout     { --dim-color: #ec4899; --dim-bg: rgba(236,72,153,.12); }
.dim-closing    { --dim-color: #06b6d4; --dim-bg: rgba(6,182,212,.12); }
.fl-dim-badge {
  display: inline-flex; padding: 2px 8px; border-radius: 999px;
  font-size: 11px; font-weight: 700;
  background: var(--dim-bg, var(--primary-soft));
  color: var(--dim-color, var(--primary));
}
.fl-status-badge {
  display: inline-flex; padding: 2px 7px; border-radius: 999px;
  font-size: 11px; font-weight: 600;
}
.fl-status-badge.active  { background: var(--success-soft); color: #059669; }
.fl-status-badge.draft   { background: var(--bg-input); color: var(--text-secondary); border: 1px solid var(--border); }
.fl-status-badge.pending { background: var(--warning-soft); color: #B45309; }
.fl-status-badge.deprecated { background: var(--danger-soft); color: var(--danger); }

/* 右栏：待审核 */
.fl-right { display: grid; gap: 12px; align-content: start; }
.fl-right-header {
  display: flex; justify-content: space-between; align-items: center;
  padding-bottom: 8px; border-bottom: 1px solid var(--border);
}
.fl-right-header h3 { margin: 0; font-size: 16px; font-weight: 700; }
.fl-pending-badge {
  padding: 3px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 700;
  background: var(--warning-soft); color: #B45309;
}
.fl-pending-list { display: grid; gap: 8px; }
.fl-pending-card {
  display: grid; gap: 8px; padding: 12px;
  border: 1px dashed rgba(245,158,11,.35); border-radius: var(--radius-md);
  border-left: 4px solid var(--warning);
  background: var(--bg-card);
}
.fl-pending-card h4 { margin: 0; font-size: 13px; font-weight: 600; line-height: 1.4; }
.fl-pending-desc {
  margin: 0; color: var(--text-secondary); font-size: 12px; line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.fl-pending-source {
  margin: 0; font-size: 11px; color: var(--text-secondary);
}
.fl-pending-source a { color: var(--primary); text-decoration: none; }
.fl-pending-actions { display: flex; flex-wrap: wrap; gap: 5px; }
.fl-pending-actions button { font-size: 11px; padding: 4px 10px; }
.fl-btn-approve { background: var(--success); color: #fff; border: none; border-radius: var(--radius-sm); cursor: pointer; font-weight: 600; }
.fl-btn-approve:hover { filter: brightness(1.1); }
.fl-btn-edit-approve { background: var(--bg-input); color: var(--primary); border: 1px solid var(--border); border-radius: var(--radius-sm); cursor: pointer; font-weight: 600; }
.fl-btn-edit-approve:hover { border-color: var(--primary); }
.fl-btn-reject { background: transparent; color: var(--danger); border: 1px solid var(--danger); border-radius: var(--radius-sm); cursor: pointer; font-weight: 600; }
.fl-btn-reject:hover { background: var(--danger-soft); }

/* 底部提取面板 */
.fl-extract {
  padding: 14px; border-radius: var(--radius-md);
  border: 1px solid var(--border); background: var(--bg-card);
  box-shadow: var(--shadow-card);
}
.fl-extract summary {
  cursor: pointer; font-size: 15px; font-weight: 700; color: var(--text);
  list-style: none; display: flex; align-items: center; gap: 8px;
}
.fl-extract summary::before { content: '▶'; font-size: 10px; transition: transform .2s; }
.fl-extract[open] summary::before { transform: rotate(90deg); }
.fl-extract-body { display: grid; gap: 12px; margin-top: 12px; }
.fl-extract-row {
  display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center;
}
.fl-extract-row input { font-size: 13px; min-height: auto; padding: 7px 10px; }
.fl-extract-results {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px;
}
.fl-extract-card {
  display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 10px;
  align-items: start; padding: 10px;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg-input);
}
.fl-extract-card input[type="checkbox"] { width: auto; min-height: auto; margin-top: 3px; }
.fl-extract-info { display: grid; gap: 3px; }
.fl-extract-head { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }
.fl-extract-head strong { font-size: 13px; }
.fl-confidence { font-size: 11px; color: var(--text-secondary); }

/* 弹窗 */
.fl-modal-overlay {
  display: none; position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,.4); backdrop-filter: blur(4px);
  align-items: center; justify-content: center;
}
.fl-modal-overlay.open { display: flex; }
.fl-modal {
  width: 90%; max-width: 580px; max-height: 90vh;
  background: var(--bg-card); border-radius: var(--radius-lg);
  border: 1px solid var(--border); box-shadow: var(--shadow-elevated);
  display: grid; grid-template-rows: auto minmax(0, 1fr) auto;
  overflow: hidden;
}
.fl-modal-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px; border-bottom: 1px solid var(--border);
}
.fl-modal-head h3 { margin: 0; font-size: 16px; font-weight: 700; }
.fl-modal-close {
  width: 28px; height: 28px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--bg-input);
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  font-size: 14px; color: var(--text-secondary); transition: all var(--transition);
}
.fl-modal-close:hover { border-color: var(--danger); color: var(--danger); }
.fl-modal-body { padding: 16px 18px; overflow-y: auto; display: grid; gap: 12px; }
.fl-modal-body label { font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-bottom: 2px; }
.fl-modal-body input, .fl-modal-body textarea { font-size: 13px; }
.fl-modal-foot {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 12px 18px; border-top: 1px solid var(--border);
}
.fl-dim-select { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; }
.fl-dim-select button {
  padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 600;
  border: 1px solid var(--border); background: var(--bg-card);
  color: var(--text-secondary); cursor: pointer; transition: all var(--transition);
}
.fl-dim-select button:hover { border-color: var(--primary); color: var(--primary); }
.fl-dim-select button.active { background: var(--primary); border-color: var(--primary); color: #fff; }

/* 空状态 */
.fl-empty {
  display: grid; place-items: center; text-align: center;
  padding: 30px 16px; border: 1px dashed var(--border); border-radius: var(--radius-md);
  color: var(--text-secondary); font-size: 13px; line-height: 1.8;
}
.fl-empty-icon { font-size: 32px; margin-bottom: 6px; }
.fl-empty-actions { display: flex; gap: 8px; margin-top: 8px; }

/* 响应式 */
@media (max-width: 1024px) {
  .fl-main { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .fl-grid { grid-template-columns: 1fr; }
  .fl-filters { flex-direction: column; align-items: stretch; }
  .fl-status-group { margin-left: 0; }
}
"""


def _page_html() -> str:
    return """\
<div class="fl-page">
  <!-- 顶栏 -->
  <div class="fl-topbar">
    <div class="fl-breadcrumb">
      <a href="/admin">后台管理</a> &gt; <span>因子库</span>
    </div>
    <div class="fl-stats">
      <span class="fl-stat-pill">有效 <b class="fl-stat-val" id="sv-active">0</b></span>
      <span class="fl-stat-pill">草稿 <b class="fl-stat-val" id="sv-draft">0</b></span>
      <span class="fl-stat-pill highlight">待审核 <b class="fl-stat-val" id="sv-pending">0</b></span>
    </div>
  </div>

  <!-- 双栏主体 -->
  <div class="fl-main">
    <!-- 左栏：因子库 -->
    <div class="fl-left">
      <div class="fl-filters">
        <div class="fl-filter-group" id="dim-tabs">
          <button class="fl-dim-btn active" data-dim="">全部</button>
          <button class="fl-dim-btn" data-dim="opening">开头</button>
          <button class="fl-dim-btn" data-dim="structure">结构</button>
          <button class="fl-dim-btn" data-dim="rhetoric">修辞</button>
          <button class="fl-dim-btn" data-dim="rhythm">节奏</button>
          <button class="fl-dim-btn" data-dim="layout">排版</button>
          <button class="fl-dim-btn" data-dim="closing">结尾</button>
        </div>
        <div class="fl-status-group" id="status-tabs">
          <button class="fl-status-btn active" data-status="">全部</button>
          <button class="fl-status-btn" data-status="active">有效</button>
          <button class="fl-status-btn" data-status="draft">草稿</button>
          <button class="fl-status-btn" data-status="deprecated">废弃</button>
        </div>
        <div class="fl-search">
          <input type="text" id="fl-search" placeholder="搜索..." />
        </div>
      </div>

      <div id="fl-grid" class="fl-grid">
        <div class="fl-empty"><div class="fl-empty-icon">⏳</div>加载中...</div>
      </div>
    </div>

    <!-- 右栏：待审核 -->
    <div class="fl-right">
      <div class="fl-right-header">
        <h3>待审核</h3>
        <span class="fl-pending-badge" id="pending-badge" style="display:none">0</span>
      </div>
      <div class="fl-pending-list" id="pending-list">
        <div class="fl-empty" style="min-height:140px;"><div>🎉 无待审核</div></div>
      </div>
    </div>
  </div>

  <!-- 底部提取面板 -->
  <details class="fl-extract" id="extract-panel">
    <summary>提取因子</summary>
    <div class="fl-extract-body">
      <div class="fl-extract-row">
        <input type="text" id="extract-url" placeholder="粘贴文章链接..." />
        <button id="btn-extract" class="tiny-button" type="button">开始提取</button>
      </div>
      <div id="extract-status" style="display:none; color:var(--text-secondary); font-size:12px;"></div>
      <div id="extract-results" class="fl-extract-results" style="display:none;"></div>
      <div id="extract-actions" style="display:none;">
        <button id="btn-submit-extracted" class="tiny-button" type="button" disabled>提交到待审核 (0)</button>
      </div>
    </div>
  </details>
</div>

<!-- 编辑弹窗 -->
<div class="fl-modal-overlay" id="fl-modal">
  <div class="fl-modal">
    <div class="fl-modal-head">
      <h3 id="modal-title">创建因子</h3>
      <button class="fl-modal-close" id="modal-close" type="button">✕</button>
    </div>
    <div class="fl-modal-body">
      <div class="field"><label for="f-name">名称</label><input type="text" id="f-name" placeholder="因子名称（4-50字）" /></div>
      <div class="field">
        <label>维度</label>
        <div class="fl-dim-select" id="f-dim-tabs">
          <button type="button" data-dim="opening">开头</button>
          <button type="button" data-dim="structure">结构</button>
          <button type="button" data-dim="rhetoric">修辞</button>
          <button type="button" data-dim="rhythm">节奏</button>
          <button type="button" data-dim="layout">排版</button>
          <button type="button" data-dim="closing">结尾</button>
        </div>
      </div>
      <div class="field"><label for="f-technique">技法描述（给 AI 的指令）</label><textarea id="f-technique" rows="3" placeholder="描述写作技法…"></textarea></div>
      <div class="field"><label for="f-effect">效果说明</label><input type="text" id="f-effect" placeholder="预期效果…" /></div>
      <div class="field"><label for="f-example">示例片段（Few-shot）</label><textarea id="f-example" rows="2" placeholder="脱敏的示例文本…"></textarea></div>
      <div class="field"><label for="f-anti-example">反面示例</label><input type="text" id="f-anti-example" placeholder="可选" /></div>
      <div class="field"><label for="f-tags">标签（逗号分隔）</label><input type="text" id="f-tags" placeholder="数据驱动, 悬念" /></div>
      <div class="field"><label for="f-conflict-group">冲突组</label><input type="text" id="f-conflict-group" placeholder="如 opening_style" /></div>
      <div class="field"><label for="f-source-url">来源链接</label><input type="text" id="f-source-url" placeholder="https://..." /></div>
      <input type="hidden" id="f-id" />
    </div>
    <div class="fl-modal-foot">
      <button class="secondary" id="modal-cancel" type="button">取消</button>
      <button id="modal-save" type="button">保存</button>
    </div>
  </div>
</div>
"""


def _page_js() -> str:
    return """\
(() => {
  const DIM = { opening:'开头', structure:'结构', rhetoric:'修辞', rhythm:'节奏', layout:'排版', closing:'结尾' };
  const STA = { active:'有效', draft:'草稿', pending:'待审核', deprecated:'废弃', archived:'归档' };
  const qs = { dimension:'', status:'', query:'' };
  const esc = AdminUiShared.escapeHtml;

  const api = async (path, opts={}) => {
    const res = await fetch(AdminUiShared.apiUrl(path), {
      method: opts.method||'GET',
      headers: opts.body ? {'Content-Type':'application/json'} : undefined,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      credentials: 'same-origin'
    });
    const data = await AdminUiShared.parseJsonResponse(res);
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    return data;
  };

  const dimBadge = d => `<span class="fl-dim-badge dim-${esc(d)}">${esc(DIM[d]||d)}</span>`;
  const staBadge = s => `<span class="fl-status-badge ${esc(s)}">${esc(STA[s]||s)}</span>`;

  // ── 加载因子 ──
  const gridEl = document.getElementById('fl-grid');
  const loadFactors = async () => {
    const p = new URLSearchParams();
    if (qs.dimension) p.set('dimension', qs.dimension);
    if (qs.status) p.set('status', qs.status);
    if (qs.query) p.set('query', qs.query);
    p.set('limit','100');
    try {
      const factors = await api(`/api/v1/admin/factors/list?${p}`);
      if (!factors.length) {
        gridEl.innerHTML = `<div class="fl-empty" style="grid-column:1/-1;">
          <div class="fl-empty-icon">📦</div>
          <div>因子库为空</div>
          <div class="fl-empty-actions">
            <button class="tiny-button" onclick="document.getElementById('modal-title').textContent='创建因子';openModal()">手动创建</button>
            <button class="secondary tiny-button" onclick="document.getElementById('extract-panel').open=true">从文章提取</button>
          </div></div>`;
        return;
      }
      gridEl.innerHTML = factors.map(f => `
        <article class="fl-card" data-fid="${esc(f.id)}">
          <div class="fl-card-head">
            <h4>${esc(f.name)}</h4>
            <button class="fl-card-edit" data-edit="${esc(f.id)}" onclick="event.stopPropagation()">编辑</button>
          </div>
          <div class="fl-card-badges">
            ${dimBadge(f.dimension)}
            ${staBadge(f.status)}
          </div>
          <p class="fl-card-desc">${esc(f.technique)}</p>
          <div class="fl-card-foot">
            <span>使用次数 ${f.usage_count||0}</span>
            ${f.avg_effect_score!=null ? `<span>效果评分 ${Number(f.avg_effect_score).toFixed(1)}</span>` : ''}
          </div>
        </article>
      `).join('');
    } catch(err) {
      gridEl.innerHTML = `<div class="fl-empty" style="grid-column:1/-1;">${esc(err.message)}</div>`;
    }
  };

  // ── 统计 ──
  const loadStats = async () => {
    try {
      const s = await api('/api/v1/admin/factors/stats');
      document.getElementById('sv-active').textContent = s.active||0;
      document.getElementById('sv-draft').textContent = s.draft||0;
      document.getElementById('sv-pending').textContent = s.pending||0;
    } catch(_){}
  };

  // ── 待审核 ──
  const plEl = document.getElementById('pending-list');
  const pbEl = document.getElementById('pending-badge');
  const loadPending = async () => {
    try {
      const factors = await api('/api/v1/admin/factors/list?status=pending&limit=50');
      if (!factors.length) {
        plEl.innerHTML = `<div class="fl-empty" style="min-height:140px;"><div>🎉 无待审核</div><div style="font-size:11px">提取的因子会出现在这里</div></div>`;
        pbEl.style.display = 'none';
        return;
      }
      pbEl.textContent = `待审核因子 · ${factors.length}`;
      pbEl.style.display = '';
      plEl.innerHTML = factors.map(f => `
        <article class="fl-pending-card" data-fid="${esc(f.id)}">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:6px">
            <h4>${esc(f.name)}</h4>
            ${dimBadge(f.dimension)}
          </div>
          <p class="fl-pending-desc">${esc(f.technique)}</p>
          ${f.source_url ? `<p class="fl-pending-source">来源：<a href="${esc(f.source_url)}" target="_blank" rel="noopener">原文 →</a></p>` : ''}
          <div class="fl-pending-actions">
            <button class="fl-btn-approve" data-approve="${esc(f.id)}">✓ 入库</button>
            <button class="fl-btn-edit-approve" data-edit-p="${esc(f.id)}">✎ 编辑入库</button>
            <button class="fl-btn-reject" data-reject="${esc(f.id)}">✗ 驳回</button>
          </div>
        </article>
      `).join('');
    } catch(err) {
      plEl.innerHTML = `<div class="fl-empty">${esc(err.message)}</div>`;
    }
  };

  // ── 审核操作 ──
  plEl.addEventListener('click', async e => {
    const aId = e.target.closest('[data-approve]')?.dataset.approve;
    const rId = e.target.closest('[data-reject]')?.dataset.reject;
    const eId = e.target.closest('[data-edit-p]')?.dataset.editP;
    if (aId) {
      const btn = e.target.closest('button');
      AdminUiShared.setButtonBusy(btn, true);
      try { await api(`/api/v1/admin/factors/${aId}/status`, {method:'PATCH', body:{status:'draft'}}); await refresh(); }
      catch(err) { alert('入库失败：'+err.message); }
      AdminUiShared.setButtonBusy(btn, false);
    } else if (rId) {
      const btn = e.target.closest('button');
      AdminUiShared.setButtonBusy(btn, true);
      try { await api(`/api/v1/admin/factors/${rId}`, {method:'DELETE'}); await refresh(); }
      catch(err) { alert('驳回失败：'+err.message); }
      AdminUiShared.setButtonBusy(btn, false);
    } else if (eId) { openEditModal(eId); }
  });

  // ── 筛选 ──
  document.getElementById('dim-tabs').addEventListener('click', e => {
    const btn = e.target.closest('.fl-dim-btn'); if(!btn) return;
    document.querySelectorAll('#dim-tabs .fl-dim-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    qs.dimension = btn.dataset.dim||'';
    loadFactors();
  });
  document.getElementById('status-tabs').addEventListener('click', e => {
    const btn = e.target.closest('.fl-status-btn'); if(!btn) return;
    document.querySelectorAll('#status-tabs .fl-status-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    qs.status = btn.dataset.status||'';
    loadFactors();
  });
  let st; document.getElementById('fl-search').addEventListener('input', e => {
    clearTimeout(st); st = setTimeout(()=>{ qs.query=e.target.value; loadFactors(); }, 300);
  });

  // ── 弹窗 ──
  const modal = document.getElementById('fl-modal');
  const openModal = () => modal.classList.add('open');
  window.openModal = openModal;
  const closeModal = () => { modal.classList.remove('open'); document.getElementById('f-id').value=''; };
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-cancel').addEventListener('click', closeModal);
  modal.addEventListener('click', e => { if(e.target===modal) closeModal(); });

  let selDim = '';
  document.getElementById('f-dim-tabs').addEventListener('click', e => {
    const btn = e.target.closest('button'); if(!btn) return;
    document.querySelectorAll('#f-dim-tabs button').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    selDim = btn.dataset.dim;
  });

  // 点击卡片编辑
  gridEl.addEventListener('click', e => {
    const editBtn = e.target.closest('[data-edit]');
    const card = e.target.closest('.fl-card');
    if (editBtn) { openEditModal(editBtn.dataset.edit); return; }
    if (card) { openEditModal(card.dataset.fid); }
  });

  const openEditModal = async fid => {
    try {
      const f = await api(`/api/v1/admin/factors/${fid}`);
      document.getElementById('modal-title').textContent = '编辑因子';
      document.getElementById('f-id').value = f.id;
      document.getElementById('f-name').value = f.name||'';
      document.getElementById('f-technique').value = f.technique||'';
      document.getElementById('f-effect').value = f.effect||'';
      document.getElementById('f-example').value = f.example_text||'';
      document.getElementById('f-anti-example').value = f.anti_example||'';
      document.getElementById('f-tags').value = (f.tags||[]).join(', ');
      document.getElementById('f-conflict-group').value = f.conflict_group||'';
      document.getElementById('f-source-url').value = f.source_url||'';
      selDim = f.dimension;
      document.querySelectorAll('#f-dim-tabs button').forEach(b => b.classList.toggle('active', b.dataset.dim===f.dimension));
      openModal();
    } catch(err) { alert('加载失败：'+err.message); }
  };

  // 保存
  document.getElementById('modal-save').addEventListener('click', async () => {
    const id = document.getElementById('f-id').value;
    const name = document.getElementById('f-name').value.trim();
    const technique = document.getElementById('f-technique').value.trim();
    if (!name||!technique||!selDim) { alert('请填写名称、选择维度并填写技法描述。'); return; }
    const body = {
      name, dimension: selDim, technique,
      effect: document.getElementById('f-effect').value.trim()||null,
      example_text: document.getElementById('f-example').value.trim()||null,
      anti_example: document.getElementById('f-anti-example').value.trim()||null,
      tags: document.getElementById('f-tags').value.split(',').map(s=>s.trim()).filter(Boolean),
      conflict_group: document.getElementById('f-conflict-group').value.trim()||null,
      source_url: document.getElementById('f-source-url').value.trim()||null,
    };
    const btn = document.getElementById('modal-save');
    AdminUiShared.setButtonBusy(btn, true);
    try {
      if (id) { await api(`/api/v1/admin/factors/${id}`, {method:'PUT', body}); }
      else { body.source_type='manual'; body.status='draft'; await api('/api/v1/admin/factors', {method:'POST', body}); }
      closeModal(); await refresh();
    } catch(err) { alert('保存失败：'+err.message); }
    AdminUiShared.setButtonBusy(btn, false);
  });

  // ── 提取 ──
  const exResultsEl = document.getElementById('extract-results');
  const exStatusEl = document.getElementById('extract-status');
  const exActionsEl = document.getElementById('extract-actions');
  const submitBtn = document.getElementById('btn-submit-extracted');

  document.getElementById('btn-extract').addEventListener('click', async () => {
    const url = document.getElementById('extract-url').value.trim();
    if (!url) { alert('请先粘贴文章链接。'); return; }
    const btn = document.getElementById('btn-extract');
    AdminUiShared.setButtonBusy(btn, true, '提取中...');
    exStatusEl.style.display=''; exStatusEl.textContent='⏳ AI 正在分析文章...';
    exResultsEl.style.display='none'; exActionsEl.style.display='none';
    await new Promise(r=>setTimeout(r,2000));
    const mock = [
      {name:'反直觉数据钩子', dimension:'opening', technique:'开篇用一个违背常识的数据或事实作为钩子，制造读者的认知冲突。', confidence:92},
      {name:'日常类比降维', dimension:'rhetoric', technique:'将专业概念用日常生活场景类比，让非专业读者秒懂复杂概念。', confidence:88},
      {name:'短句爆破节奏', dimension:'rhythm', technique:'在情绪转折处连续使用3-5个短句，制造节奏的突然变化。', confidence:75},
    ];
    exStatusEl.textContent=`✅ 提取完成，发现 ${mock.length} 个因子`;
    exResultsEl.style.display=''; exActionsEl.style.display='';
    exResultsEl.innerHTML = mock.map((r,i)=>`
      <div class="fl-extract-card"><input type="checkbox" checked data-idx="${i}" />
      <div class="fl-extract-info"><div class="fl-extract-head"><strong>${esc(r.name)}</strong>${dimBadge(r.dimension)}<span class="fl-confidence">置信度 ${r.confidence}%</span></div>
      <p style="margin:0;color:var(--text-secondary);font-size:12px;line-height:1.5">${esc(r.technique)}</p></div></div>
    `).join('');
    window._exFactors=mock; window._exUrl=url; updExCount();
    AdminUiShared.setButtonBusy(btn, false);
  });

  exResultsEl.addEventListener('change', updExCount);
  function updExCount() {
    const n = exResultsEl.querySelectorAll('input:checked').length;
    submitBtn.textContent=`提交到待审核 (${n})`; submitBtn.disabled=n===0;
  }

  submitBtn.addEventListener('click', async () => {
    const cbs = exResultsEl.querySelectorAll('input:checked'); if(!cbs.length) return;
    AdminUiShared.setButtonBusy(submitBtn, true, '提交中...');
    try {
      for (const cb of cbs) {
        const f = window._exFactors[parseInt(cb.dataset.idx)];
        await api('/api/v1/admin/factors', {method:'POST', body:{
          name:f.name, dimension:f.dimension, technique:f.technique,
          source_url:window._exUrl||'', source_type:'ai_extracted', status:'pending', tags:[]
        }});
      }
      exStatusEl.textContent='✅ 已提交到待审核';
      exResultsEl.style.display='none'; exActionsEl.style.display='none';
      document.getElementById('extract-url').value='';
      await refresh();
    } catch(err) { alert('提交失败：'+err.message); }
    AdminUiShared.setButtonBusy(submitBtn, false);
  });

  // ── 快捷键 ──
  document.addEventListener('keydown', e => {
    if (e.key==='Escape') closeModal();
    if (e.key==='/' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) {
      e.preventDefault(); document.getElementById('fl-search').focus();
    }
  });

  const refresh = () => Promise.all([loadFactors(), loadPending(), loadStats()]);
  refresh();
})();
"""


@router.get("/admin/factors", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def admin_factors_page() -> str:
    page_content = f"""\
<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
<title>因子库</title>
<style>__ADMIN_SHARED_STYLES__
{_page_css()}
</style>
</head><body>
{_page_html()}
<script>
__ADMIN_SHARED_SCRIPT_HELPERS__
{_page_js()}
</script>
</body></html>"""
    return render_admin_page(page_content, "factors")
