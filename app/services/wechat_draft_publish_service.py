from __future__ import annotations

from dataclasses import dataclass
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
from app.services.source_fetch_service import SourceFetchService
from app.services.task_generation_selection_service import TaskGenerationSelectionService
from app.services.wechat_push_policy_service import WechatPushBlockedError, WechatPushPolicyService
from app.services.wechat_layout_service import WechatLayoutService
from app.services.wechat_service import WechatDraftArticle, WechatService
from app.settings import get_settings


@dataclass
class WechatDraftPublishResult:
    task_id: str
    status: str
    generation_id: str
    wechat_media_id: str
    reused_existing: bool


class WechatDraftPublishService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.tasks = TaskRepository(session)
        self.sources = SourceArticleRepository(session)
        self.generations = GenerationRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.wechat_drafts = WechatDraftRepository(session)
        self.push_policy = WechatPushPolicyService(session)
        self.selection = TaskGenerationSelectionService(session)
        self.fetcher = SourceFetchService()
        self.wechat = WechatService()
        self.wechat_layout = WechatLayoutService()

    def push_latest_accepted_generation(self, task_id: str) -> WechatDraftPublishResult:
        task = self._require_task(task_id)
        generation = self.selection.resolve_current_accepted_generation(task_id)
        if generation is None:
            raise ValueError("No accepted generation is available.")
        return self.push_generation(task, generation)

    def push_generation(self, task: Task, generation: Generation) -> WechatDraftPublishResult:
        source_article = self.sources.get_latest_by_task_id(task.id)
        if source_article is None:
            raise ValueError("Source article not found.")

        existing = self.wechat_drafts.get_latest_by_generation_id(generation.id)
        if existing is not None and existing.push_status == "success" and existing.media_id:
            self._set_task_status(task, TaskStatus.DRAFT_SAVED)
            self._log_action(
                task.id,
                "wechat.push.reused_existing",
                {"generation_id": generation.id, "media_id": existing.media_id},
            )
            self.session.commit()
            return WechatDraftPublishResult(
                task_id=task.id,
                status=task.status,
                generation_id=generation.id,
                wechat_media_id=existing.media_id,
                reused_existing=True,
            )

        self._ensure_push_allowed(task.id, generation.id)

        self._set_task_status(task, TaskStatus.PUSHING_WECHAT_DRAFT)
        self._log_action(task.id, "wechat.push.started", {"generation_id": generation.id})
        self.session.commit()

        try:
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
            self._log_action(task.id, "wechat.push.completed", {"generation_id": generation.id, "media_id": media_id})
            self.session.commit()
            return WechatDraftPublishResult(
                task_id=task.id,
                status=task.status,
                generation_id=generation.id,
                wechat_media_id=media_id,
                reused_existing=False,
            )
        except Exception as exc:
            self._fail_task(task, "wechat_push_failed", str(exc))
            raise

    def _push_to_wechat(self, generation: Generation, source_article: SourceArticle) -> tuple[str, dict]:
        if not self.settings.wechat_enable_draft_push:
            raise RuntimeError("WECHAT_ENABLE_DRAFT_PUSH is disabled.")
        thumb_bytes, filename, mime_type = self._resolve_thumb(source_article.cover_image_url)
        material_payload = self.wechat.upload_image_material(thumb_bytes, filename, mime_type)
        rendered_layout = self.wechat_layout.render_markdown(
            self.wechat_layout.ensure_title_heading(
                generation.markdown_content or "",
                generation.title,
                generation.subtitle,
            )
        )
        html_content = rendered_layout.html if rendered_layout.normalized_markdown else (generation.html_content or "")
        rewritten_html, inline_images = self._rewrite_html_images_for_wechat(
            html_content
        )
        article = WechatDraftArticle(
            title=generation.title or "阶段 4 通过稿",
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

    def _ensure_push_allowed(self, task_id: str, generation_id: str) -> None:
        try:
            self.push_policy.ensure_push_allowed(task_id)
        except WechatPushBlockedError:
            policy = self.push_policy.get_policy(task_id)
            self._log_action(
                task_id,
                "phase5.wechat_push.blocked_attempt",
                {
                    "generation_id": generation_id,
                    "mode": policy.mode,
                    "note": policy.note,
                    "operator": policy.operator,
                    "source_action": policy.source_action,
                },
            )
            self.session.commit()
            raise

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

    def _require_task(self, task_id: str) -> Task:
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")
        return task

    def _set_task_status(self, task: Task, status: TaskStatus) -> None:
        self.tasks.update_runtime_state(
            task,
            status=status.value,
            error_code=None,
            error_message=None,
        )

    def _fail_task(self, task: Task, error_code: str, error_message: str) -> None:
        self.tasks.update_runtime_state(
            task,
            status=TaskStatus.PUSH_FAILED.value,
            error_code=error_code,
            error_message=error_message[:1000],
        )
        self._log_action(task.id, "wechat.push.failed", {"error_code": error_code, "error_message": task.error_message})
        self.session.commit()

    def _log_action(self, task_id: str, action: str, payload: Optional[dict]) -> None:
        self.audit_logs.create(AuditLog(task_id=task_id, action=action, operator="system", payload=payload))
