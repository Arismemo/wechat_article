from __future__ import annotations

from html import escape
from textwrap import dedent


PAGE_META = {
    "portal": {
        "label": "工作台",
        "group": "",
        "icon": "dashboard",
        "context": "粘贴链接，自动生成文章，推送微信草稿箱。",
    },
    "topics": {
        "label": "选题",
        "group": "",
        "icon": "radar",
        "context": "持续抓取公开信号，形成候选池并推进选题任务。",
    },
    "review": {
        "label": "审核",
        "group": "高级",
        "icon": "check-circle",
        "context": "人工通过、重写与推稿判断集中在审核台完成。",
    },
    "feedback": {
        "label": "反馈",
        "group": "高级",
        "icon": "bar-chart",
        "context": "反馈回收、实验复盘与风格资产沉淀。",
    },
    "monitor": {
        "label": "监控",
        "group": "高级",
        "icon": "activity",
        "context": "任务流、队列与 Worker 健康排障。",
    },
    "pipeline": {
        "label": "流程配置",
        "group": "",
        "icon": "pipeline",
        "context": "可视化文章处理流程，配置各环节参数。",
    },
    "settings": {
        "label": "设置",
        "group": "",
        "icon": "settings",
        "context": "运行参数、LLM 配置和环境状态。",
    },
}

NAV_ITEMS = [
    ("portal", "/admin", "工作台"),
    ("topics", "/admin/topics", "选题"),
    ("pipeline", "/admin/pipeline", "流程配置"),
    ("review", "/admin/phase5", "审核"),
    ("feedback", "/admin/phase6", "反馈"),
    ("monitor", "/admin/console", "监控"),
    ("settings", "/admin/settings", "设置"),
]

# 侧边栏只显示工作台，其他页面通过 URL 直接访问
NAV_GROUPS = [
    ("", ["portal", "topics", "pipeline"]),
]

_ICONS = {
    "dashboard": '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="4" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="11" width="7" height="10" rx="1"/></svg>',
    "check-circle": '<svg viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="M22 4 12 14.01l-3-3"/></svg>',
    "bar-chart": '<svg viewBox="0 0 24 24"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>',
    "activity": '<svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    "pipeline": '<svg viewBox="0 0 24 24"><path d="M4 6h6M14 6h6M4 12h6M14 12h6M4 18h6M14 18h6"/><circle cx="12" cy="6" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="18" r="2"/></svg>',
    "radar": '<svg viewBox="0 0 24 24"><path d="M12 12 21 3"/><path d="M3.05 11A9 9 0 0 1 11 3.05"/><path d="M12 21a9 9 0 0 0 9-9"/><path d="M3 12a9 9 0 0 0 9 9"/><circle cx="12" cy="12" r="2"/></svg>',
    "settings": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    "menu": '<svg viewBox="0 0 24 24"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>',
}


def _icon(name: str) -> str:
    return _ICONS.get(name, "")


def _page_meta(active: str) -> dict[str, str]:
    return PAGE_META.get(active, PAGE_META["portal"])


def admin_shared_head() -> str:
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com" crossorigin />'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />'
    )


def admin_global_header(active: str) -> str:
    meta = _page_meta(active)
    return dedent(
        f"""\
        <header class="admin-header">
          <div class="admin-header-left">
            <button type="button" class="admin-header-toggle" data-admin-toggle="menu" aria-label="切换侧边栏">
              {_icon("menu")}
            </button>
            <div class="admin-header-breadcrumb">
              <span>WeChat Ops</span>
              <span>/</span>
              <strong>{escape(meta["label"])}</strong>
            </div>
          </div>
          <div class="admin-header-right">
            <span class="admin-header-badge">内容工厂后台</span>
          </div>
        </header>
        """
    )


def admin_global_sidebar(active: str) -> str:
    item_lookup = {key: (href, label) for key, href, label in NAV_ITEMS}

    groups_html_parts: list[str] = []
    for title, keys in NAV_GROUPS:
        links: list[str] = []
        for key in keys:
            href, label = item_lookup[key]
            icon_name = PAGE_META.get(key, {}).get("icon", "")
            active_class = " active" if key == active else ""
            aria = ' aria-current="page"' if key == active else ""
            links.append(
                f'<a href="{escape(href)}" class="admin-nav-item{active_class}"{aria}>'
                f'{_icon(icon_name)}<span>{escape(label)}</span></a>'
            )
        groups_html_parts.append(
            f'<div class="admin-nav-group">'
            f'<div class="admin-nav-group-label">{escape(title)}</div>'
            f'{"".join(links)}'
            f'</div>'
        )

    return dedent(
        f"""\
        <aside class="admin-sidebar">
          <div class="admin-sidebar-brand">
            <div class="admin-sidebar-logo">W</div>
            <div>
              <div class="admin-sidebar-title">WeChat Ops</div>
              <div class="admin-sidebar-subtitle">内容工厂后台</div>
            </div>
          </div>
          <nav class="admin-sidebar-nav">
            {"".join(groups_html_parts)}
          </nav>
          <div class="admin-sidebar-footer">
            <div class="admin-sidebar-footer-note">稳定的后台框体承接任务流、审核流和反馈流。</div>
          </div>
        </aside>
        <div class="admin-side-mask" data-admin-toggle="mask"></div>
        """
    )


