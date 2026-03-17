"""因子库管理页面 — 完整改进版（4 批 25 项评审改进）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.api.admin_ui import render_admin_page
from app.core.security import verify_admin_basic_auth

router = APIRouter()


# ─────────────────────── CSS ───────────────────────
def _page_css() -> str:
    return """
/* ── 因子库页面 ── */
.fl-page { display: grid; gap: 14px; }

/* 面包屑 + 统计 */
.fl-topbar {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 8px;
}
.fl-breadcrumb { font-size: 13px; color: var(--text-secondary); }
.fl-breadcrumb a { color: var(--text-secondary); text-decoration: none; }
.fl-breadcrumb a:hover { color: var(--primary); }
.fl-breadcrumb span { color: var(--text); font-weight: 600; }
.fl-stats { display: flex; gap: 6px; flex-wrap: wrap; }
.fl-stat-pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600;
  background: var(--bg-input); border: 1px solid var(--border); color: var(--text-secondary);
}
.fl-stat-pill .v { color: var(--text); font-weight: 700; }
.fl-stat-pill.hl { border-color: var(--warning); background: var(--warning-soft); }

/* 双栏 */
.fl-main {
  display: grid; grid-template-columns: minmax(0,1.6fr) minmax(280px,.7fr);
  gap: 14px; align-items: start;
}
.fl-left { display: grid; gap: 12px; }

/* 左栏 header */
.fl-left-header { display: flex; justify-content: space-between; align-items: center; }
.fl-left-header h3 { margin: 0; font-size: 16px; font-weight: 700; }

