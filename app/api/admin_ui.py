from __future__ import annotations

from html import escape
from textwrap import dedent


def admin_section_nav_styles() -> str:
    return dedent(
        """\
        .section-nav-shell {
          position: sticky;
          top: 10px;
          z-index: 32;
          margin-bottom: 20px;
        }
        .section-nav {
          display: flex;
          align-items: center;
          gap: 18px;
          min-height: 64px;
          padding: 12px 18px;
          border: 1px solid rgba(255, 255, 255, 0.68);
          border-radius: 24px;
          background: rgba(255, 251, 246, 0.82);
          box-shadow: 0 18px 42px rgba(31, 93, 83, 0.12);
          backdrop-filter: blur(20px);
        }
        .section-nav-title {
          color: var(--muted);
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 0.18em;
          text-transform: uppercase;
          white-space: nowrap;
        }
        .section-nav-links {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          min-width: 0;
          margin-left: auto;
        }
        .section-nav a {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 42px;
          padding: 10px 16px;
          border-radius: 14px;
          border: 1px solid var(--line);
          background: rgba(255, 255, 255, 0.48);
          color: var(--accent-dark, var(--accent-strong, var(--accent)));
          text-decoration: none;
          font-size: 13px;
          font-weight: 600;
          letter-spacing: 0.04em;
          line-height: 1;
          transition:
            transform 140ms ease,
            background 140ms ease,
            color 140ms ease,
            border-color 140ms ease,
            box-shadow 140ms ease;
        }
        .section-nav a:hover {
          transform: translateY(-1px);
          background: rgba(31, 93, 83, 0.08);
          border-color: rgba(31, 93, 83, 0.3);
        }
        .section-nav a.active {
          background: linear-gradient(
            135deg,
            var(--accent) 0%,
            var(--accent-dark, var(--accent-strong, var(--accent))) 100%
          );
          color: #f7faf8;
          border-color: transparent;
          box-shadow: 0 14px 28px rgba(31, 93, 83, 0.22);
        }
        .section-nav a:focus-visible {
          outline: 2px solid rgba(31, 93, 83, 0.35);
          outline-offset: 2px;
        }
        @media (max-width: 720px) {
          .section-nav-shell {
            top: 0;
            margin-bottom: 14px;
          }
          .section-nav {
            align-items: stretch;
            padding: 10px;
            border-radius: 20px;
          }
          .section-nav-title {
            display: none;
          }
          .section-nav-links {
            flex-wrap: nowrap;
            justify-content: flex-start;
            overflow-x: auto;
            padding-bottom: 4px;
            scrollbar-width: none;
          }
          .section-nav-links::-webkit-scrollbar { display: none; }
          .section-nav a { flex: 0 0 auto; white-space: nowrap; }
        }
        @media (prefers-reduced-motion: reduce) {
          .section-nav a {
            transition: none;
          }
        }
        """
    )


