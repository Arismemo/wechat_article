from __future__ import annotations

DEFAULT_GENERATION_PROMPT_TYPE = "phase4_write"


def resolve_generation_prompt_version(model_name: str | None, *, prompt_type: str = DEFAULT_GENERATION_PROMPT_TYPE) -> str:
    if prompt_type == DEFAULT_GENERATION_PROMPT_TYPE and model_name in {"glm-5", "phase4-fallback-template"}:
        return "phase4-v1"
    return "unknown"


def resolve_generation_prompt_metadata(model_name: str | None) -> tuple[str, str]:
    prompt_type = DEFAULT_GENERATION_PROMPT_TYPE
    return prompt_type, resolve_generation_prompt_version(model_name, prompt_type=prompt_type)
