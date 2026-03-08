from __future__ import annotations

from textwrap import dedent


def admin_section_nav_styles() -> str:
    return dedent(
        """\
        .section-nav {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          margin-top: 4px;
        }
        .section-nav a {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 10px 14px;
          border-radius: 999px;
          border: 1px solid var(--line);
          background: rgba(255, 255, 255, 0.52);
          color: var(--accent-dark);
          text-decoration: none;
          font-size: 13px;
          line-height: 1;
          transition: transform 120ms ease, background 120ms ease, color 120ms ease, border-color 120ms ease;
        }
        .section-nav a:hover {
          transform: translateY(-1px);
          border-color: rgba(31, 93, 83, 0.3);
        }
        .section-nav a.active {
          background: var(--accent);
          color: #f7faf8;
          border-color: transparent;
          box-shadow: 0 12px 28px rgba(31, 93, 83, 0.14);
        }
        @media (max-width: 720px) {
          .section-nav {
            flex-wrap: nowrap;
            overflow-x: auto;
            padding-bottom: 4px;
            scrollbar-width: none;
          }
          .section-nav::-webkit-scrollbar { display: none; }
          .section-nav a { flex: 0 0 auto; white-space: nowrap; }
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
    links = "".join(
        f'<a href="{href}" class="{"active" if key == active else ""}">{label}</a>'
        for key, href, label in items
    )
    return f'<nav class="section-nav" aria-label="后台分区">{links}</nav>'