def admin_shared_styles() -> str:
    return dedent(
        """\
        :root {
          --bg-paper: #f3ede3;
          --bg-panel: rgba(255, 250, 244, 0.9);
          --bg-panel-soft: rgba(255, 249, 242, 0.84);
          --paper: var(--bg-panel);
          --paper-soft: var(--bg-panel-soft);
          --panel: var(--bg-panel);
          --line-soft: rgba(50, 38, 22, 0.14);
          --line: var(--line-soft);
          --text: #171717;
          --muted: #5f5a54;
          --accent: #1e5a4f;
          --accent-strong: #143d37;
          --accent-dark: #143d37;
          --accent-soft: rgba(30, 90, 79, 0.12);
          --gold: #9c6a22;
          --danger: #a14032;
          --ok: #2f7c53;
          --accent-focus: #c4497a;
          --shadow: 0 24px 54px rgba(54, 37, 19, 0.12);
          --shadow-soft: 0 14px 30px rgba(54, 37, 19, 0.08);
        }
        * { box-sizing: border-box; }
        html {
          color-scheme: light;
          scroll-behavior: smooth;
        }
        body {
          margin: 0;
          min-height: 100vh;
          color: var(--text);
          line-height: 1.6;
          font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", sans-serif;
          background:
            radial-gradient(circle at top left, rgba(244, 210, 147, 0.56), transparent 22%),
            radial-gradient(circle at top right, rgba(171, 214, 201, 0.34), transparent 28%),
            linear-gradient(145deg, #efe5d7 0%, #f7f3ec 42%, #eadfcd 100%);
          background-attachment: fixed;
        }
        body::before {
          content: "";
          position: fixed;
          inset: 0;
          pointer-events: none;
          background:
            linear-gradient(rgba(255, 255, 255, 0.14), rgba(255, 255, 255, 0.14)),
            repeating-linear-gradient(
              90deg,
              transparent 0,
              transparent 92px,
              rgba(79, 61, 35, 0.03) 92px,
              rgba(79, 61, 35, 0.03) 93px
            );
          mix-blend-mode: multiply;
          opacity: 0.55;
          z-index: -1;
        }
        h1,
        h2,
        h3,
        .eyebrow,
        .badge {
          font-family: "Noto Serif SC", "Source Han Serif SC", "Songti SC", serif;
          letter-spacing: 0.01em;
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
        main,
        .admin-main {
          max-width: 1440px;
          margin: 0 auto;
          padding: 28px 20px 48px;
        }
        .shell,
        .admin-shell {
          display: grid;
          gap: 18px;
        }
        .eyebrow,
        .badge {
          display: inline-flex;
          width: fit-content;
          padding: 6px 10px;
          border-radius: 999px;
          background: var(--accent-soft);
          color: var(--accent-dark);
          font-size: 12px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }
        .hero {
          display: grid;
          gap: 14px;
          padding: 24px;
          border: 1px solid var(--line);
          border-radius: 28px;
          background: linear-gradient(135deg, rgba(255, 248, 239, 0.94), rgba(248, 244, 237, 0.88));
          box-shadow: var(--shadow);
          backdrop-filter: blur(10px);
        }
        .hero-grid {
          display: grid;
          grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.95fr);
          gap: 18px;
          align-items: stretch;
        }
        .hero-copy {
          display: grid;
          align-content: start;
          gap: 10px;
        }
        .hero h1 {
          margin: 0;
          font-size: clamp(32px, 4vw, 42px);
          line-height: 1.05;
        }
        .hero p {
          margin: 0;
          max-width: 920px;
          color: var(--muted);
          line-height: 1.75;
        }
        .hero-status-card {
          display: grid;
          gap: 14px;
          padding: 18px;
          border-radius: 24px;
          border: 1px solid rgba(30, 90, 79, 0.12);
          background: linear-gradient(160deg, rgba(255, 252, 247, 0.96), rgba(249, 245, 237, 0.9));
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
          min-width: 0;
          padding: 12px 14px;
          border-radius: 18px;
          border: 1px solid rgba(65, 48, 27, 0.1);
          background: rgba(255, 253, 249, 0.82);
        }
        .hero-summary-card strong {
          color: var(--muted);
          font-size: 12px;
          font-weight: 600;
        }
        .hero-summary-card span {
          font-size: 16px;
          line-height: 1.55;
          font-variant-numeric: tabular-nums;
        }
        .hero-summary-card.wide {
          grid-column: 1 / -1;
          background: linear-gradient(135deg, rgba(30, 90, 79, 0.1), rgba(255, 249, 242, 0.96));
        }
        .hero-note {
          margin: 0;
          color: var(--muted);
          font-size: 13px;
          line-height: 1.7;
        }
        .hero-links {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
        }
        .hero-links a {
          color: var(--accent-dark);
          text-decoration: none;
          border-bottom: 1px solid rgba(30, 90, 79, 0.22);
          transition: border-color 140ms ease, color 140ms ease;
        }
        .hero-links a:hover {
          border-color: rgba(30, 90, 79, 0.48);
        }
        .overview-strip {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 12px;
        }
        .overview-card {
          display: grid;
          gap: 8px;
          min-width: 0;
          padding: 16px;
          border-radius: 20px;
          border: 1px solid var(--line);
          background: rgba(255, 251, 246, 0.9);
          box-shadow: var(--shadow-soft);
        }
        .overview-card.highlight {
          grid-column: span 2;
          background: linear-gradient(135deg, rgba(30, 90, 79, 0.1), rgba(255, 249, 242, 0.96));
        }
        .overview-card strong {
          color: var(--muted);
          font-size: 12px;
          font-weight: 600;
        }
        .overview-card span {
          display: block;
          font-size: clamp(24px, 3vw, 28px);
          line-height: 1.1;
          font-variant-numeric: tabular-nums;
        }
        .overview-card p {
          margin: 0;
          color: var(--muted);
          font-size: 13px;
          line-height: 1.7;
        }
        input:focus-visible,
        textarea:focus-visible,
        select:focus-visible,
        button:focus-visible,
        a:focus-visible,
        summary:focus-visible {
          outline: 2px solid var(--accent-focus);
          outline-offset: 3px;
        }
        @media (max-width: 980px) {
          .hero-grid,
          .overview-strip {
            grid-template-columns: 1fr;
          }
          .overview-card.highlight {
            grid-column: auto;
          }
        }
        @media (max-width: 720px) {
          main,
          .admin-main {
            padding: 18px 14px 32px;
          }
          .hero {
            padding: 18px;
          }
          .hero-summary {
            grid-template-columns: 1fr;
          }
        }
        @media (prefers-reduced-motion: reduce) {
          html {
            scroll-behavior: auto;
          }
          .skip-link,
          .hero-links a {
            transition: none;
          }
        }
        """
    )


