from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from app.settings import get_settings


class LLMServiceError(RuntimeError):
    pass


class LLMProviderHTTPError(LLMServiceError):
    def __init__(self, *, url: str, status_code: int, response_text: str) -> None:
        self.url = url
        self.status_code = status_code
        self.response_text = response_text
        excerpt = (response_text or "").strip()
        if len(excerpt) > 1200:
            excerpt = f"{excerpt[:1200]}..."
        message = (
            f"Client error '{status_code}' for url '{url}'"
            + (f" | response: {excerpt}" if excerpt else "")
        )
        super().__init__(message)


class LLMService:
    def __init__(
        self,
        *,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
    ) -> None:
        self.settings = get_settings()
        self.api_base = api_base
        self.api_key = api_key
        self.default_model = default_model

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        json_mode: bool = False,
        timeout_seconds: Optional[int] = None,
    ) -> dict[str, Any]:
        completion_url = self._completion_url()
        payload = self._build_payload(
            completion_url=completion_url,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model or self.default_model or self.settings.llm_model_analyze,
            temperature=temperature,
            json_mode=json_mode,
        )
        response = httpx.post(
            completion_url,
            headers={
                "Authorization": f"Bearer {self.api_key or self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout_seconds or self.settings.llm_timeout_seconds,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderHTTPError(
                url=str(exc.request.url),
                status_code=exc.response.status_code,
                response_text=exc.response.text,
            ) from exc
        body = response.json()
        try:
            content = self._extract_response_content(completion_url=completion_url, body=body)
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMServiceError(f"Invalid LLM response payload: {body}") from exc
        text = self._normalize_content(content)
        return self._extract_json(text)

    def _completion_url(self) -> str:
        base_url = (self.api_base or self.settings.llm_api_base or "https://open.bigmodel.cn/api/coding/paas/v4").rstrip("/")
        if base_url.endswith("/chat/completions") or base_url.endswith("/responses"):
            return base_url
        return f"{base_url}/chat/completions"

    def _build_payload(
        self,
        *,
        completion_url: str,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        json_mode: bool,
    ) -> dict[str, Any]:
        if completion_url.endswith("/responses"):
            payload: dict[str, Any] = {
                "model": model,
                "input": [
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": system_prompt}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": user_prompt}],
                    },
                ],
                "temperature": temperature,
            }
            if json_mode:
                payload["text"] = {"format": {"type": "json_object"}}
            return payload
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _extract_response_content(self, *, completion_url: str, body: dict[str, Any]) -> Any:
        if completion_url.endswith("/responses"):
            parts: list[dict[str, Any]] = []
            for item in body.get("output") or []:
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "message":
                    continue
                for content_item in item.get("content") or []:
                    if not isinstance(content_item, dict):
                        continue
                    if content_item.get("type") != "output_text":
                        continue
                    text = content_item.get("text")
                    if isinstance(text, str):
                        parts.append({"text": text})
            if parts:
                return parts
            raise LLMServiceError(f"Invalid responses payload: {body}")
        return body["choices"][0]["message"]["content"]

    def _normalize_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts)
        raise LLMServiceError(f"Unsupported LLM content format: {content!r}")

    def _extract_json(self, raw_text: str) -> dict[str, Any]:
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()

        decoder = json.JSONDecoder()
        for start_index, char in enumerate(text):
            if char != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(text[start_index:])
                if isinstance(payload, dict):
                    return payload
            except json.JSONDecodeError:
                continue
        raise LLMServiceError(f"Failed to parse JSON from LLM response: {raw_text[:500]}")
