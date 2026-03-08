from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class WechatLayoutRenderResult:
    normalized_markdown: str
    html: str
    normalization_warnings: list[str]
    residual_markdown_markers: list[str]


class WechatLayoutService:
    _HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
    _BLOCKQUOTE_RE = re.compile(r"^>\s?(.*)$")
    _ORDERED_LIST_RE = re.compile(r"^(\d+)\.\s+(.*)$")
    _BULLET_LIST_RE = re.compile(r"^[-*]\s+(.*)$")
    _TASK_LIST_RE = re.compile(r"^[-*]\s+\[[ xX]\]\s+(.*)$")
    _IMAGE_LINE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
    _TABLE_LINE_RE = re.compile(r"^\|.+\|$")
    _TABLE_SEPARATOR_RE = re.compile(r"^\|?(?:\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?$")
    _CODE_FENCE_RE = re.compile(r"^```")
    _HR_RE = re.compile(r"^(?:---+|\*\*\*+)$")
    _RAW_HTML_RE = re.compile(r"</?[A-Za-z][^>]*>")
    _RESIDUAL_MARKERS: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("code_fence", re.compile(r"```")),
        ("markdown_table", re.compile(r"^\|.+\|$", re.MULTILINE)),
        ("task_list", re.compile(r"^[-*]\s+\[[ xX]\]\s+", re.MULTILINE)),
        ("raw_html", re.compile(r"</?[A-Za-z][^>]*>")),
    )

    _WRAPPER_STYLE = (
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB',"
        "'Microsoft YaHei',sans-serif;"
        "font-size:16px;"
        "color:#2f2f2f;"
        "line-height:1.75;"
        "letter-spacing:0.02em;"
        "padding:0 6px;"
        "word-break:break-word;"
    )
    _H1_STYLE = (
        "margin:0 0 18px;"
        "font-size:24px;"
        "line-height:1.4;"
        "font-weight:700;"
        "color:#1f1f1f;"
    )
    _H2_STYLE = (
        "margin:30px 0 14px;"
        "padding-left:10px;"
        "border-left:4px solid #1f7a68;"
        "font-size:19px;"
        "line-height:1.45;"
        "font-weight:700;"
        "color:#1f1f1f;"
    )
    _H3_STYLE = (
        "margin:24px 0 12px;"
        "font-size:17px;"
        "line-height:1.45;"
        "font-weight:700;"
        "color:#23685a;"
    )
    _P_STYLE = "margin:0 0 16px;text-align:justify;"
    _LEAD_STYLE = "margin:0 0 18px;color:#5d5d5d;font-size:15px;"
    _BLOCKQUOTE_STYLE = (
        "margin:18px 0;"
        "padding:12px 14px;"
        "border-radius:12px;"
        "background:#f5f8f7;"
        "border-left:4px solid #7db5aa;"
        "color:#5a5a5a;"
        "font-size:15px;"
    )
    _LIST_STYLE = "margin:0 0 18px;padding-left:1.35em;"
    _LI_STYLE = "margin:8px 0;"
    _FIGURE_STYLE = "margin:22px 0;text-align:center;"
    _IMG_STYLE = "max-width:100%;height:auto;border-radius:12px;display:block;margin:0 auto;"
    _FIGCAPTION_STYLE = "margin-top:8px;color:#7b7b7b;font-size:13px;"
    _HR_STYLE = "border:none;border-top:1px solid #e6e1d8;margin:26px 0;"
    _LINK_STYLE = "color:#1f7a68;text-decoration:none;border-bottom:1px solid rgba(31,122,104,0.35);"
    _STRONG_STYLE = "font-weight:700;color:#171717;"
    _CODE_STYLE = (
        "padding:1px 6px;"
        "border-radius:6px;"
        "background:#f3efe8;"
        "font-family:Menlo,Consolas,'SFMono-Regular',monospace;"
        "font-size:14px;"
        "color:#8c3c24;"
    )

    def render_markdown(self, markdown: str) -> WechatLayoutRenderResult:
        normalized_markdown, normalization_warnings = self.normalize_markdown(markdown)
        html = self._render_normalized_markdown(normalized_markdown)
        residual_markdown_markers = self._detect_residual_markdown(normalized_markdown)
        return WechatLayoutRenderResult(
            normalized_markdown=normalized_markdown,
            html=html,
            normalization_warnings=normalization_warnings,
            residual_markdown_markers=residual_markdown_markers,
        )

    def normalize_markdown(self, markdown: str) -> tuple[str, list[str]]:
        text = str(markdown or "").replace("\r\n", "\n").replace("\r", "\n")
        warnings: list[str] = []
        normalized_lines: list[str] = []
        in_code_fence = False

        for raw_line in text.split("\n"):
            line = raw_line.rstrip()
            stripped = line.strip()

            if self._CODE_FENCE_RE.match(stripped):
                self._append_warning(warnings, "code_fence_flattened")
                in_code_fence = not in_code_fence
                continue

            if in_code_fence:
                if stripped:
                    normalized_lines.append(self._normalize_inline_markdown(stripped, warnings))
                else:
                    self._append_blank_line(normalized_lines)
                continue

            if not stripped:
                self._append_blank_line(normalized_lines)
                continue

            if self._TABLE_SEPARATOR_RE.match(stripped):
                self._append_warning(warnings, "table_flattened")
                continue

            if self._TABLE_LINE_RE.match(stripped):
                self._append_warning(warnings, "table_flattened")
                cells = [self._normalize_inline_markdown(cell.strip(), warnings) for cell in stripped.strip("|").split("|")]
                cells = [cell for cell in cells if cell]
                if cells:
                    normalized_lines.append(f"- {' / '.join(cells)}")
                continue

            image_match = self._IMAGE_LINE_RE.match(stripped)
            if image_match:
                alt = self._normalize_inline_markdown(image_match.group(1).strip(), warnings)
                url = self._normalize_url(image_match.group(2).strip())
                if url:
                    normalized_lines.append(f"![{alt}]({url})")
                else:
                    self._append_warning(warnings, "image_url_removed")
                    if alt:
                        normalized_lines.append(alt)
                continue

            heading_match = self._HEADING_RE.match(stripped)
            if heading_match:
                level = min(len(heading_match.group(1)), 3)
                if len(heading_match.group(1)) > 3:
                    self._append_warning(warnings, "heading_demoted")
                heading_text = self._normalize_inline_markdown(heading_match.group(2).strip(), warnings)
                normalized_lines.append(f"{'#' * level} {heading_text}")
                continue

            quote_match = self._BLOCKQUOTE_RE.match(stripped)
            if quote_match:
                normalized_lines.append(f"> {self._normalize_inline_markdown(quote_match.group(1).strip(), warnings)}")
                continue

            task_match = self._TASK_LIST_RE.match(stripped)
            if task_match:
                self._append_warning(warnings, "task_list_flattened")
                normalized_lines.append(f"- {self._normalize_inline_markdown(task_match.group(1).strip(), warnings)}")
                continue

            bullet_match = self._BULLET_LIST_RE.match(stripped)
            if bullet_match:
                normalized_lines.append(f"- {self._normalize_inline_markdown(bullet_match.group(1).strip(), warnings)}")
                continue

            ordered_match = self._ORDERED_LIST_RE.match(stripped)
            if ordered_match:
                normalized_lines.append(
                    f"{ordered_match.group(1)}. {self._normalize_inline_markdown(ordered_match.group(2).strip(), warnings)}"
                )
                continue

            if self._HR_RE.match(stripped):
                normalized_lines.append("---")
                continue

            normalized_lines.append(self._normalize_inline_markdown(stripped, warnings))

        normalized_text = "\n".join(normalized_lines).strip()
        normalized_text = re.sub(r"\n{3,}", "\n\n", normalized_text)
        return normalized_text, warnings

    def ensure_title_heading(self, markdown: str, title: Optional[str], subtitle: Optional[str] = None) -> str:
        normalized = str(markdown or "").strip()
        title_text = str(title or "").strip()
        subtitle_text = str(subtitle or "").strip()
        if not normalized:
            lines = [f"# {title_text}"] if title_text else []
            if subtitle_text:
                lines.extend(["", f"> {subtitle_text}"])
            return "\n".join(lines).strip()

        first_non_empty = next((line.strip() for line in normalized.splitlines() if line.strip()), "")
        if first_non_empty.startswith("# "):
            return normalized

        prefix_lines: list[str] = []
        if title_text:
            prefix_lines.append(f"# {title_text}")
        if subtitle_text:
            if prefix_lines:
                prefix_lines.append("")
            prefix_lines.append(f"> {subtitle_text}")
        if prefix_lines:
            prefix_lines.extend(["", normalized])
            return "\n".join(prefix_lines).strip()
        return normalized

    def _render_normalized_markdown(self, markdown: str) -> str:
        if not markdown:
            return f'<section style="{self._WRAPPER_STYLE}"></section>'

        parts = [f'<section style="{self._WRAPPER_STYLE}">']
        paragraph_buffer: list[str] = []
        quote_buffer: list[str] = []
        list_kind: Optional[str] = None
        list_items: list[str] = []

        def flush_paragraph() -> None:
            nonlocal paragraph_buffer
            if not paragraph_buffer:
                return
            content = "<br />".join(self._render_inline(line) for line in paragraph_buffer)
            style = self._LEAD_STYLE if parts == [f'<section style="{self._WRAPPER_STYLE}">'] else self._P_STYLE
            parts.append(f'<p style="{style}">{content}</p>')
            paragraph_buffer = []

        def flush_quote() -> None:
            nonlocal quote_buffer
            if not quote_buffer:
                return
            content = "<br />".join(self._render_inline(line) for line in quote_buffer)
            parts.append(f'<blockquote style="{self._BLOCKQUOTE_STYLE}">{content}</blockquote>')
            quote_buffer = []

        def flush_list() -> None:
            nonlocal list_kind, list_items
            if not list_kind or not list_items:
                list_kind = None
                list_items = []
                return
            tag = "ol" if list_kind == "ol" else "ul"
            items_html = "".join(f'<li style="{self._LI_STYLE}">{self._render_inline(item)}</li>' for item in list_items)
            parts.append(f'<{tag} style="{self._LIST_STYLE}">{items_html}</{tag}>')
            list_kind = None
            list_items = []

        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line:
                flush_paragraph()
                flush_quote()
                flush_list()
                continue

            image_match = self._IMAGE_LINE_RE.match(line)
            if image_match:
                flush_paragraph()
                flush_quote()
                flush_list()
                alt = self._render_inline(image_match.group(1).strip())
                src = escape(image_match.group(2).strip(), quote=True)
                figure = [
                    f'<figure style="{self._FIGURE_STYLE}">',
                    f'<img src="{src}" alt="{escape(image_match.group(1).strip(), quote=True)}" style="{self._IMG_STYLE}" />',
                ]
                if image_match.group(1).strip():
                    figure.append(f'<figcaption style="{self._FIGCAPTION_STYLE}">{alt}</figcaption>')
                figure.append("</figure>")
                parts.append("".join(figure))
                continue

            if line == "---":
                flush_paragraph()
                flush_quote()
                flush_list()
                parts.append(f'<hr style="{self._HR_STYLE}" />')
                continue

            heading_match = self._HEADING_RE.match(line)
            if heading_match:
                flush_paragraph()
                flush_quote()
                flush_list()
                level = min(len(heading_match.group(1)), 3)
                content = self._render_inline(heading_match.group(2).strip())
                if level == 1:
                    parts.append(f'<h1 style="{self._H1_STYLE}">{content}</h1>')
                elif level == 2:
                    parts.append(f'<h2 style="{self._H2_STYLE}">{content}</h2>')
                else:
                    parts.append(f'<h3 style="{self._H3_STYLE}">{content}</h3>')
                continue

            quote_match = self._BLOCKQUOTE_RE.match(line)
            if quote_match:
                flush_paragraph()
                flush_list()
                quote_buffer.append(quote_match.group(1).strip())
                continue

            ordered_match = self._ORDERED_LIST_RE.match(line)
            if ordered_match:
                flush_paragraph()
                flush_quote()
                if list_kind not in (None, "ol"):
                    flush_list()
                list_kind = "ol"
                list_items.append(ordered_match.group(2).strip())
                continue

            bullet_match = self._BULLET_LIST_RE.match(line)
            if bullet_match:
                flush_paragraph()
                flush_quote()
                if list_kind not in (None, "ul"):
                    flush_list()
                list_kind = "ul"
                list_items.append(bullet_match.group(1).strip())
                continue

            flush_quote()
            flush_list()
            paragraph_buffer.append(line)

        flush_paragraph()
        flush_quote()
        flush_list()
        parts.append("</section>")
        return "".join(parts)

    def _render_inline(self, text: str) -> str:
        result: list[str] = []
        index = 0
        token_re = re.compile(r"\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+?)\*\*|`([^`\n]+)`|\*([^*\n]+)\*")
        for match in token_re.finditer(text):
            start, end = match.span()
            if start > index:
                result.append(escape(text[index:start]))
            if match.group(1) is not None and match.group(2) is not None:
                href = self._normalize_url(match.group(2))
                label = escape(match.group(1))
                if href:
                    result.append(f'<a href="{escape(href, quote=True)}" style="{self._LINK_STYLE}">{label}</a>')
                else:
                    result.append(label)
            elif match.group(3) is not None:
                result.append(f'<strong style="{self._STRONG_STYLE}">{escape(match.group(3))}</strong>')
            elif match.group(4) is not None:
                result.append(f'<code style="{self._CODE_STYLE}">{escape(match.group(4))}</code>')
            elif match.group(5) is not None:
                result.append(f"<em>{escape(match.group(5))}</em>")
            index = end
        if index < len(text):
            result.append(escape(text[index:]))
        return "".join(result)

    def _normalize_inline_markdown(self, text: str, warnings: list[str]) -> str:
        cleaned = text.replace("\t", "  ").strip()
        if self._RAW_HTML_RE.search(cleaned):
            soup = BeautifulSoup(cleaned, "html.parser")
            stripped = soup.get_text(" ", strip=True)
            if stripped and stripped != cleaned:
                cleaned = stripped
                self._append_warning(warnings, "raw_html_stripped")
        if "__" in cleaned:
            cleaned = re.sub(r"__([^_]+?)__", r"**\1**", cleaned)
            self._append_warning(warnings, "underscore_strong_normalized")
        if "~~" in cleaned:
            cleaned = re.sub(r"~~(.+?)~~", r"\1", cleaned)
            self._append_warning(warnings, "strikethrough_removed")
        if "==" in cleaned:
            cleaned = re.sub(r"==(.+?)==", r"**\1**", cleaned)
            self._append_warning(warnings, "highlight_normalized")
        return cleaned

    def _detect_residual_markdown(self, markdown: str) -> list[str]:
        residual: list[str] = []
        for name, pattern in self._RESIDUAL_MARKERS:
            if pattern.search(markdown):
                residual.append(name)
        return residual

    def _normalize_url(self, raw_url: str) -> Optional[str]:
        url = str(raw_url or "").strip()
        if not url:
            return None
        if url.startswith("//"):
            url = f"https:{url}"
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return url
        return None

    def _append_blank_line(self, lines: list[str]) -> None:
        if lines and lines[-1] == "":
            return
        lines.append("")

    def _append_warning(self, warnings: list[str], warning: str) -> None:
        if warning not in warnings:
            warnings.append(warning)
