from __future__ import annotations

import base64
import json
import mimetypes
from dataclasses import dataclass
from typing import Optional

import httpx
from redis.exceptions import RedisError

from app.db.redis_client import get_redis_client
from app.settings import get_settings


FALLBACK_THUMB_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5fN4kAAAAASUVORK5CYII="
)


@dataclass
class WechatDraftArticle:
    title: str
    author: str
    digest: str
    content: str
    content_source_url: str
    thumb_media_id: str


class WechatAPIError(RuntimeError):
    pass


class WechatService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def get_access_token(self) -> str:
        redis_client = None
        try:
            redis_client = get_redis_client()
            cached = redis_client.get(self.settings.wechat_token_cache_key)
            if cached:
                return cached
        except RedisError:
            redis_client = None

        response = httpx.get(
            f"{self.settings.wechat_api_base}/token",
            params={
                "grant_type": "client_credential",
                "appid": self.settings.wechat_app_id,
                "secret": self.settings.wechat_app_secret,
            },
            timeout=self.settings.wechat_request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        self._raise_for_error(payload)
        access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 7200))
        if redis_client is not None:
            try:
                redis_client.setex(self.settings.wechat_token_cache_key, max(expires_in - 300, 60), access_token)
            except RedisError:
                pass
        return access_token

    def upload_image_material(self, image_bytes: bytes, filename: str, mime_type: Optional[str] = None) -> dict:
        access_token = self.get_access_token()
        guessed_mime = mime_type or mimetypes.guess_type(filename)[0] or "image/png"
        with httpx.Client(timeout=self.settings.wechat_request_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.wechat_api_base}/material/add_material",
                params={"access_token": access_token, "type": "image"},
                files={"media": (filename, image_bytes, guessed_mime)},
            )
        response.raise_for_status()
        payload = response.json()
        self._raise_for_error(payload)
        return payload

    def upload_draft_image(self, image_bytes: bytes, filename: str, mime_type: Optional[str] = None) -> dict:
        access_token = self.get_access_token()
        guessed_mime = mime_type or mimetypes.guess_type(filename)[0] or "image/png"
        with httpx.Client(timeout=self.settings.wechat_request_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.wechat_api_base}/media/uploadimg",
                params={"access_token": access_token},
                files={"media": (filename, image_bytes, guessed_mime)},
            )
        response.raise_for_status()
        payload = response.json()
        self._raise_for_error(payload)
        return payload

    def add_draft(self, article: WechatDraftArticle) -> dict:
        access_token = self.get_access_token()
        body = {
            "articles": [
                {
                    "title": article.title,
                    "author": article.author,
                    "digest": article.digest,
                    "content": article.content,
                    "content_source_url": article.content_source_url,
                    "thumb_media_id": article.thumb_media_id,
                }
            ]
        }
        response = httpx.post(
            f"{self.settings.wechat_api_base}/draft/add",
            params={"access_token": access_token},
            content=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=self.settings.wechat_request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        self._raise_for_error(payload)
        return payload

    def build_fallback_thumb(self) -> tuple[bytes, str, str]:
        return FALLBACK_THUMB_PNG, "phase2-thumb.png", "image/png"

    def _raise_for_error(self, payload: dict) -> None:
        errcode = int(payload.get("errcode", 0) or 0)
        if errcode != 0:
            errmsg = payload.get("errmsg", "Unknown WeChat API error")
            raise WechatAPIError(f"WeChat API error {errcode}: {errmsg}")
