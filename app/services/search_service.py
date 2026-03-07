from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.settings import get_settings
from app.services.url_service import normalize_url


@dataclass
class SearchResult:
    query_text: str
    title: str
    url: str
    summary: str
    source_site: Optional[str]
    published_at: Optional[datetime]


@dataclass
class RankedSearchResult(SearchResult):
    overall_score: float
    relevance_score: float
    diversity_score: float
    factual_density_score: float


class SearchServiceError(RuntimeError):
    pass


class SearchService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def search_many(self, queries: list[str], *, count_per_query: Optional[int] = None) -> list[SearchResult]:
        results: list[SearchResult] = []
        seen_urls: set[str] = set()
        for query in queries:
            for item in self.search(query, count=count_per_query or self.settings.phase3_search_per_query):
                normalized = normalize_url(item.url)
                if normalized in seen_urls:
                    continue
                seen_urls.add(normalized)
                results.append(item)
        return results

    def search(self, query: str, *, count: int) -> list[SearchResult]:
        response = httpx.post(
            self._search_url(),
            headers={
                "Authorization": f"Bearer {self.settings.search_api_key or self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "request_id": str(uuid4()),
                "tool": "web-search-pro",
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": query,
                    }
                ],
                "search_engine": self.settings.search_engine,
                "search_intent": False,
                "count": count,
            },
            timeout=self.settings.search_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        items = self._extract_items(payload)
        if not items:
            return []
        results: list[SearchResult] = []
        for item in items:
            url = str(item.get("link") or "").strip()
            title = str(item.get("title") or "").strip()
            if not url or not title:
                continue
            results.append(
                SearchResult(
                    query_text=query,
                    title=title,
                    url=url,
                    summary=str(item.get("content") or "").strip(),
                    source_site=str(item.get("media") or item.get("refer") or "").strip() or None,
                    published_at=self._parse_publish_date(item.get("publish_date")),
                )
            )
        return results

    def rank_results(
        self,
        *,
        source_url: str,
        source_title: str,
        analysis_theme: str,
        query_texts: list[str],
        results: list[SearchResult],
    ) -> list[RankedSearchResult]:
        source_normalized = normalize_url(source_url)
        theme_keywords = self._keywords(" ".join([source_title, analysis_theme, *query_texts]))
        ranked: list[RankedSearchResult] = []
        used_domains: set[str] = set()

        for item in results:
            normalized = normalize_url(item.url)
            if normalized == source_normalized:
                continue
            content_text = f"{item.title} {item.summary}"
            relevance = self._keyword_overlap(theme_keywords, self._keywords(content_text))
            recency = self._recency_score(item.published_at)
            source_quality = self._source_quality_score(item.url, item.source_site)
            diversity = self._diversity_score(item.url, used_domains)
            factual_density = self._factual_density_score(content_text)
            overall = (
                relevance * 0.35
                + recency * 0.20
                + source_quality * 0.20
                + diversity * 0.15
                + factual_density * 0.10
            )
            ranked.append(
                RankedSearchResult(
                    query_text=item.query_text,
                    title=item.title,
                    url=item.url,
                    summary=item.summary,
                    source_site=item.source_site,
                    published_at=item.published_at,
                    overall_score=round(overall, 4),
                    relevance_score=round(relevance, 4),
                    diversity_score=round(diversity, 4),
                    factual_density_score=round(factual_density, 4),
                )
            )
            used_domains.add(urlparse(item.url).netloc.lower())

        ranked.sort(key=lambda item: item.overall_score, reverse=True)
        return ranked

    def _search_url(self) -> str:
        base_url = (self.settings.search_api_base or "").rstrip("/")
        if base_url.endswith("/web_search"):
            return base_url
        if "/mcp/" in base_url or not base_url:
            return "https://open.bigmodel.cn/api/paas/v4/web_search"
        return f"{base_url}/web_search"

    def _extract_items(self, payload: dict) -> list[dict]:
        if isinstance(payload.get("search_result"), list):
            return payload["search_result"]

        choices = payload.get("choices")
        if not isinstance(choices, list):
            raise SearchServiceError(f"Unsupported search response payload: {payload}")

        for choice in choices:
            message = choice.get("message") if isinstance(choice, dict) else None
            if not isinstance(message, dict):
                continue
            tool_calls = message.get("tool_calls")
            if not isinstance(tool_calls, list):
                continue
            for tool_call in tool_calls:
                function = tool_call.get("function") if isinstance(tool_call, dict) else None
                if not isinstance(function, dict):
                    continue
                arguments = function.get("arguments")
                if isinstance(arguments, dict) and isinstance(arguments.get("search_result"), list):
                    return arguments["search_result"]
        raise SearchServiceError(f"Unsupported search response payload: {payload}")

    def _parse_publish_date(self, raw_value: object) -> Optional[datetime]:
        if not raw_value:
            return None
        text = str(raw_value).strip()
        if not text:
            return None
        for candidate in (text, text.replace("Z", "+00:00")):
            try:
                value = datetime.fromisoformat(candidate)
                if value.tzinfo is None:
                    return value.replace(tzinfo=timezone.utc)
                return value
            except ValueError:
                continue
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def _keywords(self, text: str) -> set[str]:
        keywords: set[str] = set()
        for token in text.replace("｜", " ").replace("|", " ").replace("，", " ").replace("。", " ").split():
            normalized = token.strip().lower()
            if len(normalized) >= 2:
                keywords.add(normalized)
        if not keywords:
            compact = "".join(ch for ch in text if not ch.isspace())
            for size in (2, 3, 4):
                keywords.update(compact[index : index + size] for index in range(max(len(compact) - size + 1, 0)))
        return {item for item in keywords if item}

    def _keyword_overlap(self, left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.1
        overlap = len(left & right)
        baseline = min(max(len(left), 1), max(len(right), 1))
        return min(max(overlap / baseline, 0.1), 1.0)

    def _recency_score(self, published_at: Optional[datetime]) -> float:
        if published_at is None:
            return 0.3
        age_days = max((datetime.now(timezone.utc) - published_at.astimezone(timezone.utc)).days, 0)
        if age_days <= 7:
            return 1.0
        if age_days <= 30:
            return 0.8
        if age_days <= 180:
            return 0.6
        if age_days <= 365:
            return 0.45
        return 0.25

    def _source_quality_score(self, url: str, source_site: Optional[str]) -> float:
        host = urlparse(url).netloc.lower()
        label = (source_site or "").lower()
        if host.endswith("mp.weixin.qq.com"):
            return 0.8
        if any(item in host or item in label for item in ("gov", "edu", "新华社", "人民网", "36kr", "huxiu", "geekpark")):
            return 0.9
        if host.endswith(".org") or host.endswith(".com"):
            return 0.65
        return 0.5

    def _diversity_score(self, url: str, used_domains: set[str]) -> float:
        host = urlparse(url).netloc.lower()
        return 0.9 if host and host not in used_domains else 0.45

    def _factual_density_score(self, text: str) -> float:
        digits = sum(char.isdigit() for char in text)
        evidence_markers = sum(text.count(marker) for marker in ("%", "年", "月", "日", "报告", "数据", "研究", "案例"))
        score = min((digits / 10.0) + (evidence_markers / 6.0), 1.0)
        return max(score, 0.2 if text else 0.0)
