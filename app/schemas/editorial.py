from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Stance = Literal["pass", "revise", "reject"]

# LLM 真实输出常带中文/大小写/同义词 —— 统一映射到三态。
_STANCE_MAP = {
    "pass": "pass", "通过": "pass", "accept": "pass", "approve": "pass", "ok": "pass", "可发": "pass",
    "revise": "revise", "修改": "revise", "改": "revise", "revision": "revise", "minor": "revise", "待改": "revise",
    "reject": "reject", "驳回": "reject", "毙": "reject", "拒绝": "reject", "fail": "reject", "重写": "reject",
}


def _coerce_stance(v: Any) -> Any:
    if isinstance(v, str):
        key = v.strip().lower()
        for token, mapped in _STANCE_MAP.items():
            if token in key:
                return mapped
    return v  # 未识别原样返回 -> Literal 仍会拒绝(供单测断言)


def _coerce_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        parts = [str(x) for x in v.values() if x not in (None, "")]
        return " | ".join(parts) if parts else json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return " ; ".join(_coerce_str(x) for x in v)
    return str(v)


def _coerce_str_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    if isinstance(v, list):
        return [_coerce_str(x) for x in v if x not in (None, "")]
    return [_coerce_str(v)]


def _coerce_float(v: Any):
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return None
    if isinstance(v, dict):
        for key in ("score", "value", "分", "得分"):
            if key in v:
                return _coerce_float(v[key])
    return None


def _coerce_float_map(v: Any) -> dict:
    if not isinstance(v, dict):
        return {}
    out: dict[str, float] = {}
    for key, val in v.items():
        num = _coerce_float(val)
        if num is not None:
            out[str(key)] = num
    return out


class RoleOpinion(BaseModel):
    role_key: str = ""
    scores: dict[str, float] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    stance: Stance
    key_argument: str = ""

    @field_validator("scores", mode="before")
    @classmethod
    def _v_scores(cls, v: Any) -> dict:
        return _coerce_float_map(v)

    @field_validator("issues", mode="before")
    @classmethod
    def _v_issues(cls, v: Any) -> list[str]:
        return _coerce_str_list(v)

    @field_validator("key_argument", mode="before")
    @classmethod
    def _v_arg(cls, v: Any) -> str:
        return _coerce_str(v)

    @field_validator("stance", mode="before")
    @classmethod
    def _v_stance(cls, v: Any) -> Any:
        return _coerce_stance(v)


class ConvergenceJudgement(BaseModel):
    new_substantive_objection: bool
    summary: str = ""

    @field_validator("summary", mode="before")
    @classmethod
    def _v_summary(cls, v: Any) -> str:
        return _coerce_str(v)


class RevisionDirective(BaseModel):
    location: str = ""
    problem: str = ""
    fix: str = ""

    @field_validator("location", "problem", "fix", mode="before")
    @classmethod
    def _v_str(cls, v: Any) -> str:
        return _coerce_str(v)


def _coerce_directives(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, dict):
        v = [v]
    if not isinstance(v, list):
        return []
    out = []
    for item in v:
        if isinstance(item, str):
            out.append({"fix": item})  # 模型偶把指令写成裸字符串
        else:
            out.append(item)  # dict 或 RevisionDirective 实例 -> 交给 pydantic 校验
    return out


class EditorialVerdict(BaseModel):
    decision: Stance
    final_scores: dict[str, float] = Field(default_factory=dict)
    rationale: str = ""
    revision_directives: list[RevisionDirective] = Field(default_factory=list)
    dissent_summary: str = ""

    @field_validator("decision", mode="before")
    @classmethod
    def _v_decision(cls, v: Any) -> Any:
        return _coerce_stance(v)

    @field_validator("final_scores", mode="before")
    @classmethod
    def _v_scores(cls, v: Any) -> dict:
        return _coerce_float_map(v)

    @field_validator("rationale", "dissent_summary", mode="before")
    @classmethod
    def _v_str(cls, v: Any) -> str:
        return _coerce_str(v)

    @field_validator("revision_directives", mode="before")
    @classmethod
    def _v_directives(cls, v: Any) -> list:
        return _coerce_directives(v)
