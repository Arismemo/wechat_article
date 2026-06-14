"""Task 6: EditorialBoardService — 多Agent编委会辩论编排。

流程(spec §4):
  ROUND 0  独立评审   —— 各评审岗(reviewers)互不可见,独立给意见
  ROUND 1..N 辩论     —— 携上一轮意见摘要再评,执行主编每轮判定是否还有新实质异议
                          (无新异议即收敛 break;跑满 MAX 轮则 max_rounds)
  终裁              —— 总编(chief_editor)综合裁决 -> EditorialVerdict
  映射             —— verdict.final_scores -> 一条权威 ReviewReport(驱动现有门禁)

角色分工(本服务的一致约定):
  reviewers = active_roles() 去掉 {chief_editor, managing_editor}
              —— 只有评审岗参与每轮 fan-out 独立评审/辩论。
  managing_editor 只在 _judge_convergence(收敛判定)出场。
  chief_editor    只在 _chief_verdict(终裁)出场。
  即:主席与执行主编不混入评审 fan-out,各司其职,避免双重计票。

并发:每轮内用 ThreadPoolExecutor 并行 fan-out 各评审岗;EditorialLLMClient
内部 BoundedSemaphore 再兜底全局并发上限(单进程内 ≤ max_concurrency)。

降级:context 拼装尽量取 source/brief,缺任何一块都不崩(graceful degrade)。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.content_brief import ContentBrief
from app.models.editorial_review import EditorialReview
from app.models.generation import Generation
from app.models.review_report import ReviewReport
from app.models.source_article import SourceArticle
from app.models.task import Task
from app.repositories.content_brief_repository import ContentBriefRepository
from app.repositories.editorial_review_repository import EditorialReviewRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.editorial import ConvergenceJudgement, EditorialVerdict, RoleOpinion
from app.services.editorial_roles import RoleSpec, active_roles
from app.settings import get_settings

# 这两岗不参与评审 fan-out,只在各自专属步骤出场。
_NON_REVIEWER_ROLE_KEYS = {"chief_editor", "managing_editor"}

# final_scores -> ReviewReport 数值列映射。键缺失时给安全默认值:
#   风险类(*_risk) 缺省 0(无已知风险);其余质量分缺省 60(中性偏过)。
_RISK_SCORE_DEFAULT = 0.0
_QUALITY_SCORE_DEFAULT = 60.0


_ENVELOPE_KEYS = ("answer", "result", "output", "data", "response", "json", "content")


def _unwrap_envelope(raw: Any, *expected: str) -> dict:
    """容忍 LLM 把结构化对象包在信封里(如 {"answer": {...}})。

    raw 顶层缺少所有 expected 字段,但某嵌套 dict(常见信封键或唯一 dict 值)
    含有 expected 字段时,返回该嵌套 dict;否则原样返回。空/非 dict 返回 {}。
    """
    if not isinstance(raw, dict):
        return {}
    if any(k in raw for k in expected):
        return raw
    for key in _ENVELOPE_KEYS:
        inner = raw.get(key)
        if isinstance(inner, dict) and any(k in inner for k in expected):
            return inner
    dict_values = [v for v in raw.values() if isinstance(v, dict)]
    if len(dict_values) == 1 and any(k in dict_values[0] for k in expected):
        return dict_values[0]
    return raw


class EditorialBoardService:
    def __init__(self, session: Session, llm_client) -> None:
        self.session = session
        self.llm = llm_client
        self.settings = get_settings()
        self.tasks = TaskRepository(session)
        self.generations = GenerationRepository(session)
        self.sources = SourceArticleRepository(session)
        self.briefs = ContentBriefRepository(session)
        self.reviews = ReviewReportRepository(session)
        self.editorials = EditorialReviewRepository(session)

    # ------------------------------------------------------------------ 入口
    def review(self, task_id: str) -> EditorialReview:
        task = self.tasks.get_by_id(task_id)
        generation = self.generations.get_latest_by_task_id(task_id)
        if task is None or generation is None:
            raise ValueError("editorial: task/generation missing")

        all_roles = active_roles(self.settings.editorial_role_disabled)
        reviewers = [r for r in all_roles if r.key not in _NON_REVIEWER_ROLE_KEYS]
        context = self._build_context(task, generation)

        record = self.editorials.create(
            EditorialReview(task_id=task_id, generation_id=generation.id, status="running")
        )
        rounds: list[dict] = []

        # ROUND 0: 独立评审(prior=None)。
        opinions = self._fan_out_opinions(reviewers, context, prior=None)
        rounds.append({"round_no": 0, "opinions": [o.model_dump() for o in opinions]})

        # ROUND 1..MAX: 辩论 + 收敛判定。
        max_rounds = self.settings.editorial_max_debate_rounds
        round_no = 0
        status = "max_rounds"
        for round_no in range(1, max_rounds + 1):
            opinions = self._fan_out_opinions(reviewers, context, prior=opinions)
            rounds.append({"round_no": round_no, "opinions": [o.model_dump() for o in opinions]})
            conv = self._judge_convergence(opinions, context)
            if not conv.new_substantive_objection:
                status = "converged"
                break
        else:
            # 循环正常跑完(或 MAX=0 时一次都没进):未收敛。
            round_no = max_rounds

        # 终裁 -> 映射 ReviewReport -> 落库。
        verdict = self._chief_verdict(opinions, context)
        report = self._persist_review_report(task, generation, verdict)
        record = self.editorials.update_result(
            record,
            status=status,
            rounds_used=round_no,
            verdict=verdict,
            transcript={"rounds": rounds},
            review_report_id=report.id,
        )
        return record

    # ------------------------------------------------------------------ fan-out
    def _fan_out_opinions(
        self,
        roles: list[RoleSpec],
        context: str,
        prior: Optional[list[RoleOpinion]],
    ) -> list[RoleOpinion]:
        if not roles:
            return []

        def call(role: RoleSpec) -> RoleOpinion:
            raw = self.llm.complete_json(
                system_prompt=role.system_prompt,
                user_prompt=self._opinion_prompt(role, context, prior),
            )
            raw = _unwrap_envelope(raw, "stance", "role_key")
            raw.setdefault("role_key", role.key)
            return RoleOpinion.model_validate(raw)

        max_workers = max(1, self.settings.editorial_llm_max_concurrency)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            return list(executor.map(call, roles))

    # ------------------------------------------------------------------ 收敛判定
    def _judge_convergence(self, opinions: list[RoleOpinion], context: str) -> ConvergenceJudgement:
        role = self._require_role("managing_editor")
        user_prompt = (
            f"{context}\n\n"
            "本轮各评审岗意见(role_key / stance / 关键论点):\n"
            f"{self._summarize_opinions(opinions)}\n\n"
            f"评审职责:\n{role.rubric}\n\n"
            "请判断本轮辩论相较上一轮是否出现【新的实质性异议】(而非重复旧分歧)。"
            "只输出 JSON,字段:\n"
            '  - new_substantive_objection: bool —— true=仍有新实质异议需继续辩论,false=已收敛\n'
            '  - summary: string —— 一句话说明收敛/分歧现状\n'
        )
        raw = self.llm.complete_json(system_prompt=role.system_prompt, user_prompt=user_prompt)
        raw = _unwrap_envelope(raw, "new_substantive_objection")
        return ConvergenceJudgement.model_validate(raw)

    # ------------------------------------------------------------------ 终裁
    def _chief_verdict(self, opinions: list[RoleOpinion], context: str) -> EditorialVerdict:
        role = self._require_role("chief_editor")
        user_prompt = (
            f"{context}\n\n"
            "全体评审岗最终意见(role_key / stance / 关键论点):\n"
            f"{self._summarize_opinions(opinions)}\n\n"
            f"终裁职责:\n{role.rubric}\n\n"
            "请做出最终裁决,只输出 JSON,字段:\n"
            '  - decision: "pass" | "revise" | "reject"\n'
            "  - final_scores: object,必须且只用以下键(0-100;风险项越高越糟):\n"
            "      similarity, factual_risk, policy_risk, readability, title, novelty, ai_trace, overall\n"
            "  - rationale: string —— 裁决理由(≥1句)\n"
            '  - revision_directives: array —— decision=revise 时给出 [{location, problem, fix}, ...]\n'
            "  - dissent_summary: string —— 保留异议摘要(无则空串)\n"
        )
        raw = self.llm.complete_json(system_prompt=role.system_prompt, user_prompt=user_prompt)
        raw = _unwrap_envelope(raw, "decision", "final_scores")
        return EditorialVerdict.model_validate(raw)

    # ------------------------------------------------------------------ 映射 ReviewReport
    def _persist_review_report(
        self,
        task: Task,
        generation: Generation,
        verdict: EditorialVerdict,
    ) -> ReviewReport:
        scores = verdict.final_scores or {}

        # Fix 1: Chief prompt uses 0-100 for ALL scores; phase4 expects risk columns on 0-1.
        # Convert similarity/factual_risk/policy_risk from 0-100 → 0-1 by dividing by 100.
        # Quality columns (readability/title/novelty) stay on 0-100 as phase4 expects.
        def _risk(key: str) -> float:
            return self._score(scores, key, _RISK_SCORE_DEFAULT * 100.0) / 100.0

        # Fix 2: Map RevisionDirective(location, problem, fix) to rewrite_targets items
        # shaped {block_id, reason, instruction} as expected by extract_review_metadata /
        # _coerce_rewrite_targets in app/core/review_metadata.py.
        raw_directives = [rd.model_dump() for rd in verdict.revision_directives]
        rewrite_targets = [
            {
                "block_id": rd.get("location", ""),
                "reason": rd.get("problem", ""),
                "instruction": rd.get("fix", ""),
            }
            for rd in raw_directives
        ]

        report = self.reviews.create(
            ReviewReport(
                generation_id=generation.id,
                similarity_score=_risk("similarity"),
                factual_risk_score=_risk("factual_risk"),
                policy_risk_score=_risk("policy_risk"),
                readability_score=self._score(scores, "readability", _QUALITY_SCORE_DEFAULT),
                title_score=self._score(scores, "title", _QUALITY_SCORE_DEFAULT),
                novelty_score=self._score(scores, "novelty", _QUALITY_SCORE_DEFAULT),
                # ReviewReport 无 ai_trace/overall 数值列,连同裁决理由/异议存进 issues JSON。
                issues={
                    "source": "editorial_board",
                    "ai_trace_score": self._score(scores, "ai_trace", _QUALITY_SCORE_DEFAULT),
                    "overall_score": self._score(scores, "overall", _QUALITY_SCORE_DEFAULT),
                    "rationale": verdict.rationale,
                    "dissent_summary": verdict.dissent_summary,
                },
                suggestions={
                    # Fix 2: primary key expected by extract_review_metadata.
                    "rewrite_targets": rewrite_targets,
                    # Keep raw directives for traceability (location/problem/fix vocabulary).
                    "revision_directives": raw_directives,
                },
                final_decision=verdict.decision,
            )
        )
        return report

    # ------------------------------------------------------------------ context 拼装
    def _build_context(self, task: Task, generation: Generation) -> str:
        parts: list[str] = ["你正在评审一篇即将发布到微信公众号的稿件。"]

        title = (generation.title or "").strip()
        subtitle = (generation.subtitle or "").strip()
        digest = (generation.digest or "").strip()
        if title:
            parts.append(f"【标题】{title}")
        if subtitle:
            parts.append(f"【副标题】{subtitle}")
        if digest:
            parts.append(f"【摘要】{digest}")

        # 原文/选题简报摘要(取不到就跳过,绝不报错)。
        summary = self._safe_source_summary(task)
        if summary:
            parts.append(f"【源文摘要】{summary}")
        brief_summary = self._safe_brief_summary(task)
        if brief_summary:
            parts.append(f"【选题简报】{brief_summary}")

        markdown = (generation.markdown_content or "").strip()
        parts.append("【稿件正文(Markdown)】\n" + (markdown or "(正文为空)"))
        return "\n\n".join(parts)

    def _safe_source_summary(self, task: Task) -> str:
        try:
            source: Optional[SourceArticle] = self.sources.get_latest_by_task_id(task.id)
        except Exception:
            return ""
        if source is None:
            return ""
        for value in (source.summary, source.cleaned_text):
            text = (value or "").strip()
            if text:
                return text[:1200]
        return ""

    def _safe_brief_summary(self, task: Task) -> str:
        try:
            brief: Optional[ContentBrief] = self.briefs.get_latest_by_task_id(task.id)
        except Exception:
            return ""
        if brief is None:
            return ""
        fields = [
            ("定位", brief.positioning),
            ("新角度", brief.new_angle),
            ("目标读者", brief.target_reader),
        ]
        lines = [f"{label}: {value.strip()}" for label, value in fields if (value or "").strip()]
        return "; ".join(lines)

    # ------------------------------------------------------------------ opinion prompt
    def _opinion_prompt(
        self,
        role: RoleSpec,
        context: str,
        prior: Optional[list[RoleOpinion]],
    ) -> str:
        parts = [
            context,
            f"你的评审职责({role.name} / {role.department}):\n{role.rubric}",
        ]
        if prior:
            parts.append(
                "上一轮各岗意见摘要(role_key / stance / 关键论点),请据此【反驳 / 让步 / 更新】你的立场:\n"
                + self._summarize_opinions(prior)
            )
            parts.append("结合上一轮辩论,重新给出你本轮的独立判断(可坚持也可调整)。")
        else:
            parts.append("这是独立评审轮:请仅依据稿件本身和你的职责给出判断,不参考他人意见。")
        parts.append(
            "只输出 JSON,字段:\n"
            f'  - role_key: "{role.key}"\n'
            "  - scores: object —— 你关注维度的打分(0-100,可为空对象)\n"
            "  - issues: array —— 具体问题列表(可为空)\n"
            '  - stance: "pass" | "revise" | "reject" —— 你的立场,鲜明\n'
            "  - key_argument: string —— 你最核心的一句论点\n"
        )
        return "\n\n".join(parts)

    # ------------------------------------------------------------------ helpers
    def _summarize_opinions(self, opinions: list[RoleOpinion]) -> str:
        if not opinions:
            return "(无)"
        lines = [
            f"- {o.role_key} | {o.stance} | {o.key_argument or '(无)'}"
            for o in opinions
        ]
        return "\n".join(lines)

    def _require_role(self, key: str) -> RoleSpec:
        for role in active_roles():
            if role.key == key:
                return role
        raise ValueError(f"editorial: role {key!r} not found")

    def _score(self, scores: dict[str, Any], key: str, default: float) -> float:
        value = scores.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
