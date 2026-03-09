from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ReviewRewriteTarget:
    block_id: str
    reason: str
    instruction: str


@dataclass
class ReviewMetadata:
    ai_trace_score: Optional[float] = None
    ai_trace_patterns: list[str] = field(default_factory=list)
    rewrite_targets: list[ReviewRewriteTarget] = field(default_factory=list)
    voice_summary: Optional[str] = None
    humanize_applied: bool = False
    humanize_block_ids: list[str] = field(default_factory=list)


def build_review_storage_payloads(
    *,
    issues: Any,
    suggestions: Any,
    ai_trace_score: Any = None,
    ai_trace_patterns: Any = None,
    rewrite_targets: Any = None,
    voice_summary: Any = None,
    humanize_applied: bool = False,
    humanize_block_ids: Any = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    issues_payload = _ensure_items_payload(issues)
    suggestions_payload = _ensure_items_payload(suggestions)

    score = _coerce_float(ai_trace_score)
    if score is not None:
        issues_payload["ai_trace_score"] = round(score, 4)

    patterns = _coerce_string_list(ai_trace_patterns)
    if patterns:
        issues_payload["ai_trace_patterns"] = patterns

    summary = _coerce_text(voice_summary, max_length=240)
    if summary:
        issues_payload["voice_summary"] = summary

    targets = _coerce_rewrite_targets(rewrite_targets)
    if targets:
        suggestions_payload["rewrite_targets"] = [
            {"block_id": item.block_id, "reason": item.reason, "instruction": item.instruction}
            for item in targets
        ]

    block_ids = _coerce_string_list(humanize_block_ids, limit=12)
    if humanize_applied or block_ids:
        suggestions_payload["humanize"] = {
            "applied": bool(humanize_applied),
            "block_ids": block_ids,
        }

    return issues_payload, suggestions_payload


def extract_review_metadata(issues_payload: Optional[dict], suggestions_payload: Optional[dict]) -> ReviewMetadata:
    issues = issues_payload if isinstance(issues_payload, dict) else {}
    suggestions = suggestions_payload if isinstance(suggestions_payload, dict) else {}
    humanize_payload = suggestions.get("humanize")
    humanize = humanize_payload if isinstance(humanize_payload, dict) else {}
    return ReviewMetadata(
        ai_trace_score=_coerce_float(issues.get("ai_trace_score")),
        ai_trace_patterns=_coerce_string_list(issues.get("ai_trace_patterns")),
        rewrite_targets=_coerce_rewrite_targets(suggestions.get("rewrite_targets")),
        voice_summary=_coerce_text(issues.get("voice_summary"), max_length=240),
        humanize_applied=bool(humanize.get("applied")),
        humanize_block_ids=_coerce_string_list(humanize.get("block_ids"), limit=12),
    )


def _ensure_items_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        normalized = dict(payload)
        items = normalized.get("items")
        normalized["items"] = list(items) if isinstance(items, list) else []
        return normalized
    if isinstance(payload, list):
        return {"items": [item for item in payload if item is not None]}
    if payload in (None, ""):
        return {"items": []}
    return {"items": [payload]}


def _coerce_rewrite_targets(payload: Any) -> list[ReviewRewriteTarget]:
    raw_items = payload
    if isinstance(payload, dict):
        raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return []

    targets: list[ReviewRewriteTarget] = []
    seen_block_ids: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        block_id = _coerce_text(item.get("block_id") or item.get("id"), max_length=24)
        if not block_id or block_id in seen_block_ids:
            continue
        reason = _coerce_text(
            item.get("reason") or item.get("issue") or item.get("problem"),
            max_length=120,
        )
        instruction = _coerce_text(
            item.get("instruction") or item.get("rewrite_instruction") or item.get("suggestion"),
            max_length=220,
        )
        if not reason and not instruction:
            continue
        seen_block_ids.add(block_id)
        targets.append(
            ReviewRewriteTarget(
                block_id=block_id,
                reason=reason or "AI trace needs to be reduced.",
                instruction=instruction or "Rewrite this block with a more concrete human voice.",
            )
        )
    return targets


def _coerce_string_list(payload: Any, *, limit: int = 8) -> list[str]:
    raw_items = payload
    if isinstance(payload, dict):
        raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return []

    items: list[str] = []
    for item in raw_items:
        text = _coerce_text(item, max_length=160)
        if not text:
            continue
        items.append(text)
        if len(items) >= limit:
            break
    return items


def _coerce_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_text(value: Any, *, max_length: int) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_length]