/* 筛选 */
.fl-filters { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.fl-filter-group {
  display: flex; border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden;
}
.fl-dim-btn, .fl-status-btn {
  padding: 5px 10px; border: none; background: var(--bg-card);
  color: var(--text-secondary); font-size: 12px; font-weight: 600;
  cursor: pointer; transition: all var(--transition);
  border-right: 1px solid var(--border); white-space: nowrap;
}
.fl-dim-btn:last-child, .fl-status-btn:last-child { border-right: none; }
.fl-dim-btn:hover, .fl-status-btn:hover { background: var(--bg-input); color: var(--text); }
.fl-dim-btn.active, .fl-status-btn.active { background: var(--primary); color: #fff; }
.fl-status-group {
  display: flex; border: 1px solid var(--border); border-radius: var(--radius-sm);
  overflow: hidden; margin-left: auto;
}
.fl-search { min-width: 140px; max-width: 220px; }
.fl-search input {
  padding: 5px 10px; font-size: 12px; min-height: auto; border-radius: var(--radius-sm);
}

/* 因子卡片 */
.fl-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 10px;
}
.fl-card {
  display: grid; gap: 6px; padding: 12px;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  background: var(--bg-card); box-shadow: var(--shadow-card);
  cursor: pointer; transition: all var(--transition); position: relative;
}
.fl-card:hover {
  border-color: var(--primary); box-shadow: 0 4px 12px rgba(59,130,246,.08);
  transform: translateY(-1px);
}
.fl-card-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 4px; }
.fl-card h4 { margin: 0; font-size: 13px; font-weight: 700; line-height: 1.4; }
.fl-card-edit {
  flex-shrink: 0; padding: 2px 7px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--bg-input);
  color: var(--text-secondary); font-size: 11px; cursor: pointer;
  opacity: 0; transition: opacity var(--transition);
}
.fl-card:hover .fl-card-edit { opacity: 1; }
.fl-card-edit:hover { border-color: var(--primary); color: var(--primary); }
.fl-card-badges { display: flex; flex-wrap: wrap; gap: 4px; }
.fl-card-desc {
  margin: 0; color: var(--text-secondary); font-size: 12px; line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.fl-card-foot {
  display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  font-size: 11px; color: var(--text-secondary);
  border-top: 1px solid var(--border-light); padding-top: 5px;
}
.fl-card-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.fl-card-tags span { font-size: 10px; color: var(--text-secondary); opacity: .7; }

/* 维度 & 状态 badge */
.dim-opening   { --dc: #7c3aed; --db: rgba(124,58,237,.12); }
.dim-structure  { --dc: #3b82f6; --db: rgba(59,130,246,.12); }
.dim-rhetoric   { --dc: #10b981; --db: rgba(16,185,129,.12); }
.dim-rhythm     { --dc: #f97316; --db: rgba(249,115,22,.12); }
.dim-layout     { --dc: #ec4899; --db: rgba(236,72,153,.12); }
.dim-closing    { --dc: #06b6d4; --db: rgba(6,182,212,.12); }
.fl-dim-badge {
  display: inline-flex; padding: 2px 7px; border-radius: 999px;
  font-size: 11px; font-weight: 700;
  background: var(--db, var(--primary-soft)); color: var(--dc, var(--primary));
}
.fl-status-badge { display: inline-flex; padding: 2px 7px; border-radius: 999px; font-size: 11px; font-weight: 600; }
.fl-status-badge.active  { background: var(--success-soft); color: #059669; }
.fl-status-badge.draft   { background: var(--bg-input); color: var(--text-secondary); border: 1px solid var(--border); }
.fl-status-badge.pending { background: var(--warning-soft); color: #B45309; }
.fl-status-badge.deprecated { background: var(--danger-soft); color: var(--danger); }

/* 圆点前缀映射 */
.dim-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 3px; vertical-align: middle; }

/* 右栏 */
.fl-right { display: grid; gap: 10px; align-content: start; }
.fl-right-header {
  display: flex; justify-content: space-between; align-items: center;
  padding-bottom: 6px; border-bottom: 1px solid var(--border);
}
.fl-right-header h3 { margin: 0; font-size: 15px; font-weight: 700; }
.fl-pending-badge {
  padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 700;
  background: var(--warning-soft); color: #B45309;
}
/* #6 滚动约束 */
.fl-pending-list { display: grid; gap: 8px; max-height: calc(100vh - 200px); overflow-y: auto; }
.fl-pending-card {
  display: grid; gap: 6px; padding: 10px;
  border: 1px dashed rgba(245,158,11,.35); border-radius: var(--radius-md);
  border-left: 4px solid var(--warning); background: var(--bg-card);
  transition: all .3s;
}
.fl-pending-card.fadeout { opacity: 0; transform: translateX(30px); max-height: 0; padding: 0; margin: 0; overflow: hidden; }
.fl-pending-card h4 { margin: 0; font-size: 13px; font-weight: 600; line-height: 1.4; }
.fl-pending-desc {
  margin: 0; color: var(--text-secondary); font-size: 12px; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.fl-pending-source { margin: 0; font-size: 11px; color: var(--text-secondary); }
.fl-pending-source a { color: var(--primary); text-decoration: none; }
.fl-pending-time { font-size: 10px; color: var(--text-secondary); opacity: .6; }
.fl-pending-actions { display: flex; flex-wrap: wrap; gap: 4px; }
.fl-pending-actions button { font-size: 11px; padding: 3px 9px; }
.fl-btn-approve { background: var(--success); color: #fff; border: none; border-radius: var(--radius-sm); cursor: pointer; font-weight: 600; }
.fl-btn-approve:hover { filter: brightness(1.1); }
.fl-btn-edit-approve { background: var(--bg-input); color: var(--primary); border: 1px solid var(--border); border-radius: var(--radius-sm); cursor: pointer; font-weight: 600; }
.fl-btn-edit-approve:hover { border-color: var(--primary); }
.fl-btn-reject { background: transparent; color: var(--danger); border: 1px solid var(--danger); border-radius: var(--radius-sm); cursor: pointer; font-weight: 600; transition: all .2s; }
.fl-btn-reject:hover { background: var(--danger-soft); }
.fl-btn-reject.confirm-state { background: var(--danger); color: #fff; }

/* 详情 drawer (#13) */
.fl-drawer-overlay {
  display: none; position: fixed; inset: 0; z-index: 90;
  background: rgba(0,0,0,.25); backdrop-filter: blur(2px);
}
.fl-drawer-overlay.open { display: block; }
.fl-drawer {
  position: fixed; top: 0; right: -400px; bottom: 0; width: 380px; max-width: 90vw;
  background: var(--bg-card); border-left: 1px solid var(--border);
  box-shadow: -4px 0 20px rgba(0,0,0,.1); z-index: 91;
  display: grid; grid-template-rows: auto minmax(0,1fr) auto;
  transition: right .3s cubic-bezier(.4,0,.2,1);
}
.fl-drawer-overlay.open .fl-drawer { right: 0; }
.fl-drawer-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 16px; border-bottom: 1px solid var(--border);
}
.fl-drawer-head h3 { margin: 0; font-size: 15px; font-weight: 700; }
.fl-drawer-body { padding: 14px 16px; overflow-y: auto; display: grid; gap: 12px; align-content: start; }
.fl-drawer-field label {
  display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary);
  text-transform: uppercase; letter-spacing: .5px; margin-bottom: 3px;
}
.fl-drawer-field p { margin: 0; font-size: 13px; line-height: 1.6; color: var(--text); }
.fl-drawer-field pre {
  margin: 0; padding: 8px; background: var(--bg-input); border-radius: var(--radius-sm);
  font-size: 12px; line-height: 1.5; white-space: pre-wrap; color: var(--text);
}
.fl-drawer-foot {
  display: flex; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border);
}

/* 提取面板 */
.fl-extract {
  padding: 12px; border-radius: var(--radius-md);
  border: 1px solid var(--border); background: var(--bg-card); box-shadow: var(--shadow-card);
}
.fl-extract summary {
  cursor: pointer; font-size: 14px; font-weight: 700; color: var(--text);
  list-style: none; display: flex; align-items: center; gap: 6px;
}
.fl-extract summary::-webkit-details-marker { display: none; }
.fl-extract summary::before { content: '▶'; font-size: 9px; transition: transform .2s; }
.fl-extract[open] summary::before { transform: rotate(90deg); }
.fl-extract-body { display: grid; gap: 10px; margin-top: 10px; }
.fl-extract-row { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 8px; align-items: center; }
.fl-extract-row input { font-size: 13px; min-height: auto; padding: 6px 10px; }
.fl-extract-results { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px,1fr)); gap: 8px; }
.fl-extract-card {
  display: grid; grid-template-columns: auto minmax(0,1fr); gap: 8px;
  align-items: start; padding: 10px;
  border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-input);
}
.fl-extract-card input[type="checkbox"] { width: auto; min-height: auto; margin-top: 3px; }
.fl-extract-info { display: grid; gap: 4px; }
.fl-extract-head { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.fl-ex-name { font-size: 13px; font-weight: 600; border: 1px solid transparent; background: transparent; padding: 1px 4px; border-radius: 3px; width: 100%; }
.fl-ex-name:hover, .fl-ex-name:focus { border-color: var(--border); background: var(--bg-card); }
.fl-ex-desc { font-size: 12px; border: 1px solid transparent; background: transparent; padding: 2px 4px; border-radius: 3px; resize: vertical; line-height: 1.4; font-family: inherit; width: 100%; color: var(--text-secondary); }
.fl-ex-desc:hover, .fl-ex-desc:focus { border-color: var(--border); background: var(--bg-card); }
.fl-confidence { font-size: 11px; color: var(--text-secondary); }

/* 弹窗 */
.fl-modal-overlay {
  display: none; position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,.4); backdrop-filter: blur(4px);
  align-items: center; justify-content: center;
}
.fl-modal-overlay.open { display: flex; }
.fl-modal {
  width: 90%; max-width: 560px; max-height: 90vh;
  background: var(--bg-card); border-radius: var(--radius-lg);
  border: 1px solid var(--border); box-shadow: var(--shadow-elevated);
  display: grid; grid-template-rows: auto minmax(0,1fr) auto; overflow: hidden;
}
.fl-modal-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; border-bottom: 1px solid var(--border);
}
.fl-modal-head h3 { margin: 0; font-size: 15px; font-weight: 700; }
.fl-modal-close {
  width: 26px; height: 26px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--bg-input);
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  font-size: 13px; color: var(--text-secondary); transition: all var(--transition);
}
.fl-modal-close:hover { border-color: var(--danger); color: var(--danger); }
.fl-modal-body { padding: 14px 16px; overflow-y: auto; display: grid; gap: 10px; }
.fl-modal-body label {
  font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 2px;
}
.fl-modal-body label .req { color: var(--danger); }
.fl-modal-body input, .fl-modal-body textarea { font-size: 13px; }
.fl-field-error { font-size: 11px; color: var(--danger); margin-top: 2px; display: none; }
.fl-modal-foot { padding: 10px 16px; border-top: 1px solid var(--border); }
.fl-modal-foot-row { display: flex; justify-content: flex-end; gap: 8px; }
/* #22 状态切换 */
.fl-status-bar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding-bottom: 8px; margin-bottom: 4px; border-bottom: 1px solid var(--border-light);
  font-size: 12px; color: var(--text-secondary);
}
.fl-status-bar button {
  padding: 3px 8px; font-size: 11px; font-weight: 600; border-radius: var(--radius-sm);
  cursor: pointer; transition: all var(--transition);
}
.fl-btn-set-active { background: var(--success-soft); color: #059669; border: 1px solid #059669; }
.fl-btn-set-active:hover { background: var(--success); color: #fff; }
.fl-btn-set-deprecated { background: var(--danger-soft); color: var(--danger); border: 1px solid var(--danger); }
.fl-btn-set-deprecated:hover { background: var(--danger); color: #fff; }
.fl-dim-select { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; }
.fl-dim-select button {
  padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 600;
  border: 1px solid var(--border); background: var(--bg-card);
  color: var(--text-secondary); cursor: pointer; transition: all var(--transition);
}
.fl-dim-select button:hover { border-color: var(--primary); color: var(--primary); }
.fl-dim-select button.active { background: var(--primary); border-color: var(--primary); color: #fff; }

/* 空状态 */
.fl-empty {
  display: grid; place-items: center; text-align: center;
  padding: 28px 16px; border: 1px dashed var(--border); border-radius: var(--radius-md);
  color: var(--text-secondary); line-height: 1.7;
}
.fl-empty-icon { font-size: 40px; margin-bottom: 6px; }
.fl-empty-title { font-size: 14px; font-weight: 600; color: var(--text); }
.fl-empty-sub { font-size: 12px; }
.fl-empty-actions { display: flex; gap: 8px; margin-top: 8px; }

/* Skeleton */
.fl-skeleton { display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(250px,1fr)); }
.fl-skel-card {
  height: 120px; border-radius: var(--radius-md); background: var(--bg-input);
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse { 0%,100% { opacity: .5; } 50% { opacity: 1; } }

/* Toast */
.fl-toast-container { position: fixed; top: 16px; right: 16px; z-index: 300; display: grid; gap: 6px; }
.fl-toast {
  padding: 8px 16px; border-radius: var(--radius-sm); font-size: 13px; font-weight: 600;
  box-shadow: var(--shadow-elevated);
  animation: toastSlide .3s;
  transition: opacity .3s;
}
.fl-toast.success { background: #059669; color: #fff; }
.fl-toast.error { background: var(--danger); color: #fff; }
.fl-toast.info { background: var(--primary); color: #fff; }
@keyframes toastSlide { from { transform: translateX(40px); opacity: 0; } to { transform: none; opacity: 1; } }

/* 响应式 */
@media (max-width: 1024px) { .fl-main { grid-template-columns: 1fr; } }
@media (max-width: 640px) {
  .fl-grid { grid-template-columns: 1fr; }
  .fl-filters { flex-direction: column; align-items: stretch; }
  .fl-status-group { margin-left: 0; }
}
"""


# ─────────────────────── HTML ───────────────────────
def _page_html() -> str:
    return """\
<div class="fl-page">
  <div class="fl-topbar">
    <div class="fl-breadcrumb"><a href="/admin">后台管理</a> &gt; <span>因子库</span></div>
    <div class="fl-stats">
      <span class="fl-stat-pill">有效 <b class="v" id="sv-active">0</b></span>
      <span class="fl-stat-pill">草稿 <b class="v" id="sv-draft">0</b></span>
      <span class="fl-stat-pill hl">待审核 <b class="v" id="sv-pending">0</b></span>
    </div>
  </div>

  <div class="fl-main">
    <div class="fl-left">
      <!-- #1 左栏标题 + 新建按钮 -->
      <div class="fl-left-header">
        <h3>因子库</h3>
        <button class="tiny-button" id="btn-create" type="button">+ 新建因子</button>
      </div>
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
          <input type="text" id="fl-search" placeholder="搜索名称、描述、标签...（/）" />
        </div>
      </div>
      <div id="fl-grid" class="fl-grid">
        <div class="fl-skeleton"><div class="fl-skel-card"></div><div class="fl-skel-card"></div><div class="fl-skel-card"></div></div>
      </div>
    </div>

    <div class="fl-right">
      <div class="fl-right-header">
        <h3>待审核</h3>
        <span class="fl-pending-badge" id="pending-badge" style="display:none">0</span>
      </div>
      <div class="fl-pending-list" id="pending-list">
        <div class="fl-empty" style="min-height:120px"><div class="fl-empty-icon">🎉</div><div class="fl-empty-title">无待审核</div><div class="fl-empty-sub">提取的因子会出现在这里</div></div>
      </div>
    </div>
  </div>

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

<!-- 详情 drawer (#13) -->
<div class="fl-drawer-overlay" id="fl-drawer">
  <div class="fl-drawer">
    <div class="fl-drawer-head">
      <h3 id="drawer-title">因子详情</h3>
      <button class="fl-modal-close" id="drawer-close" type="button">✕</button>
    </div>
    <div class="fl-drawer-body" id="drawer-body"></div>
    <div class="fl-drawer-foot">
      <button id="drawer-edit-btn" type="button">编辑</button>
      <button class="secondary" id="drawer-close-btn" type="button">关闭</button>
    </div>
  </div>
</div>

<!-- 编辑弹窗 -->
<div class="fl-modal-overlay" id="fl-modal">
  <div class="fl-modal">
    <div class="fl-modal-head">
      <h3 id="modal-title">创建因子</h3>
      <button class="fl-modal-close" id="modal-close" type="button">✕</button>
    </div>
    <div class="fl-modal-body">
      <!-- #22 状态切换 -->
      <div class="fl-status-bar" id="f-status-bar" style="display:none">
        <span>当前状态：<b id="f-cur-status"></b></span>
        <button class="fl-btn-set-active" data-set-status="active" type="button">激活</button>
        <button class="fl-btn-set-deprecated" data-set-status="deprecated" type="button">废弃</button>
      </div>
      <div class="field"><label for="f-name">名称 <span class="req">*</span></label><input type="text" id="f-name" placeholder="因子名称（4-50字）" /><div class="fl-field-error" id="err-name"></div></div>
      <div class="field">
        <label>维度 <span class="req">*</span></label>
        <div class="fl-dim-select" id="f-dim-tabs">
          <button type="button" data-dim="opening">开头</button>
          <button type="button" data-dim="structure">结构</button>
          <button type="button" data-dim="rhetoric">修辞</button>
          <button type="button" data-dim="rhythm">节奏</button>
          <button type="button" data-dim="layout">排版</button>
          <button type="button" data-dim="closing">结尾</button>
        </div>
        <div class="fl-field-error" id="err-dim"></div>
      </div>
      <div class="field"><label for="f-technique">技法描述 <span class="req">*</span></label><textarea id="f-technique" rows="3" placeholder="给 AI 的写作指令…"></textarea><div class="fl-field-error" id="err-tech"></div></div>
      <div class="field"><label for="f-effect">效果说明</label><input type="text" id="f-effect" placeholder="预期效果…" /></div>
      <div class="field"><label for="f-example">示例片段（Few-shot）</label><textarea id="f-example" rows="2" placeholder="脱敏的示例文本…"></textarea></div>
      <div class="field"><label for="f-anti-example">反面示例</label><input type="text" id="f-anti-example" placeholder="可选" /></div>
      <div class="field"><label for="f-tags">标签（逗号分隔）</label><input type="text" id="f-tags" placeholder="数据驱动, 悬念" /></div>
      <div class="field"><label for="f-conflict-group">冲突组</label><input type="text" id="f-conflict-group" placeholder="如 opening_style" /></div>
      <div class="field"><label for="f-source-url">来源链接</label><input type="text" id="f-source-url" placeholder="https://..." /></div>
      <input type="hidden" id="f-id" />
    </div>
    <div class="fl-modal-foot">
      <div class="fl-modal-foot-row">
        <button class="secondary" id="modal-cancel" type="button">取消</button>
        <button id="modal-save" type="button">保存</button>
      </div>
    </div>
  </div>
</div>

<!-- Toast 容器 -->
<div class="fl-toast-container" id="toast-container"></div>
"""


# ─────────────────────── JS ───────────────────────
def _page_js() -> str:
    return """\
(() => {
  const DIM = { opening:'开头', structure:'结构', rhetoric:'修辞', rhythm:'节奏', layout:'排版', closing:'结尾' };
  const STA = { active:'有效', draft:'草稿', pending:'待审核', deprecated:'废弃', archived:'归档' };
  const DIM_DOT = { opening:'#7c3aed', structure:'#3b82f6', rhetoric:'#10b981', rhythm:'#f97316', layout:'#ec4899', closing:'#06b6d4' };
  const qs = { dimension:'', status:'', query:'' };
  const esc = AdminUiShared.escapeHtml;

  // 工具函数
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

  const dimBadge = d => `<span class="fl-dim-badge dim-${esc(d)}"><span class="dim-dot" style="background:${DIM_DOT[d]||'var(--primary)'}"></span>${esc(DIM[d]||d)}</span>`;
  const staBadge = s => `<span class="fl-status-badge ${esc(s)}">${esc(STA[s]||s)}</span>`;
  const timeAgo = iso => {
    if (!iso) return '';
    const d = (Date.now() - new Date(iso).getTime()) / 1000;
    if (d < 60) return '刚刚';
    if (d < 3600) return Math.floor(d/60) + ' 分钟前';
    if (d < 86400) return Math.floor(d/3600) + ' 小时前';
    return Math.floor(d/86400) + ' 天前';
  };

  // ── Toast ──
  function showToast(msg, type='info') {
    const c = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = 'fl-toast ' + type;
    t.textContent = msg;
    c.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 2800);
  }

  // ── 因子列表 ──
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
          <div class="fl-empty-title">因子库为空</div>
          <div class="fl-empty-sub">从文章中提取写作技巧，或手动创建因子</div>
          <div class="fl-empty-actions">
            <button class="tiny-button" onclick="document.getElementById('btn-create').click()">手动创建</button>
            <button class="secondary tiny-button" onclick="document.getElementById('extract-panel').open=true">从文章提取</button>
          </div></div>`;
        return;
      }
      gridEl.innerHTML = factors.map(f => {
        const tags = (f.tags||[]).map(t => `<span>#${esc(t)}</span>`).join('');
        return `
        <article class="fl-card" data-fid="${esc(f.id)}">
          <div class="fl-card-head">
            <h4>${esc(f.name)}</h4>
            <button class="fl-card-edit" data-edit="${esc(f.id)}" onclick="event.stopPropagation()">编辑</button>
          </div>
          <div class="fl-card-badges">${dimBadge(f.dimension)} ${staBadge(f.status)}</div>
          <p class="fl-card-desc">${esc(f.technique)}</p>
          <div class="fl-card-foot">
            <span>使用 ${f.usage_count||0}</span>
            ${f.avg_effect_score!=null ? `<span>效果 ${Number(f.avg_effect_score).toFixed(1)}</span>` : ''}
            ${tags ? `<div class="fl-card-tags">${tags}</div>` : ''}
          </div>
        </article>`;
      }).join('');
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
        plEl.innerHTML = `<div class="fl-empty" style="min-height:120px"><div class="fl-empty-icon">🎉</div><div class="fl-empty-title">无待审核</div><div class="fl-empty-sub">提取的因子会出现在这里</div></div>`;
        pbEl.style.display = 'none';
        return;
      }
      pbEl.textContent = `${factors.length}`;
      pbEl.style.display = '';
      plEl.innerHTML = factors.map(f => `
        <article class="fl-pending-card" data-fid="${esc(f.id)}">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:4px">
            <h4>${esc(f.name)}</h4>
            ${dimBadge(f.dimension)}
          </div>
          <p class="fl-pending-desc">${esc(f.technique)}</p>
          ${f.source_url ? `<p class="fl-pending-source">来源：<a href="${esc(f.source_url)}" target="_blank" rel="noopener">原文 →</a></p>` : ''}
          <div class="fl-pending-time">${timeAgo(f.created_at)}</div>
          <div class="fl-pending-actions">
            <button class="fl-btn-approve" data-approve="${esc(f.id)}">✓ 通过审核</button>
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
      const card = btn.closest('.fl-pending-card');
      AdminUiShared.setButtonBusy(btn, true);
      try {
        await api(`/api/v1/admin/factors/${aId}/status`, {method:'PATCH', body:{status:'active'}});
        card.classList.add('fadeout');
        showToast('已通过审核并激活', 'success');
        setTimeout(() => refresh(), 350);
      } catch(err) { showToast('操作失败：'+err.message, 'error'); }
      AdminUiShared.setButtonBusy(btn, false);
    } else if (rId) {
      // #8 二次确认
      const btn = e.target.closest('button');
      if (!btn.classList.contains('confirm-state')) {
        btn.classList.add('confirm-state');
        btn.textContent = '确认驳回？';
        btn._timer = setTimeout(() => { btn.classList.remove('confirm-state'); btn.textContent = '✗ 驳回'; }, 2000);
        return;
      }
      clearTimeout(btn._timer);
      const card = btn.closest('.fl-pending-card');
      AdminUiShared.setButtonBusy(btn, true);
      try {
        await api(`/api/v1/admin/factors/${rId}`, {method:'DELETE'});
        card.classList.add('fadeout');
        showToast('已驳回', 'error');
        setTimeout(() => refresh(), 350);
      } catch(err) { showToast('驳回失败：'+err.message, 'error'); }
      AdminUiShared.setButtonBusy(btn, false);
    } else if (eId) {
      _pendingApproval = true;
      openEditModal(eId);
    }
  });

  // ── 筛选 ──
  document.getElementById('dim-tabs').addEventListener('click', e => {
    const btn = e.target.closest('.fl-dim-btn'); if(!btn) return;
    document.querySelectorAll('#dim-tabs .fl-dim-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active'); qs.dimension = btn.dataset.dim||''; loadFactors();
  });
  document.getElementById('status-tabs').addEventListener('click', e => {
    const btn = e.target.closest('.fl-status-btn'); if(!btn) return;
    document.querySelectorAll('#status-tabs .fl-status-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active'); qs.status = btn.dataset.status||''; loadFactors();
  });
  let st; document.getElementById('fl-search').addEventListener('input', e => {
    clearTimeout(st); st = setTimeout(()=>{ qs.query=e.target.value; loadFactors(); }, 300);
  });

  // ── Drawer (#13) ──
  const drawerEl = document.getElementById('fl-drawer');
  const drawerBody = document.getElementById('drawer-body');
  let _drawerFid = null;
  const openDrawer = async fid => {
    _drawerFid = fid;
    try {
      const f = await api(`/api/v1/admin/factors/${fid}`);
      const field = (label, val) => val ? `<div class="fl-drawer-field"><label>${label}</label><p>${esc(val)}</p></div>` : '';
      const preF = (label, val) => val ? `<div class="fl-drawer-field"><label>${label}</label><pre>${esc(val)}</pre></div>` : '';
      drawerBody.innerHTML = `
        <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
          ${dimBadge(f.dimension)} ${staBadge(f.status)}
          ${(f.tags||[]).map(t=>'<span style="font-size:11px;color:var(--text-secondary)">#'+esc(t)+'</span>').join(' ')}
        </div>
        ${field('技法描述', f.technique)}
        ${field('效果说明', f.effect)}
        ${preF('示例片段', f.example_text)}
        ${preF('反面示例', f.anti_example)}
        ${field('冲突组', f.conflict_group)}
        ${f.source_url ? `<div class="fl-drawer-field"><label>来源</label><p><a href="${esc(f.source_url)}" target="_blank" rel="noopener">${esc(f.source_url)}</a></p></div>` : ''}
        <div style="display:flex;gap:12px;font-size:12px;color:var(--text-secondary)">
          <span>使用 ${f.usage_count||0} 次</span>
          ${f.avg_effect_score!=null ? `<span>效果 ${Number(f.avg_effect_score).toFixed(1)}</span>` : ''}
        </div>`;
      document.getElementById('drawer-title').textContent = f.name;
      drawerEl.classList.add('open');
    } catch(err) { showToast('加载失败：'+err.message, 'error'); }
  };
  const closeDrawer = () => { drawerEl.classList.remove('open'); _drawerFid = null; };
  document.getElementById('drawer-close').addEventListener('click', closeDrawer);
  document.getElementById('drawer-close-btn').addEventListener('click', closeDrawer);
  drawerEl.addEventListener('click', e => { if(e.target===drawerEl) closeDrawer(); });
  document.getElementById('drawer-edit-btn').addEventListener('click', () => { if(_drawerFid) { closeDrawer(); openEditModal(_drawerFid); } });

  // 点击卡片 → drawer；编辑按钮 → 直接编辑
  gridEl.addEventListener('click', e => {
    const editBtn = e.target.closest('[data-edit]');
    const card = e.target.closest('.fl-card');
    if (editBtn) { _pendingApproval = false; openEditModal(editBtn.dataset.edit); return; }
    if (card) { openDrawer(card.dataset.fid); }
  });

  // ── 弹窗 ──
  const modal = document.getElementById('fl-modal');
  let _pendingApproval = false;
  let selDim = '';

  const openModal = () => modal.classList.add('open');
  const closeModal = () => {
    modal.classList.remove('open');
    document.getElementById('f-id').value = '';
    _pendingApproval = false;
    clearErrors();
  };
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-cancel').addEventListener('click', closeModal);
  modal.addEventListener('click', e => { if(e.target===modal) closeModal(); });

  // #1 新建按钮
  document.getElementById('btn-create').addEventListener('click', () => {
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
    selDim = '';
    document.querySelectorAll('#f-dim-tabs button').forEach(b=>b.classList.remove('active'));
    document.getElementById('f-status-bar').style.display = 'none';
    document.getElementById('modal-save').textContent = '保存';
    _pendingApproval = false;
    openModal();
  });

  document.getElementById('f-dim-tabs').addEventListener('click', e => {
    const btn = e.target.closest('button'); if(!btn) return;
    document.querySelectorAll('#f-dim-tabs button').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active'); selDim = btn.dataset.dim;
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

      // #22 状态切换
      const sbar = document.getElementById('f-status-bar');
      sbar.style.display = '';
      document.getElementById('f-cur-status').textContent = STA[f.status]||f.status;

      // #18 编辑入库时保存按钮文案
      document.getElementById('modal-save').textContent = _pendingApproval ? '保存并通过审核' : '保存';

      openModal();
    } catch(err) { showToast('加载失败：'+err.message, 'error'); }
  };

  // #22 状态操作按钮
  document.getElementById('f-status-bar').addEventListener('click', async e => {
    const btn = e.target.closest('[data-set-status]'); if(!btn) return;
    const newStatus = btn.dataset.setStatus;
    const fid = document.getElementById('f-id').value;
    if (!fid) return;
    AdminUiShared.setButtonBusy(btn, true);
    try {
      await api(`/api/v1/admin/factors/${fid}/status`, {method:'PATCH', body:{status:newStatus}});
      showToast(`状态已切换为「${STA[newStatus]}」`, 'success');
      document.getElementById('f-cur-status').textContent = STA[newStatus];
      await refresh();
    } catch(err) { showToast('操作失败：'+err.message, 'error'); }
    AdminUiShared.setButtonBusy(btn, false);
  });

  // #12 内联校验
  function clearErrors() {
    document.querySelectorAll('.fl-field-error').forEach(e => { e.style.display='none'; e.textContent=''; });
  }
  function showError(id, msg) {
    const el = document.getElementById(id);
    if (el) { el.textContent=msg; el.style.display='block'; }
  }

  // 保存
  document.getElementById('modal-save').addEventListener('click', async () => {
    clearErrors();
    const id = document.getElementById('f-id').value;
    const name = document.getElementById('f-name').value.trim();
    const technique = document.getElementById('f-technique').value.trim();
    let valid = true;
    if (!name || name.length < 4) { showError('err-name', '名称不少于 4 个字'); valid = false; }
    if (!selDim) { showError('err-dim', '请选择维度'); valid = false; }
    if (!technique || technique.length < 10) { showError('err-tech', '技法描述不少于 10 个字'); valid = false; }
    if (!valid) return;

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
      if (id) {
        await api(`/api/v1/admin/factors/${id}`, {method:'PUT', body});
        // #18 编辑入库
        if (_pendingApproval) {
          await api(`/api/v1/admin/factors/${id}/status`, {method:'PATCH', body:{status:'active'}});
          showToast('已保存并通过审核', 'success');
        } else {
          showToast('已保存', 'success');
        }
      } else {
        body.source_type = 'manual'; body.status = 'draft';
        await api('/api/v1/admin/factors', {method:'POST', body});
        showToast('因子已创建（草稿）', 'success');
      }
      closeModal(); await refresh();
    } catch(err) { showToast('保存失败：'+err.message, 'error'); }
    AdminUiShared.setButtonBusy(btn, false);
  });

  // ── 提取 ──
  const exResultsEl = document.getElementById('extract-results');
  const exStatusEl = document.getElementById('extract-status');
  const exActionsEl = document.getElementById('extract-actions');
  const submitBtn = document.getElementById('btn-submit-extracted');

  document.getElementById('btn-extract').addEventListener('click', async () => {
    const url = document.getElementById('extract-url').value.trim();
    if (!url) { showToast('请先粘贴文章链接', 'error'); return; }
    const btn = document.getElementById('btn-extract');
    AdminUiShared.setButtonBusy(btn, true, '提取中...');
    exStatusEl.style.display=''; exStatusEl.textContent='⏳ AI 正在抓取并分析文章...';
    exResultsEl.style.display='none'; exActionsEl.style.display='none';
    try {
      const result = await api('/api/v1/admin/factors/extract', {method:'POST', body:{url, max_factors:5}});
      const factors = result.factors || [];
      if (!factors.length) {
        exStatusEl.textContent='⚠️ 未提取到因子，请尝试其他文章';
        AdminUiShared.setButtonBusy(btn, false);
        return;
      }
      exStatusEl.textContent=`✅ 提取完成，发现 ${factors.length} 个因子（来源：${esc(result.article_title||'')}）`;
      exResultsEl.style.display=''; exActionsEl.style.display='';
      exResultsEl.innerHTML = factors.map((r,i)=>`
        <div class="fl-extract-card"><input type="checkbox" checked data-idx="${i}" />
        <div class="fl-extract-info">
          <div class="fl-extract-head">${dimBadge(r.dimension)}<span class="fl-confidence">置信度 ${r.confidence}%</span></div>
          <input class="fl-ex-name" data-idx="${i}" data-field="name" value="${esc(r.name)}" />
          <textarea class="fl-ex-desc" data-idx="${i}" data-field="technique" rows="2">${esc(r.technique)}</textarea>
        </div></div>
      `).join('');
      window._exFactors=factors; window._exUrl=url; updExCount();
    } catch(err) {
      exStatusEl.textContent=`❌ 提取失败：${err.message}`;
      showToast('因子提取失败：'+err.message, 'error');
    }
    AdminUiShared.setButtonBusy(btn, false);
  });

  // 同步编辑回 mock 数据
  exResultsEl.addEventListener('input', e => {
    const el = e.target; const idx = parseInt(el.dataset.idx);
    if (!isNaN(idx) && el.dataset.field && window._exFactors[idx]) {
      window._exFactors[idx][el.dataset.field] = el.value;
    }
  });
  exResultsEl.addEventListener('change', updExCount);
  function updExCount() {
    const n = exResultsEl.querySelectorAll('input[type=checkbox]:checked').length;
    submitBtn.textContent=`提交到待审核 (${n})`; submitBtn.disabled=n===0;
  }

  submitBtn.addEventListener('click', async () => {
    const cbs = exResultsEl.querySelectorAll('input[type=checkbox]:checked'); if(!cbs.length) return;
    AdminUiShared.setButtonBusy(submitBtn, true, '提交中...');
    try {
      for (const cb of cbs) {
        const f = window._exFactors[parseInt(cb.dataset.idx)];
        await api('/api/v1/admin/factors', {method:'POST', body:{
          name:f.name, dimension:f.dimension, technique:f.technique,
          source_url:window._exUrl||'', source_type:'ai_extracted', status:'pending', tags:[]
        }});
      }
      showToast(`已提交 ${cbs.length} 个因子到待审核`, 'success');
      exResultsEl.style.display='none'; exActionsEl.style.display='none';
      exStatusEl.textContent='✅ 已提交到待审核';
      document.getElementById('extract-url').value='';
      // #20 滚动到待审核区域
      document.getElementById('pending-list').scrollIntoView({behavior:'smooth', block:'start'});
      await refresh();
    } catch(err) { showToast('提交失败：'+err.message, 'error'); }
    AdminUiShared.setButtonBusy(submitBtn, false);
  });

  // ── 快捷键 ──
  document.addEventListener('keydown', e => {
    if (e.key==='Escape') { closeModal(); closeDrawer(); }
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