# 兼容空壳：其他页面仍调用这些函数，但新设计中不再渲染
def admin_page_hero(**kwargs) -> str:
    return ""


def admin_hero_summary_card(*args, **kwargs) -> str:
    return ""


def admin_shared_styles() -> str:
    return _ADMIN_SHARED_CSS


def admin_overview_card(
    label: str,
    value: str,
    description: str = "",
    *,
    highlight: bool = False,
    value_id: str | None = None,
    description_id: str | None = None,
) -> str:
    classes = "overview-card highlight" if highlight else "overview-card"
    value_attr = f' id="{escape(value_id)}"' if value_id else ""
    desc_html = ""
    if description:
        description_attr = f' id="{escape(description_id)}"' if description_id else ""
        desc_html = f"<p{description_attr}>{escape(description)}</p>"
    return (
        f'<article class="{classes}">'
        f"<strong>{escape(label)}</strong>"
        f"<span{value_attr}>{escape(value)}</span>"
        f"{desc_html}"
        "</article>"
    )


def admin_overview_strip(aria_label: str, cards_html: str) -> str:
    return f'<section class="overview-strip" aria-label="{escape(aria_label)}">{cards_html}</section>'


def admin_shared_script_helpers() -> str:
    return dedent(
        """\
        const AdminUiShared = (() => {
          const escapeHtml = (value) => String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");

          const storageGet = (key, fallback = "") => {
            try {
              const value = localStorage.getItem(key);
              return value === null ? fallback : value;
            } catch (_error) {
              return fallback;
            }
          };

          const storageSet = (key, value) => {
            try {
              localStorage.setItem(key, String(value));
            } catch (_error) {}
          };

          const storageRemove = (key) => {
            try {
              localStorage.removeItem(key);
            } catch (_error) {}
          };

          const apiUrl = (path) => new URL(path, window.location.origin).toString();

          const setButtonBusy = (button, busy, pendingLabel = "处理中...") => {
            if (!button) return;
            if (!button.dataset.defaultLabel) {
              button.dataset.defaultLabel = button.textContent.trim();
            }
            button.disabled = busy;
            button.setAttribute("aria-busy", busy ? "true" : "false");
            button.textContent = busy ? pendingLabel : button.dataset.defaultLabel;
          };

          const parseJsonResponse = async (response) => {
            const text = await response.text();
            if (!text) return {};
            try {
              return JSON.parse(text);
            } catch (_error) {
              return { raw: text, detail: text };
            }
          };

          const buildSessionExpiredError = (message, note = "", beforeThrow = null) => {
            if (typeof beforeThrow === "function") {
              try { beforeThrow(); } catch (_error) {}
            }
            return new Error(note ? `${message} ${note}` : message);
          };

          const bindAdminChrome = () => {
            const body = document.body;
            const closeSidebar = () => body.classList.remove("sidebar-open");
            const toggleSidebar = () => body.classList.toggle("sidebar-open");

            document.querySelectorAll("[data-admin-toggle]").forEach((element) => {
              element.addEventListener("click", () => {
                const action = element.getAttribute("data-admin-toggle");
                if (action === "menu") { toggleSidebar(); return; }
                if (action === "mask") { closeSidebar(); }
              });
            });

            window.addEventListener("resize", () => {
              if (window.innerWidth > 960) { closeSidebar(); }
            });
          };

          return {
            apiUrl,
            bindAdminChrome,
            buildSessionExpiredError,
            escapeHtml,
            parseJsonResponse,
            setButtonBusy,
            storageGet,
            storageRemove,
            storageSet,
          };
        })();

        AdminUiShared.bindAdminChrome();
        """
    )


def _normalize_admin_markup(html: str) -> str:
    replacements = (
        ("<body>", '<body class="admin-app">'),
        ('class="shell"', 'class="shell admin-shell"'),
        ('class="stack"', 'class="stack admin-stack"'),
        ('class="layout"', 'class="layout admin-layout-grid"'),
        ('class="panel"', 'class="panel admin-panel"'),
    )
    for old, new in replacements:
        html = html.replace(old, new)
    return html


