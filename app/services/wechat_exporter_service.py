from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import httpx

from app.settings import get_settings


@dataclass
class ExporterAccountMatch:
    fakeid: str
    nickname: str
    alias: str
    signature: str
    service_type: Optional[int]
    verify_status: Optional[int]


@dataclass
class ExporterArticleSummary:
    title: str
    link: str
    digest: Optional[str]
    cover: Optional[str]
    author_name: Optional[str]
    update_time: Optional[int]


class WechatArticleExporterError(RuntimeError):
    pass


class WechatArticleExporterService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = (self.settings.wechat_exporter_base_url or "").rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def download_html(self, article_url: str) -> str:
        response = self._request(
            "/api/public/v1/download",
            params={"url": article_url, "format": "html"},
        )
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = response.json()
            self._raise_for_error(payload)
            raise WechatArticleExporterError("Exporter returned JSON instead of HTML content.")
        return response.text

    def resolve_account_by_url(self, article_url: str) -> Optional[ExporterAccountMatch]:
        payload = self._request_json("/api/public/v1/accountbyurl", params={"url": article_url})
        self._raise_for_error(payload)
        items = payload.get("list") or []
        if not items:
            return None
        item = items[0]
        return ExporterAccountMatch(
            fakeid=str(item.get("fakeid") or ""),
            nickname=str(item.get("nickname") or ""),
            alias=str(item.get("alias") or ""),
            signature=str(item.get("signature") or ""),
            service_type=item.get("service_type"),
            verify_status=item.get("verify_status"),
        )

    def list_articles(self, fakeid: str, begin: int = 0, size: int = 5) -> list[ExporterArticleSummary]:
        payload = self._request_json(
            "/api/public/v1/article",
            params={"fakeid": fakeid, "begin": begin, "size": size},
        )
        self._raise_for_error(payload)
        result: list[ExporterArticleSummary] = []
        for item in payload.get("articles") or []:
            result.append(
                ExporterArticleSummary(
                    title=str(item.get("title") or ""),
                    link=str(item.get("link") or ""),
                    digest=item.get("digest"),
                    cover=item.get("cover") or item.get("cover_img"),
                    author_name=item.get("author_name"),
                    update_time=item.get("update_time"),
                )
            )
        return result

    def _request_json(self, path: str, params: dict[str, object]) -> dict:
        response = self._request(path, params=params)
        payload = response.json()
        self._raise_for_error(payload)
        return payload

    def _request(self, path: str, params: dict[str, object]) -> httpx.Response:
        if not self.enabled:
            raise WechatArticleExporterError("WECHAT_EXPORTER_BASE_URL is not configured.")
        with httpx.Client(timeout=self.settings.wechat_exporter_request_timeout_seconds) as client:
            response = client.get(urljoin(f"{self.base_url}/", path.lstrip("/")), params=params)
        response.raise_for_status()
        return response

    def _raise_for_error(self, payload: dict) -> None:
        base_resp = payload.get("base_resp")
        if not isinstance(base_resp, dict):
            return
        ret = int(base_resp.get("ret", 0) or 0)
        if ret != 0:
            message = base_resp.get("err_msg") or payload.get("message") or "Unknown exporter error"
            raise WechatArticleExporterError(f"Exporter error {ret}: {message}")
