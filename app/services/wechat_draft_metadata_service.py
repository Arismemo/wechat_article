from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

from app.models.wechat_draft import WechatDraft


WECHAT_BACKEND_ENTRY_URL = "https://mp.weixin.qq.com/"


@dataclass(frozen=True)
class WechatDraftMetadata:
    media_id: Optional[str]
    draft_url: Optional[str]
    draft_url_direct: bool
    draft_url_hint: Optional[str]


def build_wechat_draft_metadata(draft: Optional[WechatDraft]) -> WechatDraftMetadata:
    media_id = _normalize_text(draft.media_id) if draft else None
    if draft is None:
        return WechatDraftMetadata(
            media_id=None,
            draft_url=None,
            draft_url_direct=False,
            draft_url_hint=None,
        )

    direct_url = _extract_direct_url(draft.push_response)
    if direct_url:
        return WechatDraftMetadata(
            media_id=media_id,
            draft_url=direct_url,
            draft_url_direct=True,
            draft_url_hint="已拿到微信返回的草稿地址，可直接打开。",
        )

    if media_id:
        return WechatDraftMetadata(
            media_id=media_id,
            draft_url=WECHAT_BACKEND_ENTRY_URL,
            draft_url_direct=False,
            draft_url_hint="微信接口当前只返回 media_id。这里提供公众号后台入口，登录后请在草稿箱按 media_id 核对草稿。",
        )

    return WechatDraftMetadata(
        media_id=None,
        draft_url=None,
        draft_url_direct=False,
        draft_url_hint=None,
    )


def _extract_direct_url(payload: Any) -> Optional[str]:
    candidates = _collect_candidate_urls(payload)
    for candidate in candidates:
        normalized = _normalize_url(candidate)
        if normalized:
            return normalized
    return None


def _collect_candidate_urls(value: Any) -> list[str]:
    candidates: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key in {
                "draft_url",
                "preview_url",
                "page_url",
                "edit_url",
                "article_url",
                "article_link",
                "page_link",
                "link",
                "url",
            } and isinstance(item, str):
                candidates.append(item)
            candidates.extend(_collect_candidate_urls(item))
    elif isinstance(value, list):
        for item in value:
            candidates.extend(_collect_candidate_urls(item))
    return candidates


def _normalize_url(value: str) -> Optional[str]:
    text = _normalize_text(value)
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return None
    host = parsed.netloc.lower()
    if host.endswith("qpic.cn") or host.endswith("qlogo.cn"):
        return None
    return text


def _normalize_text(value: Optional[str]) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