def _wrap_admin_frame(html: str, active: str) -> str:
    body_open = '<body class="admin-app">'
    shell_open = (
        f"{body_open}"
        f"{admin_global_sidebar(active)}"
        f"{admin_global_header(active)}"
        '<div class="admin-content"><main class="admin-main">'
    )
    shell_close = "</main></div></body>"
    return html.replace(body_open, shell_open, 1).replace("</body>", shell_close, 1)


def render_admin_page(html: str, active: str) -> str:
    normalized_html = _normalize_admin_markup(html)
    framed_html = _wrap_admin_frame(normalized_html, active)
    return (
        framed_html.replace("</head>", f"{admin_shared_head()}</head>")
        .replace("__ADMIN_SHARED_STYLES__", admin_shared_styles())
        .replace("__ADMIN_SHARED_SCRIPT_HELPERS__", admin_shared_script_helpers())
        .replace("__ADMIN_NAV_STYLES__", "")
        .replace("__ADMIN_SECTION_NAV__", "")
        .replace("__ADMIN_HERO__", "")
        .replace("__ADMIN_OVERVIEW__", "")
    )


# 将 CSS 放在模块末尾，作为常量字符串，避免函数体过长
_ADMIN_SHARED_CSS = dedent("""\
:root {
  --sidebar-w: 260px;
  --header-h: 56px;
  --bg-body: #F1F5F9;
  --bg-sidebar: #0C1222;
  --bg-sidebar-hover: rgba(255,255,255,.06);
  --bg-sidebar-active: rgba(59,130,246,.18);
  --bg-card: #FFFFFF;
  --bg-input: #F8FAFC;
  --primary: #3B82F6;
  --primary-hover: #2563EB;
  --primary-soft: rgba(59,130,246,.1);
  --success: #10B981;
  --success-soft: rgba(16,185,129,.1);
  --warning: #F59E0B;
  --warning-soft: rgba(245,158,11,.1);
  --danger: #EF4444;
  --danger-soft: rgba(239,68,68,.08);
  --text: #0F172A;
  --text-secondary: #64748B;
  --text-sidebar: rgba(255,255,255,.7);
  --text-sidebar-active: #FFFFFF;
  --border: #E2E8F0;
  --border-light: #F1F5F9;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --shadow-card: 0 1px 3px rgba(0,0,0,.04), 0 1px 2px rgba(0,0,0,.02);
  --shadow-elevated: 0 10px 25px rgba(0,0,0,.07);
  --shadow-header: 0 1px 3px rgba(0,0,0,.05);
  --transition: 150ms cubic-bezier(.4,0,.2,1);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; }
html { scroll-behavior: smooth; }
body.admin-app {
  font-family: 'Inter', -apple-system, 'PingFang SC', 'Noto Sans SC', sans-serif;
  color: var(--text); background: var(--bg-body); line-height: 1.6;
  min-height: 100vh; -webkit-font-smoothing: antialiased;
}
/* Header */
.admin-header {
  position: fixed; top: 0; left: var(--sidebar-w); right: 0; z-index: 30;
  height: var(--header-h); display: flex; align-items: center;
  justify-content: space-between; padding: 0 24px;
  background: rgba(255,255,255,.88); backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border); box-shadow: var(--shadow-header);
}
.admin-header-left { display: flex; align-items: center; gap: 16px; }
.admin-header-toggle {
  display: none; width: 36px; height: 36px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--bg-card); cursor: pointer;
  align-items: center; justify-content: center; padding: 0;
}
.admin-header-toggle svg {
  width: 18px; height: 18px; stroke: var(--text); stroke-width: 2;
  stroke-linecap: round; fill: none;
}
.admin-header-breadcrumb {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px; color: var(--text-secondary);
}
.admin-header-breadcrumb strong { color: var(--text); font-weight: 600; }
.admin-header-right { display: flex; align-items: center; gap: 12px; }
.admin-header-badge {
  display: inline-flex; align-items: center; padding: 4px 10px;
  border-radius: 999px; background: var(--primary-soft);
  color: var(--primary); font-size: 12px; font-weight: 600;
}
/* Sidebar */
.admin-sidebar {
  position: fixed; top: 0; left: 0; bottom: 0; width: var(--sidebar-w);
  z-index: 40; display: flex; flex-direction: column;
  background: var(--bg-sidebar); transition: transform var(--transition);
}
.admin-sidebar-brand {
  height: var(--header-h); display: flex; align-items: center;
  padding: 0 20px; gap: 10px;
  border-bottom: 1px solid rgba(255,255,255,.08); flex-shrink: 0;
}
.admin-sidebar-logo {
  width: 32px; height: 32px; border-radius: 8px;
  background: linear-gradient(135deg, #3B82F6, #8B5CF6);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 700; font-size: 14px; flex-shrink: 0;
}
.admin-sidebar-title { color: #fff; font-size: 15px; font-weight: 700; letter-spacing: -.02em; }
.admin-sidebar-subtitle { color: rgba(255,255,255,.4); font-size: 11px; }
.admin-sidebar-nav { flex: 1; overflow-y: auto; padding: 16px 12px; }
.admin-nav-group { margin-bottom: 20px; }
.admin-nav-group-label {
  padding: 0 12px 8px; font-size: 11px; font-weight: 600;
  color: rgba(255,255,255,.35); text-transform: uppercase; letter-spacing: .08em;
}
.admin-nav-item {
  display: flex; align-items: center; gap: 10px; padding: 9px 12px;
  border-radius: 8px; color: var(--text-sidebar); text-decoration: none;
  font-size: 14px; font-weight: 500; margin-bottom: 2px;
  transition: background var(--transition), color var(--transition);
}
.admin-nav-item svg {
  width: 18px; height: 18px; stroke: currentColor; stroke-width: 2;
  stroke-linecap: round; stroke-linejoin: round; fill: none; flex-shrink: 0; opacity: .7;
}
.admin-nav-item:hover { background: var(--bg-sidebar-hover); color: var(--text-sidebar-active); }
.admin-nav-item.active { background: var(--bg-sidebar-active); color: var(--text-sidebar-active); }
.admin-nav-item.active svg { opacity: 1; }
.admin-sidebar-footer { padding: 16px; border-top: 1px solid rgba(255,255,255,.06); flex-shrink: 0; }
.admin-sidebar-footer-note { font-size: 12px; color: rgba(255,255,255,.3); line-height: 1.5; }
.admin-side-mask { display: none; position: fixed; inset: 0; z-index: 35; background: rgba(0,0,0,.5); }
/* Content */
.admin-content { margin-left: var(--sidebar-w); padding-top: var(--header-h); min-height: 100vh; }
.admin-main { max-width: 1440px; margin: 0 auto; padding: 24px; }
/* Shell & Layout */
.shell, .admin-shell { display: grid; gap: 20px; }
.stack, .admin-stack { display: grid; gap: 16px; min-width: 0; }
.layout, .admin-layout-grid {
  display: grid; grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
  gap: 20px; align-items: start;
}
.panel, .admin-panel {
  padding: 20px; border-radius: var(--radius-md);
  border: 1px solid var(--border); background: var(--bg-card); box-shadow: var(--shadow-card);
}
.panel h2, .admin-panel h2 { margin: 0 0 4px; font-size: 16px; font-weight: 700; }
.panel-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
.panel-tools { display: flex; align-items: center; gap: 8px; }
.panel-intro { margin: 0 0 14px; color: var(--text-secondary); font-size: 13px; line-height: 1.7; }
/* Hero */
.hero { display: grid; gap: 16px; padding: 24px; border-radius: var(--radius-lg); border: 1px solid var(--border); background: var(--bg-card); box-shadow: var(--shadow-card); }
.hero-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(300px, 360px); gap: 20px; align-items: start; }
.hero-copy { display: grid; gap: 10px; align-content: start; }
.eyebrow, .badge { display: inline-flex; align-items: center; width: fit-content; padding: 4px 10px; border-radius: 999px; background: var(--primary-soft); color: var(--primary); font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.hero h1 { font-size: clamp(26px, 3vw, 34px); line-height: 1.15; font-weight: 800; letter-spacing: -.02em; }
.hero p { margin: 0; color: var(--text-secondary); line-height: 1.7; }
.hero-status-card { display: grid; gap: 12px; padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border); background: var(--bg-input); }
.hero-status-copy { margin: 0; font-size: 14px; line-height: 1.7; }
.hero-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.hero-summary-card { display: grid; gap: 4px; padding: 10px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-card); }
.hero-summary-card strong { color: var(--text-secondary); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
.hero-summary-card span { font-size: 14px; line-height: 1.5; }
.hero-summary-card.wide { grid-column: 1 / -1; background: var(--primary-soft); }
.hero-note { margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.7; }
.hero-links { display: flex; flex-wrap: wrap; gap: 10px; }
.hero-links a { color: var(--primary); text-decoration: none; font-size: 13px; font-weight: 500; }
.hero-links a:hover { text-decoration: underline; }
/* Overview */
.overview-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.overview-card { display: grid; gap: 6px; padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border); background: var(--bg-card); box-shadow: var(--shadow-card); }
.overview-card.highlight { grid-column: span 2; border-color: rgba(59,130,246,.2); background: linear-gradient(135deg, var(--primary-soft), var(--bg-card)); }
.overview-card strong { color: var(--text-secondary); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
.overview-card span { display: block; font-size: 28px; font-weight: 800; line-height: 1.1; font-variant-numeric: tabular-nums; letter-spacing: -.02em; }
.overview-card p { margin: 0; color: var(--text-secondary); font-size: 12px; line-height: 1.6; }
/* Form */
label { display: block; color: var(--text-secondary); font-size: 13px; font-weight: 500; margin-bottom: 4px; }
input, textarea, select { width: 100%; min-height: 40px; padding: 8px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-input); color: var(--text); font: inherit; font-size: 14px; transition: border-color var(--transition), box-shadow var(--transition); }
input:focus-visible, textarea:focus-visible, select:focus-visible { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft); }
textarea { min-height: 100px; resize: vertical; }
/* Button */
button, .button-link { display: inline-flex; align-items: center; justify-content: center; gap: 6px; min-height: 36px; padding: 7px 16px; border-radius: var(--radius-sm); border: none; font: inherit; font-size: 14px; font-weight: 600; cursor: pointer; text-decoration: none; text-align: center; background: var(--primary); color: #fff; transition: all var(--transition); }
button:hover, .button-link:hover { background: var(--primary-hover); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(59,130,246,.25); }
button.secondary, .button-link.secondary { background: var(--bg-input); border: 1px solid var(--border); color: var(--text); box-shadow: none; }
button.secondary:hover, .button-link.secondary:hover { border-color: var(--primary); color: var(--primary); background: var(--primary-soft); box-shadow: none; transform: translateY(-1px); }
button.ghost, .button-link.ghost { background: transparent; border: 1px solid var(--border); color: var(--text-secondary); box-shadow: none; }
button.warn, .button-link.warn { background: var(--warning); color: #fff; }
button.danger, .button-link.danger { background: var(--danger); color: #fff; }
button.danger:hover, .button-link.danger:hover { background: #DC2626; box-shadow: 0 4px 12px rgba(239,68,68,.25); }
button:disabled { opacity: .45; cursor: not-allowed; transform: none; box-shadow: none; }
button[aria-busy="true"] { opacity: .7; cursor: progress; }
.tiny-button { min-height: 30px; padding: 4px 10px; font-size: 12px; font-weight: 600; }
/* Status & Pill */
.status, .status-chip, .pill { display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; background: var(--primary-soft); color: var(--primary); }
.status.warn, .status-chip.waiting, .pill.warn { background: var(--warning-soft); color: #B45309; }
.status-chip.done, .pill.ok { background: var(--success-soft); color: #059669; }
.status-chip.fail, .pill.danger { background: var(--danger-soft); color: var(--danger); }
.pill { min-height: 34px; padding: 6px 14px; background: var(--bg-card); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; transition: all var(--transition); }
.pill:hover { border-color: var(--primary); color: var(--primary); transform: translateY(-1px); }
.pill.active { background: var(--primary); border-color: var(--primary); color: #fff; }
/* Misc text */
.mini, .hint, .meta, .card-note, .task-meta, .task-reason, .field-hint, .alert-meta, .list, .warning-list, .section-hint, .mini-note, .footer-note { color: var(--text-secondary); font-size: 13px; line-height: 1.7; }
/* Card bases */
.hero-summary-card, .overview-card, .workspace-overview-card, .metric-card, .detail-card, .audit-card, .summary-item, .detail-section, .setting-card, .env-card, .llm-selection-card, .llm-provider-card, .ops-card, .alert-card, .trend-card, .focus-action-item, .action-block, .task-card { border-radius: var(--radius-md); border: 1px solid var(--border); background: var(--bg-card); }
/* Field & Composer */
.field, .composer { display: grid; gap: 8px; }
.detail-column { min-width: 0; }
.grid { display: grid; gap: 10px; }
.grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.grid.single { grid-template-columns: 1fr; }
.actions, .task-actions, .section-actions, .setting-actions, .alert-actions, .status-line, .filter-row, .pill-row, .advanced-links, .check-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
/* Task list */
.task-list { display: grid; gap: 8px; align-content: start; }
.task-card { display: grid; gap: 6px; width: 100%; padding: 12px 14px; cursor: pointer; color: var(--text); font: inherit; text-align: left; transition: all var(--transition); }
.task-card:hover { border-color: var(--primary); box-shadow: 0 4px 12px rgba(59,130,246,.08); transform: translateY(-1px); }
.task-card.selected { border-color: var(--primary); background: var(--primary-soft); box-shadow: 0 4px 12px rgba(59,130,246,.1); }
.task-card.tone-waiting { border-left: 3px solid var(--warning); }
.task-card.tone-fail { border-left: 3px solid var(--danger); }
.task-card.tone-done { border-left: 3px solid var(--success); }
.task-title { font-size: 14px; font-weight: 600; line-height: 1.4; overflow-wrap: anywhere; }
.task-eyebrow { color: var(--text-secondary); font-size: 11px; font-weight: 600; }
.progress-track { width: 100%; height: 6px; border-radius: 999px; background: var(--border-light); overflow: hidden; }
.progress-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--primary), #60A5FA); }
/* Workspace */
.workspace-overview { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.workspace-overview-card { display: grid; gap: 6px; padding: 12px; }
.workspace-overview-card.strong { grid-column: span 2; background: var(--primary-soft); }
.workspace-overview-card strong { color: var(--text-secondary); font-size: 11px; font-weight: 600; text-transform: uppercase; }
.workspace-overview-card span { font-size: 18px; font-weight: 700; line-height: 1.3; word-break: break-word; }
.workspace-overview-card p { margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.workspace-layout { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(280px, .95fr); gap: 14px; align-items: start; }
.workspace-stack { display: grid; gap: 14px; }
/* Detail sections */
.detail-grid, .detail-sections, .summary-block, .section-metrics, .board, .categories, .detail-more-grid, .action-blocks, .kv-grid, .summary-grid, .env-grid, .metrics, .ops-grid, .llm-shell, .llm-selection-grid, .llm-provider-grid, .task-toolbar, .setting-grid, .ops-metrics, .trend-grid, .task-grid { display: grid; gap: 12px; }
.summary-grid, .kv-grid, .metrics, .trend-grid, .task-grid, .setting-grid, .section-metrics { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
.detail-section, .setting-card, .env-card, .ops-card, .alert-card, .trend-card, .action-block { display: grid; gap: 12px; padding: 16px; }
.detail-section-head, .ops-top, .trend-top, .group-title, .focus-action-top, .env-top, .llm-provider-head, .llm-provider-top, .alert-head, .panel-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.detail-section-head strong, .group-title h3, .panel h2, .panel-row h2, .llm-provider-top h4, .llm-provider-head h3, .llm-selection-card h3 { margin: 0; font-size: 16px; font-weight: 700; line-height: 1.35; }
.action-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; }
.action-grid.single { grid-template-columns: 1fr; }
.action-grid.compact { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.action-grid button, .action-grid .button-link { width: 100%; }
.metric-item, .summary-item, .kv { display: grid; gap: 4px; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-input); }
.metric-item strong, .summary-item strong, .kv strong, .hero-summary-card strong, .overview-card strong, .workspace-overview-card strong, .metric-item strong { color: var(--text-secondary); font-size: 11px; font-weight: 600; }
.metric-item span, .summary-item span, .kv span { font-size: 14px; line-height: 1.6; word-break: break-word; }
.summary-item.signal { background: var(--primary-soft); border-color: rgba(59,130,246,.15); }
.summary-item.signal strong { color: var(--primary); }
.summary-item.signal span { font-size: 15px; font-weight: 600; }
.summary-item small { display: block; margin-top: 6px; color: var(--text-secondary); font-size: 12px; line-height: 1.5; }
/* Pre & Empty */
pre { margin: 0; padding: 16px; border-radius: var(--radius-md); background: #1E293B; color: #E2E8F0; white-space: pre-wrap; word-break: break-word; overflow: auto; font-size: 13px; line-height: 1.65; border: 1px solid rgba(255,255,255,.05); }
.empty { padding: 20px; border-radius: var(--radius-md); border: 1px dashed var(--border); color: var(--text-secondary); text-align: center; }
.article-preview-shell { padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border); background: var(--bg-card); min-height: 200px; }
.article-preview-shell img { max-width: 100%; height: auto; }
.article-preview-shell section { margin: 0 auto; }
.latest-box, .fold, .advanced-shell, .danger-confirm-box { padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--border); background: var(--bg-input); }
.latest-box strong { font-size: 13px; color: var(--text-secondary); font-weight: 500; }
.latest-box p { margin: 0; line-height: 1.7; }
.fold summary, .advanced-shell summary { cursor: pointer; color: var(--text-secondary); font-size: 13px; }
.danger-card { border-color: rgba(239,68,68,.2); background: linear-gradient(180deg, var(--danger-soft), var(--bg-card)); }
.danger-inline-note, .danger-confirm-copy { margin: 0; color: #991B1B; font-size: 13px; line-height: 1.7; }
.danger-confirm-actions { display: flex; gap: 8px; flex-wrap: wrap; }
/* Focus action */
.focus-action-card { display: grid; gap: 14px; padding: 18px; border-radius: var(--radius-md); border: 1px solid rgba(59,130,246,.15); background: linear-gradient(135deg, var(--primary-soft), var(--bg-card)); }
.focus-action-copy { display: grid; gap: 6px; }
.focus-action-kicker { display: inline-flex; width: fit-content; padding: 3px 8px; border-radius: 999px; background: var(--primary-soft); color: var(--primary); font-size: 11px; font-weight: 700; letter-spacing: .06em; }
.focus-action-copy h2 { margin: 0; font-size: 20px; font-weight: 700; }
.focus-action-copy p { margin: 0; color: var(--text-secondary); font-size: 14px; line-height: 1.7; }
.focus-action-cta { display: grid; gap: 6px; justify-items: end; min-width: 160px; }
.focus-action-cta button { width: auto; min-width: 132px; }
.focus-action-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
.focus-action-item { display: grid; gap: 6px; padding: 12px; }
.focus-action-item.wide { grid-column: span 2; }
.focus-action-item strong { color: var(--text-secondary); font-size: 11px; font-weight: 600; text-transform: uppercase; }
.focus-action-item span { font-size: 14px; line-height: 1.6; }
/* Checkbox & Filter */
.checkbox, .check-row { min-height: 40px; padding: 8px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-input); display: flex; align-items: center; gap: 10px; }
.checkbox input, .check-row input { width: auto; min-height: auto; padding: 0; margin: 0; }
.filter-grid { display: grid; gap: 10px; }
.composer-row { display: grid; grid-template-columns: 1fr; }
.composer-actions { display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: 8px; }
.search-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; }
.search-row button { width: auto; }
/* Summary */
.summary-title { display: grid; gap: 6px; }
.summary-title h3 { margin: 0; font-size: 24px; font-weight: 800; line-height: 1.2; }
.summary-title a { width: fit-content; color: var(--primary); text-decoration: none; font-size: 13px; }
.summary-block { border-radius: var(--radius-md); padding: 16px; border: 1px solid rgba(59,130,246,.1); background: var(--primary-soft); }
.big-hint { display: grid; gap: 4px; padding: 12px; border-radius: var(--radius-sm); background: var(--bg-input); border: 1px solid var(--border); }
.big-hint strong { font-size: 11px; color: var(--text-secondary); font-weight: 600; text-transform: uppercase; }
.big-hint span { font-size: 18px; font-weight: 700; line-height: 1.4; }
.quick-facts { display: flex; flex-wrap: wrap; gap: 6px; }
.fact-pill { display: inline-flex; align-items: center; padding: 6px 10px; border-radius: 999px; border: 1px solid var(--border); background: var(--bg-input); color: var(--text-secondary); font-size: 12px; }
/* Diff & Compare */
.compare-toolbar { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-bottom: 14px; }
.compare-toolbar select { width: 100%; }
.diff-summary { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.diff-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px; }
.diff-card { background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px; }
.diff-card strong { display: block; margin-bottom: 4px; font-size: 11px; color: var(--text-secondary); font-weight: 600; }
.diff-card .before { color: #B91C1C; }
.diff-card .after { color: #15803D; }
.diff-pre { margin-top: 0; }
.diff-line { display: block; padding: 1px 0; }
.diff-line.add { color: #D1FAE5; background: rgba(16,185,129,.2); }
.diff-line.remove { color: #FEE2E2; background: rgba(239,68,68,.2); }
.diff-line.same { color: #E2E8F0; }
/* Generation & Reference */
.generation-list, .audit-list, .reference-list, .timeline-list { display: grid; gap: 10px; align-content: start; grid-auto-rows: max-content; }
.generation-card, .reference-card, .timeline-card, .audit-card, .detail-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 12px; display: grid; gap: 6px; }
.generation-card.selected { border-color: var(--primary); box-shadow: 0 0 0 1px var(--primary-soft); }
.generation-header { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 6px; }
.generation-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.generation-actions button { width: auto; min-width: 120px; }
.link-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
.link-row a, .reference-card a, .timeline-card a, .summary-title a { color: var(--primary); text-decoration: none; }
.link-row a:hover, .reference-card a:hover, .summary-title a:hover { text-decoration: underline; }
.reason-list { margin: 0; padding-left: 16px; display: grid; gap: 4px; }
.reason-list li { line-height: 1.6; }
.detail-more { border-radius: var(--radius-md); border: 1px dashed var(--border); padding: 12px; background: var(--bg-input); }
.detail-more summary { cursor: pointer; color: var(--text-secondary); font-size: 13px; }
.detail-more[open] .detail-more-grid { margin-top: 10px; }
.error-box { border-color: rgba(239,68,68,.15); background: var(--danger-soft); }
.utility-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.utility-grid button { width: auto; min-width: 120px; }
/* Progress & Trend */
.progress, .trend-rail { overflow: hidden; border-radius: 999px; background: var(--border-light); }
.progress > span, .trend-bar.submitted { background: linear-gradient(90deg, var(--primary), #60A5FA); }
.trend-bar.failed { background: linear-gradient(90deg, var(--danger), #F87171); }
/* Group & Summary pill */
.group-block { display: grid; gap: 8px; }
.group-title span { font-size: 12px; color: var(--text-secondary); }
.summary-strip { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.summary-pill { width: auto; padding: 5px 10px; border-radius: 999px; border: 1px solid var(--border); background: var(--bg-card); color: var(--text-secondary); font-size: 12px; cursor: pointer; transition: all var(--transition); }
.summary-pill:hover { border-color: var(--primary); color: var(--primary); }
.summary-pill.active { background: var(--primary-soft); color: var(--primary); border-color: var(--primary); }
/* Skip link & Busy */
.skip-link { position: absolute; top: 12px; left: 16px; transform: translateY(-180%); padding: 8px 14px; border-radius: 999px; background: var(--primary); color: #fff; text-decoration: none; z-index: 100; font-size: 13px; font-weight: 600; }
.skip-link:focus-visible { transform: translateY(0); }
.task-list[aria-busy="true"], .detail-grid[aria-busy="true"], .metrics[aria-busy="true"], .board[aria-busy="true"], .workspace[aria-busy="true"], .categories[aria-busy="true"], .alerts-grid[aria-busy="true"], .trend-grid[aria-busy="true"], .ops-grid[aria-busy="true"] { opacity: .85; }
/* Focus */
button:focus-visible, .button-link:focus-visible, a:focus-visible, summary:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
/* Responsive */
@media (max-width: 1280px) {
  .hero-grid, .layout, .admin-layout-grid, .workspace-layout, .detail-grid .workspace-layout { grid-template-columns: 1fr; }
  .overview-strip, .workspace-overview { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .overview-card.highlight, .workspace-overview-card.strong, .focus-action-item.wide { grid-column: auto; }
  .focus-action-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 960px) {
  .admin-header { left: 0; }
  .admin-content { margin-left: 0; }
  .admin-sidebar { transform: translateX(-100%); }
  body.admin-app.sidebar-open .admin-sidebar { transform: translateX(0); }
  body.admin-app.sidebar-open .admin-side-mask { display: block; }
  .admin-header-toggle { display: flex; }
  .admin-page-nav { flex-direction: column; align-items: flex-start; }
}
@media (max-width: 720px) {
  .admin-main { padding: 16px; }
  .hero, .panel, .admin-panel { padding: 16px; }
  .hero h1 { font-size: 24px; }
  .hero-summary, .overview-strip, .workspace-overview, .focus-action-grid, .grid.two, .summary-grid, .kv-grid, .metrics, .trend-grid, .task-grid, .setting-grid, .section-metrics { grid-template-columns: 1fr; }
  .overview-card.highlight, .workspace-overview-card.strong { grid-column: span 1; }
  .panel-head, .detail-section-head, .focus-action-top, .danger-confirm-actions, .panel-row, .group-title, .ops-top, .env-top, .llm-provider-head, .llm-provider-top, .alert-head, .trend-top { flex-direction: column; }
  button, .button-link { width: 100%; }
  .composer-actions { grid-template-columns: 1fr; }
  .filter-row { overflow-x: auto; flex-wrap: nowrap; scrollbar-width: none; }
  .filter-row::-webkit-scrollbar { display: none; }
  .pill { flex: 0 0 auto; white-space: nowrap; }
  .admin-header-right { display: none; }
  .search-row { grid-template-columns: 1fr; }
  .action-grid { grid-template-columns: 1fr; }
  .action-grid.compact { grid-template-columns: 1fr; }
  .task-actions button, .generation-actions button, .section-actions button, .section-actions .button-link { width: 100%; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { transition: none !important; animation: none !important; }
}
""")
