from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

Stance = Literal["pass", "revise", "reject"]


class RoleOpinion(BaseModel):
    role_key: str
    scores: dict[str, float] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    stance: Stance
    key_argument: str = ""


class ConvergenceJudgement(BaseModel):
    new_substantive_objection: bool
    summary: str = ""


class RevisionDirective(BaseModel):
    location: str
    problem: str
    fix: str


class EditorialVerdict(BaseModel):
    decision: Stance
    final_scores: dict[str, float] = Field(default_factory=dict)
    rationale: str = ""
    revision_directives: list[RevisionDirective] = Field(default_factory=list)
    dissent_summary: str = ""
