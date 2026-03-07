from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.models.article_analysis import ArticleAnalysis
from app.models.audit_log import AuditLog
from app.models.content_brief import ContentBrief
from app.models.generation import Generation
from app.models.related_article import RelatedArticle
from app.models.review_report import ReviewReport
from app.models.source_article import SourceArticle
from app.models.task import Task
from app.repositories.article_analysis_repository import ArticleAnalysisRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.content_brief_repository import ContentBriefRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.related_article_repository import RelatedArticleRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.task_repository import TaskRepository
from app.services.llm_service import LLMService, LLMServiceError
from app.services.phase3_pipeline_service import Phase3PipelineService
from app.services.wechat_draft_publish_service import WechatDraftPublishService
from app.settings import get_settings


@dataclass
class Phase4PipelineResult:
    task_id: str
    status: str
    generation_id: Optional[str]
    review_report_id: Optional[str]
    decision: Optional[str]
    auto_revised: bool


class Phase4PipelineService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.tasks = TaskRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.sources = SourceArticleRepository(session)
        self.analyses = ArticleAnalysisRepository(session)
        self.briefs = ContentBriefRepository(session)
        self.related_articles = RelatedArticleRepository(session)
        self.generations = GenerationRepository(session)
        self.reviews = ReviewReportRepository(session)
        self.llm = LLMService()
        self.wechat_publisher = WechatDraftPublishService(session)

    def run(self, task_id: str) -> Phase4PipelineResult:
        task = self._require_task(task_id)
        source, analysis, brief, related = self._ensure_phase3_inputs(task)

        try:
            generation = self._generate_generation(
                task=task,
                source=source,
                analysis=analysis,
                brief=brief,
                related=related,
            )
        except Exception as exc:
            self._fail_task(task, TaskStatus.GENERATE_FAILED, "phase4_generate_failed", str(exc))
            raise

        try:
            review = self._review_generation(
                task=task,
                source=source,
                brief=brief,
                related=related,
                generation=generation,
            )
        except Exception as exc:
            self._fail_task(task, TaskStatus.REVIEW_FAILED, "phase4_review_failed", str(exc))
            raise

        decision = self._normalize_decision(review.final_decision)
        if decision == "pass" and self._passes_thresholds(review):
            return self._mark_review_passed(task, generation, review, auto_revised=False)
        if decision == "reject":
            return self._mark_needs_regenerate(task, generation, review)
        if decision == "revise" and self.settings.phase4_max_auto_revisions > 0:
            return self._auto_revise_once(task, source, analysis, brief, related, generation, review)
        return self._mark_needs_manual_review(task, generation, review, auto_revised=False)

    def _ensure_phase3_inputs(
        self,
        task: Task,
    ) -> tuple[SourceArticle, ArticleAnalysis, ContentBrief, list[RelatedArticle]]:
        source = self.sources.get_latest_by_task_id(task.id)
        analysis = self.analyses.get_latest_by_task_id(task.id)
        brief = self.briefs.get_latest_by_task_id(task.id)
        related = self.related_articles.list_selected_by_task_id(task.id)

        if source is not None and analysis is not None and brief is not None and related:
            return source, analysis, brief, related

        Phase3PipelineService(self.session).run(task.id)

        source = self.sources.get_latest_by_task_id(task.id)
        analysis = self.analyses.get_latest_by_task_id(task.id)
        brief = self.briefs.get_latest_by_task_id(task.id)
        related = self.related_articles.list_selected_by_task_id(task.id)
        if source is None or analysis is None or brief is None or not related:
            raise ValueError("Phase 3 prerequisites are not ready.")
        return source, analysis, brief, related

    def _generate_generation(
        self,
        *,
        task: Task,
        source: SourceArticle,
        analysis: ArticleAnalysis,
        brief: ContentBrief,
        related: list[RelatedArticle],
        prior_generation: Optional[Generation] = None,
        prior_review: Optional[ReviewReport] = None,
    ) -> Generation:
        self._set_task_status(task, TaskStatus.GENERATING)
        self._log_action(
            task.id,
            "phase4.generation.started",
            {
                "brief_id": brief.id,
                "revision_from_generation_id": prior_generation.id if prior_generation else None,
            },
        )
        self.session.commit()

        payload, model_name = self._build_generation_payload(
            task_id=task.id,
            source=source,
            analysis=analysis,
            brief=brief,
            related=related,
            prior_generation=prior_generation,
            prior_review=prior_review,
        )
        markdown_content = str(payload.get("markdown_content") or "").strip()
        if not markdown_content:
            raise ValueError("Generated draft does not contain markdown_content.")

        generation = self.generations.create(
            Generation(
                task_id=task.id,
                brief_id=brief.id,
                version_no=self.generations.get_next_version_no(task.id),
                model_name=model_name,
                title=self._limit(str(payload.get("title") or self._fallback_title(source, brief)), 64),
                subtitle=self._limit(str(payload.get("subtitle") or ""), 120) or None,
                digest=self._limit(str(payload.get("digest") or self._fallback_digest(source, brief)), 120),
                markdown_content=markdown_content,
                html_content=self._render_markdown_to_html(markdown_content),
                status="generated",
            )
        )
        self._log_action(
            task.id,
            "phase4.generation.completed",
            {"generation_id": generation.id, "version_no": generation.version_no, "model_name": generation.model_name},
        )
        self.session.commit()
        return generation

    def _review_generation(
        self,
        *,
        task: Task,
        source: SourceArticle,
        brief: ContentBrief,
        related: list[RelatedArticle],
        generation: Generation,
    ) -> ReviewReport:
        self._set_task_status(task, TaskStatus.REVIEWING)
        self._log_action(task.id, "phase4.review.started", {"generation_id": generation.id})
        self.session.commit()

        payload = self._build_review_payload(
            task_id=task.id,
            source=source,
            brief=brief,
            related=related,
            generation=generation,
        )
        report = self.reviews.create(
            ReviewReport(
                generation_id=generation.id,
                similarity_score=self._coerce_float(payload.get("similarity_score")),
                factual_risk_score=self._coerce_float(payload.get("factual_risk_score")),
                policy_risk_score=self._coerce_float(payload.get("policy_risk_score")),
                readability_score=self._coerce_float(payload.get("readability_score")),
                title_score=self._coerce_float(payload.get("title_score")),
                novelty_score=self._coerce_float(payload.get("novelty_score")),
                issues=self._wrap_list(payload.get("issues")),
                suggestions=self._wrap_list(payload.get("suggestions")),
                final_decision=self._normalize_decision(str(payload.get("final_decision") or "revise")),
            )
        )
        self._apply_review_scores(generation, report)
        self._log_action(
            task.id,
            "phase4.review.completed",
            {
                "generation_id": generation.id,
                "review_report_id": report.id,
                "decision": report.final_decision,
                "overall_score": generation.score_overall,
            },
        )
        self.session.commit()
        return report

    def _auto_revise_once(
        self,
        task: Task,
        source: SourceArticle,
        analysis: ArticleAnalysis,
        brief: ContentBrief,
        related: list[RelatedArticle],
        prior_generation: Generation,
        prior_review: ReviewReport,
    ) -> Phase4PipelineResult:
        self._log_action(
            task.id,
            "phase4.revision.started",
            {"generation_id": prior_generation.id, "review_report_id": prior_review.id},
        )
        self.session.commit()

        try:
            revised_generation = self._generate_generation(
                task=task,
                source=source,
                analysis=analysis,
                brief=brief,
                related=related,
                prior_generation=prior_generation,
                prior_review=prior_review,
            )
            revised_review = self._review_generation(
                task=task,
                source=source,
                brief=brief,
                related=related,
                generation=revised_generation,
            )
        except Exception as exc:
            self._fail_task(task, TaskStatus.REVIEW_FAILED, "phase4_auto_revise_failed", str(exc))
            raise

        decision = self._normalize_decision(revised_review.final_decision)
        if decision == "pass" and self._passes_thresholds(revised_review):
            return self._mark_review_passed(task, revised_generation, revised_review, auto_revised=True)
        if decision == "reject":
            return self._mark_needs_regenerate(task, revised_generation, revised_review)
        return self._mark_needs_manual_review(task, revised_generation, revised_review, auto_revised=True)

    def _mark_review_passed(
        self,
        task: Task,
        generation: Generation,
        review: ReviewReport,
        *,
        auto_revised: bool,
    ) -> Phase4PipelineResult:
        generation.status = "accepted"
        self._set_task_status(task, TaskStatus.REVIEW_PASSED)
        self._log_action(
            task.id,
            "phase4.review.passed",
            {"generation_id": generation.id, "review_report_id": review.id, "auto_revised": auto_revised},
        )
        self.session.commit()
        if self.settings.phase4_auto_push_wechat_draft:
            return self._auto_push_wechat_draft(task, generation, review, auto_revised=auto_revised)
        return Phase4PipelineResult(
            task_id=task.id,
            status=task.status,
            generation_id=generation.id,
            review_report_id=review.id,
            decision=review.final_decision,
            auto_revised=auto_revised,
        )

    def _auto_push_wechat_draft(
        self,
        task: Task,
        generation: Generation,
        review: ReviewReport,
        *,
        auto_revised: bool,
    ) -> Phase4PipelineResult:
        if not self.settings.wechat_enable_draft_push:
            self._log_action(
                task.id,
                "phase4.wechat_push.skipped",
                {"generation_id": generation.id, "reason": "WECHAT_ENABLE_DRAFT_PUSH disabled"},
            )
            self.session.commit()
            return Phase4PipelineResult(
                task_id=task.id,
                status=task.status,
                generation_id=generation.id,
                review_report_id=review.id,
                decision=review.final_decision,
                auto_revised=auto_revised,
            )

        try:
            publish_result = self.wechat_publisher.push_generation(task, generation)
            return Phase4PipelineResult(
                task_id=task.id,
                status=publish_result.status,
                generation_id=generation.id,
                review_report_id=review.id,
                decision=review.final_decision,
                auto_revised=auto_revised,
            )
        except Exception:
            return Phase4PipelineResult(
                task_id=task.id,
                status=task.status,
                generation_id=generation.id,
                review_report_id=review.id,
                decision=review.final_decision,
                auto_revised=auto_revised,
            )

    def _mark_needs_regenerate(self, task: Task, generation: Generation, review: ReviewReport) -> Phase4PipelineResult:
        generation.status = "rejected"
        self._set_task_status(task, TaskStatus.NEEDS_REGENERATE)
        self._log_action(
            task.id,
            "phase4.review.rejected",
            {"generation_id": generation.id, "review_report_id": review.id},
        )
        self.session.commit()
        return Phase4PipelineResult(
            task_id=task.id,
            status=task.status,
            generation_id=generation.id,
            review_report_id=review.id,
            decision=review.final_decision,
            auto_revised=False,
        )

    def _mark_needs_manual_review(
        self,
        task: Task,
        generation: Generation,
        review: ReviewReport,
        *,
        auto_revised: bool,
    ) -> Phase4PipelineResult:
        generation.status = "needs_manual_review"
        self._set_task_status(task, TaskStatus.NEEDS_MANUAL_REVIEW)
        self._log_action(
            task.id,
            "phase4.review.manual_required",
            {"generation_id": generation.id, "review_report_id": review.id, "auto_revised": auto_revised},
        )
        self.session.commit()
        return Phase4PipelineResult(
            task_id=task.id,
            status=task.status,
            generation_id=generation.id,
            review_report_id=review.id,
            decision=review.final_decision,
            auto_revised=auto_revised,
        )

    def _build_generation_payload(
        self,
        *,
        task_id: str,
        source: SourceArticle,
        analysis: ArticleAnalysis,
        brief: ContentBrief,
        related: list[RelatedArticle],
        prior_generation: Optional[Generation],
        prior_review: Optional[ReviewReport],
    ) -> tuple[dict[str, Any], str]:
        system_prompt = (
            "你是微信公众号资深编辑。"
            "请基于输入的原文分析、content_brief 和同题素材，输出严格 JSON。"
            "不要输出 Markdown 解释，不要输出代码块。"
        )
        user_prompt = (
            "请返回 JSON，字段固定为：title,subtitle,digest,markdown_content。"
            "其中 markdown_content 必须是一篇完整的新稿，必须包含一级标题、至少三个二级标题，"
            "并明确体现新的论证顺序和信息增量。\n\n"
            f"原文标题：{source.title or '未知'}\n"
            f"原文摘要：{source.summary or '无'}\n"
            f"原文分析主题：{analysis.theme or '未知'}\n"
            f"原文分析角度：{analysis.angle or '未知'}\n"
            f"目标读者：{brief.target_reader or '泛技术读者'}\n"
            f"重构定位：{brief.positioning or '未提供'}\n"
            f"新角度：{brief.new_angle or '未提供'}\n"
            f"必须覆盖：{self._json_items(brief.must_cover)}\n"
            f"必须避免：{self._json_items(brief.must_avoid)}\n"
            f"差异矩阵：{self._json_items(brief.difference_matrix)}\n"
            f"推荐大纲：{self._json_items(brief.outline)}\n"
            f"标题方向：{self._json_items(brief.title_directions)}\n"
            f"同题素材：{self._related_context(related)}\n"
        )
        if prior_generation is not None and prior_review is not None:
            user_prompt += (
                f"\n上一版标题：{prior_generation.title or '无'}\n"
                f"上一版摘要：{prior_generation.digest or '无'}\n"
                f"上一版审稿结论：{prior_review.final_decision or 'revise'}\n"
                f"审稿问题：{self._json_items(prior_review.issues)}\n"
                f"审稿建议：{self._json_items(prior_review.suggestions)}\n"
                "请保留核心新角度，但根据审稿建议完成一次实质性修订。\n"
            )
        try:
            return (
                self.llm.complete_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=self.settings.llm_model_write,
                    temperature=0.6,
                    json_mode=True,
                    timeout_seconds=self.settings.llm_write_timeout_seconds,
                ),
                self.settings.llm_model_write,
            )
        except Exception as exc:
            self._log_action(
                task_id,
                "phase4.generation.fallback",
                {"reason": str(exc)[:500], "fallback_model": "phase4-fallback-template"},
            )
            return self._build_generation_fallback(source=source, analysis=analysis, brief=brief, related=related), "phase4-fallback-template"

    def _build_review_payload(
        self,
        *,
        task_id: str,
        source: SourceArticle,
        brief: ContentBrief,
        related: list[RelatedArticle],
        generation: Generation,
    ) -> dict[str, Any]:
        system_prompt = (
            "你是内容审稿编辑。"
            "请对输入稿件做结构化审稿，并输出严格 JSON。"
            "不要输出 Markdown，不要解释。"
        )
        user_prompt = (
            "请返回 JSON，字段固定为："
            "final_decision,similarity_score,factual_risk_score,policy_risk_score,"
            "readability_score,title_score,novelty_score,issues,suggestions。"
            "其中 final_decision 只能是 pass/revise/reject；"
            "similarity_score/factual_risk_score/policy_risk_score 使用 0 到 1 浮点数；"
            "其余分数使用 0 到 100 数值；issues/suggestions 为字符串数组。\n\n"
            f"原文标题：{source.title or '未知'}\n"
            f"原文摘要：{source.summary or '无'}\n"
            f"新角度：{brief.new_angle or '未提供'}\n"
            f"必须覆盖：{self._json_items(brief.must_cover)}\n"
            f"必须避免：{self._json_items(brief.must_avoid)}\n"
            f"参考素材：{self._related_titles(related)}\n"
            f"生成稿标题：{generation.title or '无'}\n"
            f"生成稿摘要：{generation.digest or '无'}\n"
            f"生成稿正文：{(generation.markdown_content or '')[:4500]}\n"
        )
        try:
            return self.llm.complete_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self.settings.llm_model_review,
                temperature=0.2,
                json_mode=True,
                timeout_seconds=self.settings.llm_review_timeout_seconds,
            )
        except (LLMServiceError, Exception) as exc:
            self._log_action(
                task_id,
                "phase4.review.fallback",
                {"reason": str(exc)[:500], "generation_id": generation.id},
            )
            return self._build_review_fallback(source=source, brief=brief, related=related, generation=generation)

    def _build_generation_fallback(
        self,
        *,
        source: SourceArticle,
        analysis: ArticleAnalysis,
        brief: ContentBrief,
        related: list[RelatedArticle],
    ) -> dict[str, str]:
        must_cover = self._items_from_json(brief.must_cover)[:4]
        must_avoid = self._items_from_json(brief.must_avoid)[:3]
        outline = self._items_from_json(brief.outline)[:3]
        related_points = [item.title or item.url for item in related[:3]]
        title = self._fallback_title(source, brief)
        subtitle = brief.target_reader or analysis.audience or "给技术读者的一次重构解读"
        digest = self._fallback_digest(source, brief)
        markdown_lines = [
            f"# {title}",
            "",
            f"> {subtitle}",
            "",
            "## 先说结论：这篇内容为什么值得重写",
            f"{brief.new_angle or '这篇稿件将从新的判断框架切入，而不是重复原文顺序。'}",
            "",
            "## 这次重构必须讲清楚的三件事",
        ]
        markdown_lines.extend(f"- {item}" for item in must_cover or ["核心定义", "关键判断", "常见误区"])
        markdown_lines.extend(
            [
                "",
                "## 原文之外，读者真正需要补上的信息",
                f"{source.summary or source.cleaned_text[:180] or '原文基础信息已给出，但没有展开真正影响判断的上下文。'}",
                "",
                "## 结合同题素材，可以换一个更稳的解释框架",
            ]
        )
        markdown_lines.extend(f"- 参考：{item}" for item in related_points or ["补充一手与二手视角"])
        markdown_lines.extend(
            [
                "",
                "## 写作时需要刻意避免什么",
                *(f"- {item}" for item in must_avoid or ["照搬原文顺序", "把结论写成绝对化判断"]),
                "",
                "## 推荐成稿结构",
            ]
        )
        markdown_lines.extend(f"- {item}" for item in outline or ["开头纠偏", "中段展开判断框架", "结尾给出落地结论"])
        markdown_lines.extend(
            [
                "",
                "## 收尾",
                "最终成稿应让读者拿到一个更清晰、更可执行的理解框架，而不是重复原文表述。",
            ]
        )
        return {
            "title": title,
            "subtitle": subtitle,
            "digest": digest,
            "markdown_content": "\n".join(markdown_lines),
        }

    def _build_review_fallback(
        self,
        *,
        source: SourceArticle,
        brief: ContentBrief,
        related: list[RelatedArticle],
        generation: Generation,
    ) -> dict[str, Any]:
        markdown = generation.markdown_content or ""
        similarity = self._similarity_heuristic(source.cleaned_text or "", markdown)
        readability = 88.0 if len(markdown) >= 600 and "## " in markdown else 66.0
        title_score = 84.0 if 8 <= len(generation.title or "") <= 32 else 68.0
        novelty = 84.0 if (brief.new_angle or "") and (brief.new_angle or "") not in (source.title or "") else 72.0
        policy_risk = 0.15 if not self._contains_policy_keywords(markdown) else 0.55
        factual_risk = 0.2 if len(related) >= 3 else 0.38

        issues: list[str] = []
        suggestions: list[str] = []
        if similarity > self.settings.phase4_similarity_max:
            issues.append("与原文关键词重合度偏高，可能缺少足够的信息重构。")
            suggestions.append("调整段落顺序，并补入来自同题素材的新解释和判断。")
        if readability < 70:
            issues.append("结构不够稳定，二级标题和分段不足。")
            suggestions.append("按“纠偏-展开-结论”重排结构，并缩短单段长度。")
        if factual_risk > self.settings.phase4_factual_risk_max:
            issues.append("支撑素材不足，事实风险偏高。")
            suggestions.append("增加来自同题素材的事实点和对比论据。")
        if policy_risk > self.settings.phase4_policy_risk_max:
            issues.append("出现高风险或绝对化表述。")
            suggestions.append("改写敏感措辞，避免带结论性断言。")

        if policy_risk > self.settings.phase4_policy_risk_max + 0.1:
            decision = "reject"
        elif issues:
            decision = "revise"
        else:
            decision = "pass"

        return {
            "final_decision": decision,
            "similarity_score": round(similarity, 4),
            "factual_risk_score": round(factual_risk, 4),
            "policy_risk_score": round(policy_risk, 4),
            "readability_score": readability,
            "title_score": title_score,
            "novelty_score": novelty,
            "issues": issues or ["未发现明显结构性问题。"],
            "suggestions": suggestions or ["可以进入下一阶段。"],
        }

    def _apply_review_scores(self, generation: Generation, review: ReviewReport) -> None:
        similarity = float(review.similarity_score or 0)
        policy_risk = float(review.policy_risk_score or 0)
        factual_risk = float(review.factual_risk_score or 0)
        readability = float(review.readability_score or 0)
        title_score = float(review.title_score or 0)
        novelty = float(review.novelty_score or 0)
        risk_score = max(0.0, 100.0 - max(similarity * 100.0, policy_risk * 100.0, factual_risk * 100.0))
        overall = (
            title_score * 0.2
            + readability * 0.25
            + novelty * 0.25
            + (100.0 - similarity * 100.0) * 0.15
            + (100.0 - policy_risk * 100.0) * 0.1
            + (100.0 - factual_risk * 100.0) * 0.05
        )
        generation.score_title = round(title_score, 4)
        generation.score_readability = round(readability, 4)
        generation.score_novelty = round(novelty, 4)
        generation.score_risk = round(risk_score, 4)
        generation.score_overall = round(overall, 4)

    def _passes_thresholds(self, review: ReviewReport) -> bool:
        overall = self._overall_score(review)
        similarity = float(review.similarity_score or 0)
        policy_risk = float(review.policy_risk_score or 0)
        factual_risk = float(review.factual_risk_score or 0)
        return (
            overall >= self.settings.phase4_review_pass_score
            and similarity <= self.settings.phase4_similarity_max
            and policy_risk <= self.settings.phase4_policy_risk_max
            and factual_risk <= self.settings.phase4_factual_risk_max
        )

    def _overall_score(self, review: ReviewReport) -> float:
        similarity = float(review.similarity_score or 0)
        policy_risk = float(review.policy_risk_score or 0)
        factual_risk = float(review.factual_risk_score or 0)
        readability = float(review.readability_score or 0)
        title_score = float(review.title_score or 0)
        novelty = float(review.novelty_score or 0)
        return (
            title_score * 0.2
            + readability * 0.25
            + novelty * 0.25
            + (100.0 - similarity * 100.0) * 0.15
            + (100.0 - policy_risk * 100.0) * 0.1
            + (100.0 - factual_risk * 100.0) * 0.05
        )

    def _render_markdown_to_html(self, markdown: str) -> str:
        parts = ["<section>"]
        in_list = False
        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line:
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                continue
            if line.startswith("# "):
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                parts.append(f"<h1>{escape(line[2:])}</h1>")
                continue
            if line.startswith("## "):
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                parts.append(f"<h2>{escape(line[3:])}</h2>")
                continue
            if line.startswith("### "):
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                parts.append(f"<h3>{escape(line[4:])}</h3>")
                continue
            if line.startswith("> "):
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                parts.append(f"<blockquote>{escape(line[2:])}</blockquote>")
                continue
            if line.startswith("- "):
                if not in_list:
                    parts.append("<ul>")
                    in_list = True
                parts.append(f"<li>{escape(line[2:])}</li>")
                continue
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<p>{escape(line)}</p>")
        if in_list:
            parts.append("</ul>")
        parts.append("</section>")
        return "".join(parts)

    def _related_context(self, related: list[RelatedArticle]) -> str:
        lines: list[str] = []
        for index, item in enumerate(related[:5], start=1):
            lines.append(
                f"{index}. 标题：{item.title or item.url}；"
                f"摘要：{(item.summary or item.cleaned_text or '')[:220]}；"
                f"来源：{item.source_site or item.url}"
            )
        return " | ".join(lines)

    def _related_titles(self, related: list[RelatedArticle]) -> str:
        return " | ".join(item.title or item.url for item in related[:5])

    def _json_items(self, payload: Optional[dict]) -> str:
        return "；".join(str(item) for item in self._items_from_json(payload))

    def _items_from_json(self, payload: Optional[dict]) -> list[str]:
        if not payload:
            return []
        items = payload.get("items")
        if not isinstance(items, list):
            return []
        return [str(item) for item in items if item is not None]

    def _fallback_title(self, source: SourceArticle, brief: ContentBrief) -> str:
        title_candidates = self._items_from_json(brief.title_directions)
        if title_candidates:
            return self._limit(title_candidates[0], 64)
        seed = brief.new_angle or source.title or "重构稿"
        return self._limit(seed, 64)

    def _fallback_digest(self, source: SourceArticle, brief: ContentBrief) -> str:
        parts = [brief.new_angle or "", source.summary or ""]
        text = " ".join(part.strip() for part in parts if part and part.strip())
        return self._limit(text or "基于 content_brief 生成的重构稿。", 120)

    def _similarity_heuristic(self, source_text: str, generated_text: str) -> float:
        left = self._keywords(source_text)
        right = self._keywords(generated_text)
        if not left or not right:
            return 0.2
        overlap = len(left & right)
        baseline = max(min(len(left), len(right)), 1)
        return min(overlap / baseline, 1.0)

    def _keywords(self, text: str) -> set[str]:
        compact = "".join(ch for ch in text if not ch.isspace())
        if not compact:
            return set()
        keywords: set[str] = set()
        for size in (2, 3, 4):
            for index in range(max(len(compact) - size + 1, 0)):
                keywords.add(compact[index : index + size].lower())
        return keywords

    def _contains_policy_keywords(self, text: str) -> bool:
        risky_terms = ("绝对", "保证", "内幕", "医疗建议", "稳赚", "保本", "政治", "时政快讯")
        return any(term in text for term in risky_terms)

    def _normalize_decision(self, value: Optional[str]) -> str:
        decision = (value or "revise").strip().lower()
        if decision in {"pass", "revise", "reject"}:
            return decision
        return "revise"

    def _coerce_float(self, value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _wrap_list(self, payload: Any) -> dict[str, list[Any]]:
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            return payload
        if isinstance(payload, list):
            return {"items": payload}
        if payload in (None, ""):
            return {"items": []}
        return {"items": [payload]}

    def _limit(self, text: str, max_length: int) -> str:
        return text.strip()[:max_length]

    def _require_task(self, task_id: str) -> Task:
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")
        return task

    def _set_task_status(self, task: Task, status: TaskStatus) -> None:
        task.status = status.value
        task.error_code = None
        task.error_message = None
        self.session.flush()

    def _fail_task(self, task: Task, status: TaskStatus, error_code: str, error_message: str) -> None:
        task.status = status.value
        task.error_code = error_code
        task.error_message = error_message[:500]
        self._log_action(task.id, "task.failed", {"status": status.value, "error_code": error_code, "error_message": task.error_message})
        self.session.commit()

    def _log_action(self, task_id: str, action: str, payload: Optional[dict]) -> None:
        self.audit_logs.create(
            AuditLog(
                task_id=task_id,
                action=action,
                operator="system",
                payload=payload,
            )
        )
