from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from app.settings import get_settings


class LLMServiceError(RuntimeError):
    pass


class LLMService:
    def __init__(self) -> None:
        self.settings = get_settings()

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
        payload = {
            "model": model or self.settings.llm_model_analyze,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = httpx.post(
            self._completion_url(),
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout_seconds or self.settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMServiceError(f"Invalid LLM response payload: {body}") from exc
        text = self._normalize_content(content)
        return self._extract_json(text)

    def _completion_url(self) -> str:
        base_url = (self.settings.llm_api_base or "https://open.bigmodel.cn/api/coding/paas/v4").rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"

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