def admin_section_nav(active: str) -> str:
    items = [
        ("portal", "/admin", "总览"),
        ("review", "/admin/phase5", "审核"),
        ("feedback", "/admin/phase6", "反馈"),
        ("monitor", "/admin/console", "监控"),
        ("settings", "/admin/settings", "设置"),
    ]

    def render_link(key: str, href: str, label: str) -> str:
        active_class = "active" if key == active else ""
        aria_current = ' aria-current="page"' if key == active else ""
        return f'<a href="{href}" class="{active_class}"{aria_current}>{label}</a>'

    links = "".join(render_link(key, href, label) for key, href, label in items)
    return (
        '<div class="section-nav-shell">'
        '<nav class="section-nav" aria-label="后台分区">'
        '<span class="section-nav-title">后台导航</span>'
        f'<div class="section-nav-links">{links}</div>'
        "</nav>"
        "</div>"
    )


def admin_hero_summary_card(label: str, content: str, *, wide: bool = False, content_id: str | None = None) -> str:
    classes = "hero-summary-card wide" if wide else "hero-summary-card"
    id_attr = f' id="{escape(content_id)}"' if content_id else ""
    return (
        f'<div class="{classes}">'
        f"<strong>{escape(label)}</strong>"
        f"<span{id_attr}>{escape(content)}</span>"
        "</div>"
    )


def admin_overview_card(
    label: str,
    value: str,
    description: str,
    *,
    highlight: bool = False,
    value_id: str | None = None,
    description_id: str | None = None,
) -> str:
    classes = "overview-card highlight" if highlight else "overview-card"
    value_attr = f' id="{escape(value_id)}"' if value_id else ""
    description_attr = f' id="{escape(description_id)}"' if description_id else ""
    return (
        f'<article class="{classes}">'
        f"<strong>{escape(label)}</strong>"
        f"<span{value_attr}>{escape(value)}</span>"
        f"<p{description_attr}>{escape(description)}</p>"
        "</article>"
    )


def admin_overview_strip(aria_label: str, cards_html: str) -> str:
    return f'<section class="overview-strip" aria-label="{escape(aria_label)}">{cards_html}</section>'


def admin_page_hero(
    *,
    eyebrow: str,
    title: str,
    description: str,
    status_aria_label: str,
    status_slot_html: str,
    status_message: str,
    summary_cards_html: str,
    summary_aria_label: str = "首屏提示",
    hero_body_html: str = "",
    hero_note: str | None = None,
    hero_links_html: str = "",
    hero_tail_html: str = "",
) -> str:
    note_html = f'<p class="hero-note">{escape(hero_note)}</p>' if hero_note else ""
    return dedent(
        f"""\
        <section class="hero">
          <div class="hero-grid">
            <div class="hero-copy">
              <span class="eyebrow">{escape(eyebrow)}</span>
              <h1>{escape(title)}</h1>
              <p>{escape(description)}</p>
              {hero_body_html}
            </div>
            <aside class="hero-status-card" aria-label="{escape(status_aria_label)}">
              {status_slot_html}
              <p class="hero-status-copy" id="flash-message" role="status" aria-live="polite" aria-atomic="true">{escape(status_message)}</p>
              <div class="hero-summary" aria-label="{escape(summary_aria_label)}">
                {summary_cards_html}
              </div>
            </aside>
          </div>
          {note_html}
          {hero_links_html}
          {hero_tail_html}
        </section>
        """
    )


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
            } catch (_error) {
              // Ignore storage write failures so pages still work in private mode.
            }
          };

          const storageRemove = (key) => {
            try {
              localStorage.removeItem(key);
            } catch (_error) {
              // Ignore storage removal failures so pages still work in private mode.
            }
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
              try {
                beforeThrow();
              } catch (_error) {
                // Ignore persist failures and still surface the session-expired message.
              }
            }
            return new Error(note ? `${message} ${note}` : message);
          };

          return {
            apiUrl,
            buildSessionExpiredError,
            escapeHtml,
            parseJsonResponse,
            setButtonBusy,
            storageGet,
            storageRemove,
            storageSet,
          };
        })();
        """
    )


def render_admin_page(html: str, active: str) -> str:
    return (
        html.replace("__ADMIN_NAV_STYLES__", admin_section_nav_styles())
        .replace("__ADMIN_SHARED_STYLES__", admin_shared_styles())
        .replace("__ADMIN_SHARED_SCRIPT_HELPERS__", admin_shared_script_helpers())
        .replace("__ADMIN_SECTION_NAV__", admin_section_nav(active))
    )
