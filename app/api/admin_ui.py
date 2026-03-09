from __future__ import annotations

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
          transition: transform 140ms ease, background 140ms ease, color 140ms ease, border-color 140ms ease, box-shadow 140ms ease;
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


def admin_section_nav(active: str) -> str:
    items = [
        ("portal", "/admin", "总览"),
        ("review", "/admin/phase5", "审核"),
        ("feedback", "/admin/phase6", "反馈"),
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
