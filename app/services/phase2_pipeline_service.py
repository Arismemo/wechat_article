from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from html import escape
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.models.audit_log import AuditLog
from app.models.generation import Generation
from app.models.source_article import SourceArticle
from app.models.task import Task
from app.models.wechat_draft import WechatDraft
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.wechat_draft_repository import WechatDraftRepository
from app.services.source_fetch_service import FetchedArticle, SourceFetchService
from app.services.wechat_service import WechatDraftArticle, WechatService
from app.settings import get_settings


@dataclass
class Phase2PipelineResult:
    task_id: str
    status: str
    source_title: Optional[str]
    generation_id: Optional[str]
    wechat_media_id: Optional[str]
    snapshot_path: Optional[str]


class Phase2PipelineService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.tasks = TaskRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.source_articles = SourceArticleRepository(session)
        self.generations = GenerationRepository(session)
        self.wechat_drafts = WechatDraftRepository(session)
        self.fetcher = SourceFetchService()
        self.wechat = WechatService()

    def run(self, task_id: str) -> Phase2PipelineResult:
        task = self._require_task(task_id)
        self._set_task_status(task, TaskStatus.FETCHING_SOURCE)
        self._log_action(task.id, "phase2.fetch.started", {"source_url": task.source_url})
        self.session.commit()

        try:
            fetched = self.fetcher.fetch(task.id, task.source_url, task.source_type or "web")
            source_article = self._save_source_article(task, fetched)
            self._set_task_status(task, TaskStatus.SOURCE_READY)
            self._log_action(
                task.id,
                "phase2.fetch.completed",
                {
                    "title": fetched.title,
                    "fetch_method": fetched.fetch_method,
                    "snapshot_path": fetched.snapshot_path,
                    "cover_image_url": fetched.cover_image_url,
                },
            )
            self.session.commit()
        except Exception as exc:
            self._fail_task(task, TaskStatus.FETCH_FAILED, "source_fetch_failed", str(exc))
            raise

        try:
            generation = self._create_test_generation(task, source_article)
            self._set_task_status(task, TaskStatus.PUSHING_WECHAT_DRAFT)
            self._log_action(task.id, "phase2.draft.rendered", {"generation_id": generation.id})
            self.session.commit()

            media_id, push_response = self._push_to_wechat(generation, source_article)
            self.wechat_drafts.create(
                WechatDraft(
                    task_id=task.id,
                    generation_id=generation.id,
                    media_id=media_id,
                    push_status="success",
                    push_response=push_response,
                )
            )
            self._set_task_status(task, TaskStatus.DRAFT_SAVED)
            self._log_action(task.id, "phase2.draft.saved", {"generation_id": generation.id, "media_id": media_id})
            self.session.commit()
        except Exception as exc:
            self._fail_task(task, TaskStatus.PUSH_FAILED, "wechat_push_failed", str(exc))
            raise

        return Phase2PipelineResult(
            task_id=task.id,
            status=task.status,
            source_title=source_article.title,
            generation_id=generation.id,
            wechat_media_id=media_id,
            snapshot_path=source_article.snapshot_path,
        )

    def _require_task(self, task_id: str) -> Task:
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")
        return task

    def _save_source_article(self, task: Task, fetched: FetchedArticle) -> SourceArticle:
        source_article = self.source_articles.get_latest_by_task_id(task.id)
        if source_article is None:
            source_article = self.source_articles.create(SourceArticle(task_id=task.id, url=fetched.final_url))

        source_article.url = fetched.final_url
        source_article.title = fetched.title
        source_article.author = fetched.author
        source_article.published_at = fetched.published_at
        source_article.cover_image_url = fetched.cover_image_url
        source_article.raw_html = fetched.raw_html
        source_article.cleaned_text = fetched.cleaned_text
        source_article.summary = fetched.summary
        source_article.snapshot_path = fetched.snapshot_path
        source_article.fetch_status = "success"
        source_article.word_count = fetched.word_count
        source_article.content_hash = fetched.content_hash
        self.session.flush()
        return source_article

    def _create_test_generation(self, task: Task, source_article: SourceArticle) -> Generation:
        version_no = self.generations.get_next_version_no(task.id)
        html_content = self._render_test_html(task, source_article)
        markdown_content = self._render_test_markdown(task, source_article)
        digest = self._build_digest(source_article.summary)
        generation = self.generations.create(
            Generation(
                task_id=task.id,
                version_no=version_no,
                model_name="phase2-fixed-template",
                title=self._build_draft_title(source_article.title),
                digest=digest,
                markdown_content=markdown_content,
                html_content=html_content,
                status="accepted",
                score_overall=80,
                score_title=70,
                score_readability=85,
                score_novelty=60,
                score_risk=90,
            )
        )
        self.session.flush()
        return generation

    def _push_to_wechat(self, generation: Generation, source_article: SourceArticle) -> tuple[str, dict]:
        if not self.settings.wechat_enable_draft_push:
            raise RuntimeError("WECHAT_ENABLE_DRAFT_PUSH is disabled.")
        thumb_bytes, filename, mime_type = self._resolve_thumb(source_article.cover_image_url)
        material_payload = self.wechat.upload_image_material(thumb_bytes, filename, mime_type)
        rewritten_html, inline_images = self._rewrite_html_images_for_wechat(generation.html_content or "")
        article = WechatDraftArticle(
            title=generation.title or "阶段 2 测试稿",
            author=self._select_author(source_article.author),
            digest=generation.digest or "",
            content=rewritten_html,
            content_source_url=source_article.url,
            thumb_media_id=material_payload["media_id"],
        )
        push_payload = self.wechat.add_draft(article)
        return str(push_payload.get("media_id")), {
            "material": material_payload,
            "inline_images": inline_images,
            "draft": push_payload,
        }

    def _resolve_thumb(self, cover_image_url: Optional[str]) -> tuple[bytes, str, str]:
        if cover_image_url:
            try:
                image_bytes, mime_type = self.fetcher.download_binary(cover_image_url)
                suffix = self._suffix_from_url(cover_image_url, mime_type)
                return image_bytes, f"source-thumb{suffix}", mime_type or "image/png"
            except Exception:
                pass
        return self.wechat.build_fallback_thumb()

    def _render_test_html(self, task: Task, source_article: SourceArticle) -> str:
        excerpt = self._excerpt(source_article.cleaned_text or "")
        published_at = self._format_datetime(source_article.published_at)
        source_images_html = self._render_source_images_html(source_article)
        return (
            "<section>"
            f"<h1>{escape(self._build_draft_title(source_article.title or '未命名文章'))}</h1>"
            "<p>这是一篇阶段 2 联调测试稿，用于验证原文抓取、正文清洗、固定模板渲染和公众号草稿箱写入链路。</p>"
            "<h2>原文信息</h2>"
            "<ul>"
            f"<li>任务编号：{escape(task.task_code)}</li>"
            f"<li>原文标题：{escape(source_article.title or '未命名文章')}</li>"
            f"<li>作者：{escape(source_article.author or '未知')}</li>"
            f"<li>发布时间：{escape(published_at)}</li>"
            f"<li>原文链接：<a href=\"{escape(source_article.url)}\">{escape(source_article.url)}</a></li>"
            "</ul>"
            "<h2>原文摘要</h2>"
            f"<p>{escape(source_article.summary or '无摘要')}</p>"
            f"{source_images_html}"
            "<h2>清洗后正文节选</h2>"
            f"{self._paragraphize_html(excerpt)}"
            "<h2>说明</h2>"
            "<p>该稿仅用于阶段 2 技术联调，不用于正式发布。阶段 3 开始再接入选题重构和多源分析。</p>"
            "</section>"
        )

    def _render_test_markdown(self, task: Task, source_article: SourceArticle) -> str:
        excerpt = self._excerpt(source_article.cleaned_text or "")
        published_at = self._format_datetime(source_article.published_at)
        source_images_markdown = self._render_source_images_markdown(source_article)
        return "\n".join(
            [
                f"# {self._build_draft_title(source_article.title or '未命名文章')}",
                "",
                "这是一篇阶段 2 联调测试稿，用于验证原文抓取、正文清洗、固定模板渲染和公众号草稿箱写入链路。",
                "",
                "## 原文信息",
                f"- 任务编号：{task.task_code}",
                f"- 原文标题：{source_article.title or '未命名文章'}",
                f"- 作者：{source_article.author or '未知'}",
                f"- 发布时间：{published_at}",
                f"- 原文链接：{source_article.url}",
                "",
                "## 原文摘要",
                source_article.summary or "无摘要",
                "",
                *source_images_markdown,
                "",
                "## 清洗后正文节选",
                excerpt,
                "",
                "## 说明",
                "该稿仅用于阶段 2 技术联调，不用于正式发布。阶段 3 开始再接入选题重构和多源分析。",
            ]
        )

    def _build_digest(self, summary: Optional[str]) -> str:
        prefix = (self.settings.wechat_default_digest_prefix or "阶段 2 联调测试稿：").strip()
        digest_body = (summary or "验证原文抓取与草稿箱写入链路。").strip()
        return f"{prefix}{digest_body}"[:120]

    def _build_draft_title(self, source_title: str) -> str:
        title = f"阶段2测试｜{source_title}"
        return title[:64]

    def _excerpt(self, cleaned_text: str) -> str:
        excerpt = cleaned_text[: self.settings.max_source_excerpt_chars].strip()
        if len(cleaned_text) > len(excerpt):
            return f"{excerpt}……"
        return excerpt

    def _paragraphize_html(self, text: str) -> str:
        paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
        return "".join(f"<p>{escape(paragraph)}</p>" for paragraph in paragraphs)

    def _render_source_images_html(self, source_article: SourceArticle) -> str:
        image_urls = self._collect_source_image_urls(source_article)
        if not image_urls:
            return ""
        figures = []
        for index, image_url in enumerate(image_urls, start=1):
            figures.append(
                "<figure>"
                f"<img src=\"{escape(image_url)}\" alt=\"原文配图{index}\" />"
                f"<figcaption>原文配图 {index}</figcaption>"
                "</figure>"
            )
        return (
            "<h2>原文配图</h2>"
            "<p>以下配图来自原文抓取结果，推送草稿前会自动上传到微信并重写 URL。</p>"
            f"{''.join(figures)}"
        )

    def _render_source_images_markdown(self, source_article: SourceArticle) -> list[str]:
        image_urls = self._collect_source_image_urls(source_article)
        if not image_urls:
            return []
        lines = [
            "## 原文配图",
            "以下配图来自原文抓取结果，推送草稿前会自动上传到微信并重写 URL。",
        ]
        lines.extend(f"- 配图 {index}：{image_url}" for index, image_url in enumerate(image_urls, start=1))
        return lines

    def _collect_source_image_urls(self, source_article: SourceArticle) -> list[str]:
        if not self.settings.phase2_include_source_images:
            return []

        urls: list[str] = []
        if source_article.cover_image_url:
            urls.append(source_article.cover_image_url)

        if source_article.raw_html:
            soup = BeautifulSoup(source_article.raw_html, "html.parser")
            content_node = soup.select_one("#js_content") or soup.select_one("article") or soup.select_one("main") or soup.body
            if content_node is not None:
                for node in content_node.select("img"):
                    image_url = self._extract_image_url(node, source_article.url)
                    if image_url and image_url not in urls:
                        urls.append(image_url)
                    if len(urls) >= self.settings.phase2_max_inline_images:
                        break

        return urls[: self.settings.phase2_max_inline_images]

    def _rewrite_html_images_for_wechat(self, html: str) -> tuple[str, list[dict[str, str]]]:
        if not html:
            return html, []

        soup = BeautifulSoup(html, "html.parser")
        upload_logs: list[dict[str, str]] = []

        for index, node in enumerate(soup.select("img"), start=1):
            source_url = self._extract_image_url(node)
            if not source_url:
                continue
            if self._is_wechat_image_url(source_url):
                upload_logs.append({"source_url": source_url, "status": "already_wechat"})
                continue

            try:
                image_bytes, mime_type = self.fetcher.download_binary(source_url)
                if len(image_bytes) > self.settings.wechat_inline_image_max_bytes:
                    raise RuntimeError("image exceeds WECHAT_INLINE_IMAGE_MAX_BYTES")
                filename = f"inline-image-{index}{self._suffix_from_url(source_url, mime_type)}"
                payload = self.wechat.upload_draft_image(image_bytes, filename, mime_type)
                uploaded_url = str(payload.get("url") or "")
                if not uploaded_url:
                    raise RuntimeError("uploadimg response does not contain url")
                node["src"] = uploaded_url
                for attribute in ("data-src", "data-original"):
                    if node.has_attr(attribute):
                        node[attribute] = uploaded_url
                upload_logs.append({"source_url": source_url, "wechat_url": uploaded_url, "status": "uploaded"})
            except Exception as exc:  # noqa: BLE001
                upload_logs.append({"source_url": source_url, "status": "failed", "error": str(exc)[:300]})

        return self._render_html_fragment(soup), upload_logs

    def _select_author(self, source_author: Optional[str]) -> str:
        if self.settings.wechat_default_author:
            return self.settings.wechat_default_author[:16]
        if source_author:
            return source_author[:16]
        return "奇点价值"

    def _format_datetime(self, value) -> str:
        if value is None:
            return "未知"
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return value.isoformat(sep=" ", timespec="seconds")

    def _suffix_from_url(self, url: str, mime_type: Optional[str]) -> str:
        path = urlparse(url).path.lower()
        for suffix in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            if path.endswith(suffix):
                return suffix
        if mime_type == "image/jpeg":
            return ".jpg"
        if mime_type == "image/gif":
            return ".gif"
        if mime_type == "image/webp":
            return ".webp"
        return ".png"

    def _extract_image_url(self, node, base_url: Optional[str] = None) -> Optional[str]:
        for key in ("data-src", "data-original", "src"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return urljoin(base_url or "", value.strip())
        return None

    def _is_wechat_image_url(self, image_url: str) -> bool:
        host = urlparse(image_url).netloc.lower()
        return host.endswith("qpic.cn") or host.endswith("qlogo.cn")

    def _render_html_fragment(self, soup: BeautifulSoup) -> str:
        if soup.body is None:
            return str(soup)
        return "".join(str(child) for child in soup.body.contents)

    def _set_task_status(self, task: Task, status: TaskStatus) -> None:
        task.status = status.value
        task.error_code = None
        task.error_message = None
        self.session.flush()

    def _fail_task(self, task: Task, status: TaskStatus, error_code: str, error_message: str) -> None:
        task.status = status.value
        task.error_code = error_code
        task.error_message = error_message[:1000]
        self._log_action(task.id, f"phase2.failed.{status.value}", {"error_code": error_code, "error_message": error_message})
        self.session.commit()

    def _log_action(self, task_id: str, action: str, payload: Optional[dict]) -> None:
        self.audit_logs.create(AuditLog(task_id=task_id, action=action, operator="system", payload=payload))
