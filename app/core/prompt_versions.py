from __future__ import annotations

DEFAULT_GENERATION_PROMPT_TYPE = "phase4_write"
LEGACY_PHASE4_PROMPT_VERSION = "phase4-v1"
CURRENT_PHASE4_PROMPT_VERSION = "phase4-v2"


def resolve_generation_prompt_version(
    model_name: str | None,
    *,
    prompt_type: str = DEFAULT_GENERATION_PROMPT_TYPE,
    stored_prompt_version: str | None = None,
) -> str:
    if stored_prompt_version:
        return stored_prompt_version
    if prompt_type == DEFAULT_GENERATION_PROMPT_TYPE and model_name in {"glm-5", "phase4-fallback-template"}:
        return LEGACY_PHASE4_PROMPT_VERSION
    return "unknown"


def resolve_generation_prompt_metadata(
    model_name: str | None,
    *,
    stored_prompt_type: str | None = None,
    stored_prompt_version: str | None = None,
) -> tuple[str, str]:
    prompt_type = stored_prompt_type or DEFAULT_GENERATION_PROMPT_TYPE
    return prompt_type, resolve_generation_prompt_version(
        model_name,
        prompt_type=prompt_type,
        stored_prompt_version=stored_prompt_version,
    )
