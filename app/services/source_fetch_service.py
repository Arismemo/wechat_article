from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx
from bs4 import BeautifulSoup

from app.services.storage_service import StorageService
from app.services.wechat_exporter_service import WechatArticleExporterService
from app.settings import get_settings


WHITESPACE_RE = re.compile(r"\s+")
WECHAT_PUBLISH_RE = re.compile(r'var\s+publish_time\s*=\s*"?(?P<ts>\d{10})"?')


@dataclass
class FetchedArticle:
    url: str
    final_url: str
    fetch_method: str
    title: str
    author: Optional[str]
    published_at: Optional[datetime]
    cover_image_url: Optional[str]
    raw_html: str
    cleaned_text: str
    summary: str
    snapshot_path: str
    word_count: int
    content_hash: str


class SourceFetchError(RuntimeError):
    pass


class SourceFetchService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.storage = StorageService()
        self.wechat_exporter = WechatArticleExporterService()

    def fetch(
        self,
        task_id: str,
        url: str,
        source_type: str,
        *,
        snapshot_relative_path: str = "source/source.html",
    ) -> FetchedArticle:
        errors: list[str] = []
        fetch_methods: list[tuple[str, Callable[[str, str], tuple[str, str]]]] = [("http", self._fetch_via_http)]
        if source_type == "wechat" and self.wechat_exporter.enabled:
            fetch_methods.append(("wechat_exporter", self._fetch_via_exporter))
        fetch_methods.append(("playwright", self._fetch_via_playwright))

        for method_name, fetcher in fetch_methods:
            try:
                final_url, html = fetcher(url, source_type)
                parsed = self._parse_fetched_article(source_type, final_url, html, method_name)
                if not parsed.cleaned_text:
                    raise SourceFetchError(f"{method_name} fetched article has empty cleaned_text.")
                snapshot_path = self.storage.write_text(task_id, snapshot_relative_path, html)
                parsed.snapshot_path = snapshot_path
                return parsed
            except Exception as exc:
                errors.append(f"{method_name}: {exc}")

        raise SourceFetchError("; ".join(errors))

    def download_binary(self, url: str) -> tuple[bytes, Optional[str]]:
        with httpx.Client(
            timeout=self.settings.fetch_http_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": self.settings.fetch_user_agent},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content, response.headers.get("content-type")

    def _parse_wechat_article(self, final_url: httpx.URL, html: str) -> FetchedArticle:
        soup = BeautifulSoup(html, "html.parser")
        title = self._meta_content(soup, "property", "og:title") or self._node_text(soup.select_one("#activity-name")) or ""
        author = self._node_text(soup.select_one("#js_name")) or self._meta_content(soup, "name", "author")
        published_at = self._extract_wechat_publish_time(html)
        content_node = soup.select_one("#js_content")
        cleaned_text = self._clean_content_node(content_node)
        summary = self._build_summary(cleaned_text)
        cover_image_url = (
            self._meta_content(soup, "property", "og:image")
            or self._image_url(content_node.select_one("img") if content_node else None)
        )
        return self._build_result("http", final_url, html, title, author, published_at, cover_image_url, cleaned_text, summary)

    def _parse_generic_article(self, final_url: httpx.URL, html: str) -> FetchedArticle:
        soup = BeautifulSoup(html, "html.parser")
        title = (
            self._meta_content(soup, "property", "og:title")
            or self._node_text(soup.title)
            or self._node_text(soup.select_one("h1"))
            or ""
        )
        author = self._meta_content(soup, "name", "author")
        published_at = self._extract_generic_publish_time(soup)
        content_node = soup.select_one("article") or soup.select_one("main") or soup.body
        cleaned_text = self._clean_content_node(content_node)
        summary = self._build_summary(cleaned_text)
        cover_image_url = self._meta_content(soup, "property", "og:image") or self._image_url(
            content_node.select_one("img") if content_node else None
        )
        return self._build_result("http", final_url, html, title, author, published_at, cover_image_url, cleaned_text, summary)

    def _build_result(
        self,
        fetch_method: str,
        final_url: httpx.URL,
        html: str,
        title: str,
        author: Optional[str],
        published_at: Optional[datetime],
        cover_image_url: Optional[str],
        cleaned_text: str,
        summary: str,
    ) -> FetchedArticle:
        compacted_text = cleaned_text.strip()
        word_count = len(compacted_text)
        return FetchedArticle(
            url=str(final_url),
            final_url=str(final_url),
            fetch_method=fetch_method,
            title=title.strip() or "未命名文章",
            author=author.strip() if author else None,
            published_at=published_at,
            cover_image_url=cover_image_url,
            raw_html=html,
            cleaned_text=compacted_text,
            summary=summary,
            snapshot_path="",
            word_count=word_count,
            content_hash=hashlib.sha256(compacted_text.encode("utf-8")).hexdigest(),
        )

    def _fetch_via_http(self, url: str, source_type: str) -> tuple[str, str]:
        del source_type
        with httpx.Client(
            timeout=self.settings.fetch_http_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": self.settings.fetch_user_agent},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return str(response.url), response.text

    def _fetch_via_exporter(self, url: str, source_type: str) -> tuple[str, str]:
        if source_type != "wechat":
            raise SourceFetchError("Exporter fallback currently supports only WeChat article URLs.")
        return url, self.wechat_exporter.download_html(url)

    def _fetch_via_playwright(self, url: str, source_type: str) -> tuple[str, str]:
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise SourceFetchError("Playwright is not installed in the runtime environment.") from exc

        timeout_ms = self.settings.fetch_browser_timeout_seconds * 1000
        try:
            with sync_playwright() as playwright:
                launch_errors: list[str] = []
                for channel in self._playwright_channels():
                    browser = None
                    context = None
                    try:
                        browser = playwright.chromium.launch(
                            channel=channel,
                            headless=self.settings.playwright_headless,
                        )
                        context = browser.new_context(
                            user_agent=self.settings.fetch_user_agent,
                            viewport={
                                "width": self.settings.playwright_viewport_width,
                                "height": self.settings.playwright_viewport_height,
                            },
                            is_mobile=True,
                            has_touch=True,
                            locale="zh-CN",
                        )
                        page = context.new_page()
                        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                        if source_type == "wechat":
                            try:
                                page.wait_for_selector("#js_content", timeout=timeout_ms)
                            except PlaywrightError:
                                pass
                        try:
                            page.wait_for_load_state("networkidle", timeout=timeout_ms)
                        except PlaywrightError:
                            pass
                        html = page.content()
                        final_url = page.url
                        return final_url, html
                    except Exception as exc:  # noqa: BLE001
                        label = channel or "default"
                        launch_errors.append(f"{label}: {exc}")
                    finally:
                        if context is not None:
                            context.close()
                        if browser is not None:
                            browser.close()
        except PlaywrightError as exc:
            raise SourceFetchError(f"Playwright fallback failed: {exc}") from exc
        raise SourceFetchError("Playwright fallback failed: " + "; ".join(launch_errors))

    def _parse_fetched_article(self, source_type: str, final_url: str, html: str, fetch_method: str) -> FetchedArticle:
        parsed_url = httpx.URL(final_url)
        if source_type == "wechat":
            parsed = self._parse_wechat_article(parsed_url, html)
        else:
            parsed = self._parse_generic_article(parsed_url, html)
        parsed.fetch_method = fetch_method
        return parsed

    def _clean_content_node(self, node) -> str:
        if node is None:
            return ""

        for bad_node in node.select("script, style, noscript"):
            bad_node.decompose()

        lines: list[str] = []
        for element in node.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
            text = WHITESPACE_RE.sub(" ", element.get_text(" ", strip=True)).strip()
            if text:
                lines.append(text)

        if not lines:
            fallback_text = WHITESPACE_RE.sub(" ", node.get_text(" ", strip=True)).strip()
            return fallback_text
        return "\n\n".join(lines)

    def _build_summary(self, cleaned_text: str) -> str:
        if not cleaned_text:
            return ""
        lines = [line.strip() for line in cleaned_text.split("\n") if line.strip()]
        summary = " ".join(lines[:3])
        return summary[:220]

    def _extract_wechat_publish_time(self, html: str) -> Optional[datetime]:
        match = WECHAT_PUBLISH_RE.search(html)
        if match is None:
            return None
        return datetime.fromtimestamp(int(match.group("ts")), tz=timezone.utc)

    def _extract_generic_publish_time(self, soup: BeautifulSoup) -> Optional[datetime]:
        for attr_name, attr_value in (("property", "article:published_time"), ("name", "pubdate"), ("name", "publishdate")):
            raw = self._meta_content(soup, attr_name, attr_value)
            if not raw:
                continue
            try:
                normalized = raw.replace("Z", "+00:00")
                return datetime.fromisoformat(normalized)
            except ValueError:
                continue
        return None

    def _meta_content(self, soup: BeautifulSoup, attr_name: str, attr_value: str) -> Optional[str]:
        node = soup.find("meta", attrs={attr_name: attr_value})
        if node is None:
            return None
        content = node.get("content")
        return content.strip() if isinstance(content, str) and content.strip() else None

    def _node_text(self, node) -> Optional[str]:
        if node is None:
            return None
        text = WHITESPACE_RE.sub(" ", node.get_text(" ", strip=True)).strip()
        return text or None

    def _image_url(self, node) -> Optional[str]:
        if node is None:
            return None
        for key in ("data-src", "data-original", "src"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _playwright_channels(self) -> list[Optional[str]]:
        raw_channels = [item.strip() for item in self.settings.playwright_browser_channels.split(",")]
        channels = [item or None for item in raw_channels if item.strip()]
        if not channels:
            return [None]
        return channels
