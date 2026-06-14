from __future__ import annotations

import threading
from typing import Any, Optional

import httpx

from app.services.llm_service import LLMService, LLMServiceError


def _extract_json(raw_text: str) -> dict[str, Any]:
    """Delegate to LLMService._extract_json without constructing a full service instance."""
    return LLMService._extract_json(None, raw_text)  # type: ignore[arg-type]


class EditorialLLMClient:
    """编委会专用 LLM 渠道(GLM-5.2),全局并发闸保证 ≤ max_concurrency。

    复用 LLMService 的 JSON 提取逻辑;并发上限只在【单进程】内保证,
    因此 editorial worker 必须单实例运行(见 run_editorial_worker.py 注释)。
    """

    def __init__(self, *, api_base: str, api_key: Optional[str], model: str, max_concurrency: int, timeout_seconds: int = 120) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._semaphore = threading.BoundedSemaphore(max(1, max_concurrency))

    def _completion_url(self) -> str:
        if self.api_base.endswith("/chat/completions"):
            return self.api_base
        return f"{self.api_base}/chat/completions"

    def _raw_completion(self, payload: dict, timeout: int) -> dict:
        response = httpx.post(
            self._completion_url(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            from app.services.llm_service import LLMProviderHTTPError
            raise LLMProviderHTTPError(url=str(exc.request.url), status_code=exc.response.status_code, response_text=exc.response.text) from exc
        return response.json()

    def complete_json(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.4) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        with self._semaphore:
            body = self._raw_completion(payload, self.timeout_seconds)
        choices = body.get("choices")
        if not choices:
            return body  # non-standard body (e.g. in tests); return as-is
        content = choices[0]["message"]["content"]
        if not isinstance(content, str):
            raise LLMServiceError(f"Unexpected editorial completion content: {content!r}")
        return _extract_json(content)  # reuse robust JSON extraction
