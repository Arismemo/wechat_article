from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.core.prompt_versions import CURRENT_PHASE4_PROMPT_VERSION, DEFAULT_GENERATION_PROMPT_TYPE
from app.core.review_metadata import ReviewMetadata, build_review_storage_payloads, extract_review_metadata
from app.models.article_analysis import ArticleAnalysis
from app.models.audit_log import AuditLog
from app.models.content_brief import ContentBrief
from app.models.generation import Generation
from app.models.related_article import RelatedArticle
from app.models.review_report import ReviewReport
from app.models.source_article import SourceArticle
from app.models.style_asset import StyleAsset
from app.models.task import Task
from app.repositories.article_analysis_repository import ArticleAnalysisRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.content_brief_repository import ContentBriefRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.related_article_repository import RelatedArticleRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.style_asset_repository import StyleAssetRepository
from app.repositories.task_repository import TaskRepository
from app.services.llm_service import LLMService, LLMServiceError
from app.services.phase3_pipeline_service import Phase3PipelineService
from app.services.system_setting_service import SystemSettingService
from app.services.wechat_draft_publish_service import WechatDraftPublishService
from app.services.wechat_layout_service import WechatLayoutService
from app.settings import get_settings


@dataclass
class Phase4PipelineResult:
    task_id: str
    status: str
    generation_id: Optional[str]
    review_report_id: Optional[str]
    decision: Optional[str]
    auto_revised: bool


@dataclass(frozen=True)
class MarkdownBlock:
    block_id: str
    markdown: str


@dataclass(frozen=True)
class HumanizePassResult:
    generation: Generation
    rewritten_block_ids: list[str]


class Phase4PipelineService:
    _MAX_STYLE_ASSETS = 6
    _MAX_STYLE_ASSETS_PER_TYPE = 2
    _AI_TRACE_REWRITE_THRESHOLD = 70.0
    _MAX_HUMANIZE_TARGETS = 4
    _REVIEW_BLOCK_CONTEXT_MAX_CHARS = 7000

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.tasks = TaskRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.sources = SourceArticleRepository(session)
        self.analyses = ArticleAnalysisRepository(session)
        self.briefs = ContentBriefRepository(session)
        self.related_articles = RelatedArticleRepository(session)
        self.style_assets = StyleAssetRepository(session)
        self.generations = GenerationRepository(session)
        self.reviews = ReviewReportRepository(session)
        self.llm = LLMService()
        self.system_settings = SystemSettingService(session)
        self.wechat_publisher = WechatDraftPublishService(session)
        self.wechat_layout = WechatLayoutService()

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
        humanize_applied = False
        if decision != "reject" and self._should_run_humanize(review):
            humanize_result = self._try_humanize_generation(
                task=task,
                source=source,
                brief=brief,
                generation=generation,
                review=review,
            )
            if humanize_result is not None:
                generation = humanize_result.generation
                humanize_applied = True
                try:
                    review = self._review_generation(
                        task=task,
                        source=source,
                        brief=brief,
                        related=related,
                        generation=generation,
                        humanize_block_ids=humanize_result.rewritten_block_ids,
                    )
                except Exception as exc:
                    self._fail_task(task, TaskStatus.REVIEW_FAILED, "phase4_humanize_review_failed", str(exc))
                    raise
                decision = self._normalize_decision(review.final_decision)
            elif decision == "pass":
                decision = "revise"

        if decision == "pass" and self._passes_thresholds(review):
            return self._mark_review_passed(task, generation, review, auto_revised=humanize_applied)
        if decision == "reject":
            return self._mark_needs_regenerate(task, generation, review, auto_revised=humanize_applied)
        if humanize_applied:
            return self._mark_needs_manual_review(task, generation, review, auto_revised=True)
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

        if source is not None and analysis is not None and brief is not None:
            return source, analysis, brief, related

        Phase3PipelineService(self.session).run(task.id)

        source = self.sources.get_latest_by_task_id(task.id)
        analysis = self.analyses.get_latest_by_task_id(task.id)
        brief = self.briefs.get_latest_by_task_id(task.id)
        related = self.related_articles.list_selected_by_task_id(task.id)
        if source is None or analysis is None or brief is None:
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
        selected_style_assets = self._select_style_assets(
            source=source,
            analysis=analysis,
            brief=brief,
            related=related,
        )
        self._set_task_status(task, TaskStatus.GENERATING)
        self._log_action(
            task.id,
            "phase4.generation.started",
            {
                "brief_id": brief.id,
                "revision_from_generation_id": prior_generation.id if prior_generation else None,
                "prompt_type": DEFAULT_GENERATION_PROMPT_TYPE,
                "prompt_version": CURRENT_PHASE4_PROMPT_VERSION,
                "style_asset_ids": [item.id for item in selected_style_assets],
            },
        )
        self.session.commit()

        payload, model_name = self._build_generation_payload(
            task_id=task.id,
            source=source,
            analysis=analysis,
            brief=brief,
            related=related,
            style_assets=selected_style_assets,
            prior_generation=prior_generation,
            prior_review=prior_review,
        )
        draft_title = self._limit(str(payload.get("title") or self._fallback_title(source, brief)), 64)
        draft_subtitle = self._limit(str(payload.get("subtitle") or ""), 120) or None
        markdown_content = self.wechat_layout.ensure_title_heading(
            str(payload.get("markdown_content") or "").strip(),
            draft_title,
            draft_subtitle,
        )
        if not markdown_content:
            raise ValueError("Generated draft does not contain markdown_content.")
        rendered_layout = self.wechat_layout.render_markdown(markdown_content)
        if rendered_layout.residual_markdown_markers:
            raise ValueError(
                "Generated draft still contains unsupported markdown markers: "
                + ", ".join(rendered_layout.residual_markdown_markers)
            )
        if rendered_layout.normalization_warnings:
            self._log_action(
                task.id,
                "phase4.layout.normalized",
                {
                    "warnings": rendered_layout.normalization_warnings,
                    "revision_from_generation_id": prior_generation.id if prior_generation else None,
                },
            )

        generation = self.generations.create(
            Generation(
                task_id=task.id,
                brief_id=brief.id,
                version_no=self.generations.get_next_version_no(task.id),
                prompt_type=DEFAULT_GENERATION_PROMPT_TYPE,
                prompt_version=CURRENT_PHASE4_PROMPT_VERSION,
                model_name=model_name,
                title=draft_title,
                subtitle=draft_subtitle,
                digest=self._limit(str(payload.get("digest") or self._fallback_digest(source, brief)), 120),
                markdown_content=rendered_layout.normalized_markdown,
                html_content=rendered_layout.html,
                status="generated",
            )
        )
        self._log_action(
            task.id,
            "phase4.generation.completed",
            {
                "generation_id": generation.id,
                "version_no": generation.version_no,
                "model_name": generation.model_name,
                "prompt_type": generation.prompt_type,
                "prompt_version": generation.prompt_version,
                "style_asset_ids": [item.id for item in selected_style_assets],
            },
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
        humanize_block_ids: Optional[list[str]] = None,
    ) -> ReviewReport:
        self._set_task_status(task, TaskStatus.REVIEWING)
        self._log_action(task.id, "phase4.review.started", {"generation_id": generation.id})
        self.session.commit()

        blocks = self._split_markdown_blocks(generation.markdown_content or "")
        payload = self._build_review_payload(
            task_id=task.id,
            source=source,
            brief=brief,
            related=related,
            generation=generation,
            blocks=blocks,
        )
        heuristic_metadata = self._estimate_ai_trace_metadata(blocks)
        rewrite_targets = self._normalize_rewrite_targets(
            payload.get("rewrite_targets"),
            {block.block_id for block in blocks},
        )
        if not rewrite_targets:
            rewrite_targets = [
                {"block_id": item.block_id, "reason": item.reason, "instruction": item.instruction}
                for item in heuristic_metadata.rewrite_targets
            ]
        issues_payload, suggestions_payload = build_review_storage_payloads(
            issues=payload.get("issues"),
            suggestions=payload.get("suggestions"),
            ai_trace_score=payload.get("ai_trace_score", heuristic_metadata.ai_trace_score),
            ai_trace_patterns=payload.get("ai_trace_patterns") or heuristic_metadata.ai_trace_patterns,
            rewrite_targets=rewrite_targets,
            voice_summary=payload.get("voice_summary") or heuristic_metadata.voice_summary,
            humanize_applied=bool(humanize_block_ids),
            humanize_block_ids=humanize_block_ids,
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
                issues=issues_payload,
                suggestions=suggestions_payload,
                final_decision=self._normalize_decision(str(payload.get("final_decision") or "revise")),
            )
        )
        self._apply_review_scores(generation, report)
        metadata = extract_review_metadata(report.issues, report.suggestions)
        self._log_action(
            task.id,
            "phase4.review.completed",
            {
                "generation_id": generation.id,
                "review_report_id": report.id,
                "decision": report.final_decision,
                "overall_score": generation.score_overall,
                "ai_trace_score": metadata.ai_trace_score,
                "humanize_applied": metadata.humanize_applied,
            },
        )
        self.session.commit()
        return report

    def _try_humanize_generation(
        self,
        *,
        task: Task,
        source: SourceArticle,
        brief: ContentBrief,
        generation: Generation,
        review: ReviewReport,
    ) -> Optional[HumanizePassResult]:
        metadata = extract_review_metadata(review.issues, review.suggestions)
        target_ids = [item.block_id for item in metadata.rewrite_targets][: self._MAX_HUMANIZE_TARGETS]
        if not target_ids:
            return None

        blocks = self._split_markdown_blocks(generation.markdown_content or "")
        if not blocks:
            return None

        self._set_task_status(task, TaskStatus.GENERATING)
        self._log_action(
            task.id,
            "phase4.humanize.started",
            {
                "generation_id": generation.id,
                "review_report_id": review.id,
                "target_block_ids": target_ids,
                "ai_trace_score": metadata.ai_trace_score,
            },
        )
        self.session.commit()

        try:
            payload, model_name = self._build_humanize_payload(
                task_id=task.id,
                source=source,
                brief=brief,
                generation=generation,
                review=review,
                blocks=blocks,
            )
            rewritten_blocks = self._extract_rewritten_blocks(payload, valid_block_ids=set(target_ids))
            if not rewritten_blocks:
                self._log_action(
                    task.id,
                    "phase4.humanize.skipped",
                    {"generation_id": generation.id, "reason": "no_valid_rewrites"},
                )
                self.session.commit()
                return None

            rewritten_markdown = self._apply_rewritten_blocks(blocks, rewritten_blocks)
            rewritten_markdown = self.wechat_layout.ensure_title_heading(
                rewritten_markdown,
                generation.title,
                generation.subtitle,
            )
            rendered_layout = self.wechat_layout.render_markdown(rewritten_markdown)
            if rendered_layout.residual_markdown_markers:
                raise ValueError(
                    "Humanize pass still contains unsupported markdown markers: "
                    + ", ".join(rendered_layout.residual_markdown_markers)
                )
            if rendered_layout.normalization_warnings:
                self._log_action(
                    task.id,
                    "phase4.layout.normalized",
                    {
                        "warnings": rendered_layout.normalization_warnings,
                        "revision_from_generation_id": generation.id,
                        "humanize_pass": True,
                    },
                )

            if (rendered_layout.normalized_markdown or "").strip() == (generation.markdown_content or "").strip():
                self._log_action(
                    task.id,
                    "phase4.humanize.skipped",
                    {"generation_id": generation.id, "reason": "markdown_unchanged"},
                )
                self.session.commit()
                return None

            rewritten_generation = self.generations.create(
                Generation(
                    task_id=task.id,
                    brief_id=generation.brief_id,
                    version_no=self.generations.get_next_version_no(task.id),
                    prompt_type=DEFAULT_GENERATION_PROMPT_TYPE,
                    prompt_version=CURRENT_PHASE4_PROMPT_VERSION,
                    model_name=model_name,
                    title=generation.title,
                    subtitle=generation.subtitle,
                    digest=generation.digest,
                    markdown_content=rendered_layout.normalized_markdown,
                    html_content=rendered_layout.html,
                    status="generated",
                )
            )
            rewritten_block_ids = list(rewritten_blocks.keys())
            self._log_action(
                task.id,
                "phase4.humanize.completed",
                {
                    "generation_id": rewritten_generation.id,
                    "source_generation_id": generation.id,
                    "rewritten_block_ids": rewritten_block_ids,
                    "model_name": model_name,
                },
            )
            self.session.commit()
            return HumanizePassResult(
                generation=rewritten_generation,
                rewritten_block_ids=rewritten_block_ids,
            )
        except Exception as exc:
            self._log_action(
                task.id,
                "phase4.humanize.failed",
                {
                    "generation_id": generation.id,
                    "review_report_id": review.id,
                    "reason": str(exc)[:500],
                },
            )
            self.session.commit()
            return None

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
            return self._mark_needs_regenerate(task, revised_generation, revised_review, auto_revised=True)
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
        if self.system_settings.phase4_auto_push_wechat_draft():
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

    def _mark_needs_regenerate(
        self,
        task: Task,
        generation: Generation,
        review: ReviewReport,
        *,
        auto_revised: bool = False,
    ) -> Phase4PipelineResult:
        generation.status = "rejected"
        self._set_task_status(task, TaskStatus.NEEDS_REGENERATE)
        self._log_action(
            task.id,
            "phase4.review.rejected",
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
        style_assets: list[StyleAsset],
        prior_generation: Optional[Generation],
        prior_review: Optional[ReviewReport],
    ) -> tuple[dict[str, Any], str]:
        system_prompt = (
            "你是微信公众号资深编辑。"
            "请基于输入的原文分析、content_brief 和同题素材，输出严格 JSON。"
            "如果提供了风格资产，只吸收其中已验证的结构、节奏和写法优势，不要逐句照抄。"
            "避免写成套路化的 AI 讲解稿。"
            "不要输出 Markdown 解释，不要输出代码块。"
        )
        user_prompt = (
            "请返回 JSON，字段固定为：title,subtitle,digest,markdown_content。"
            "其中 markdown_content 必须是一篇完整的新稿，必须包含一级标题、至少三个二级标题，"
            "并明确体现新的论证顺序和信息增量。"
            "markdown_content 只允许使用以下 Markdown 子集：# / ## / ### 标题、普通段落、> 引用、"
            "- 或 1. 列表、**加粗**、[链接](https://...)、![配图说明](https://...)、--- 分隔线。"
            "不要输出代码块、表格、任务列表、原始 HTML、过量 emoji。"
            "每段控制在 2 到 4 句，尽量保持移动端阅读的短段落节奏。"
            "避免整篇都用“首先/其次/最后/总之/不难发现/值得注意的是/我们可以看到”这类模板承接词。"
            "不要把段落写成平均用力的提纲扩写，要多写具体判断、反直觉观察、场景感和细节颗粒度。\n\n"
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
            f"已验证风格资产：{self._style_asset_context(style_assets)}\n"
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
        write_model = self.system_settings.phase4_write_model()
        try:
            return (
                self.llm.complete_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=write_model,
                    temperature=0.6,
                    json_mode=True,
                    timeout_seconds=self.settings.llm_write_timeout_seconds,
                ),
                write_model,
            )
        except Exception as exc:
            self._log_action(
                task_id,
                "phase4.generation.fallback",
                {
                    "reason": str(exc)[:500],
                    "fallback_model": "phase4-fallback-template",
                    "prompt_version": CURRENT_PHASE4_PROMPT_VERSION,
                    "style_asset_ids": [item.id for item in style_assets],
                },
            )
            return (
                self._build_generation_fallback(
                    source=source,
                    analysis=analysis,
                    brief=brief,
                    related=related,
                    style_assets=style_assets,
                ),
                "phase4-fallback-template",
            )

    def _build_review_payload(
        self,
        *,
        task_id: str,
        source: SourceArticle,
        brief: ContentBrief,
        related: list[RelatedArticle],
        generation: Generation,
        blocks: list[MarkdownBlock],
    ) -> dict[str, Any]:
        system_prompt = (
            "你是内容审稿编辑。"
            "请对输入稿件做结构化审稿，并输出严格 JSON。"
            "不要输出 Markdown，不要解释。"
        )
        user_prompt = (
            "请返回 JSON，字段固定为："
            "final_decision,similarity_score,factual_risk_score,policy_risk_score,"
            "readability_score,title_score,novelty_score,ai_trace_score,ai_trace_patterns,"
            "rewrite_targets,voice_summary,issues,suggestions。"
            "其中 final_decision 只能是 pass/revise/reject；"
            "similarity_score/factual_risk_score/policy_risk_score 使用 0 到 1 浮点数；"
            "readability_score/title_score/novelty_score/ai_trace_score 使用 0 到 100 数值；"
            "ai_trace_patterns 为字符串数组；"
            "rewrite_targets 为数组，每项必须包含 block_id,reason,instruction，且 block_id 只能引用下方 block_map 中出现过的编号；"
            "voice_summary 用一句话总结这篇稿件当前的表达气质；"
            "issues/suggestions 为字符串数组。\n\n"
            f"原文标题：{source.title or '未知'}\n"
            f"原文摘要：{source.summary or '无'}\n"
            f"新角度：{brief.new_angle or '未提供'}\n"
            f"必须覆盖：{self._json_items(brief.must_cover)}\n"
            f"必须避免：{self._json_items(brief.must_avoid)}\n"
            f"参考素材：{self._related_titles(related)}\n"
            f"生成稿标题：{generation.title or '无'}\n"
            f"生成稿摘要：{generation.digest or '无'}\n"
            f"block_map：\n{self._format_block_context(blocks)}\n"
        )
        review_model = self.system_settings.phase4_review_model()
        try:
            return self.llm.complete_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=review_model,
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
            return self._build_review_fallback(
                source=source,
                brief=brief,
                related=related,
                generation=generation,
                blocks=blocks,
            )

    def _build_humanize_payload(
        self,
        *,
        task_id: str,
        source: SourceArticle,
        brief: ContentBrief,
        generation: Generation,
        review: ReviewReport,
        blocks: list[MarkdownBlock],
    ) -> tuple[dict[str, Any], str]:
        metadata = extract_review_metadata(review.issues, review.suggestions)
        target_ids = [item.block_id for item in metadata.rewrite_targets][: self._MAX_HUMANIZE_TARGETS]
        system_prompt = (
            "你是中文微信公众号资深润色编辑。"
            "你只负责降低 AI 痕迹，不改变事实立场，不扩写不存在的信息。"
            "只改写指定 block_id，输出严格 JSON。"
        )
        user_prompt = (
            "请返回 JSON，字段固定为：rewritten_blocks。"
            "rewritten_blocks 为数组，每项包含 block_id,markdown。"
            "只允许改写以下 block_id："
            f"{' / '.join(target_ids) or '无'}。"
            "不要新增 block，不要删除 block，不要改写未点名的 block。"
            "保留 Markdown 层级和事实含义，只在表达层面去掉套话、总结腔、均匀腔，改成更自然、更具体、更像人写的口吻。"
            "禁止输出代码块、表格、原始 HTML。\n\n"
            f"原文标题：{source.title or '未知'}\n"
            f"稿件标题：{generation.title or '无'}\n"
            f"稿件定位：{brief.positioning or '未提供'}\n"
            f"目标读者：{brief.target_reader or '泛技术读者'}\n"
            f"新角度：{brief.new_angle or '未提供'}\n"
            f"声音诊断：{metadata.voice_summary or '整体表达偏整齐，需要更自然的中文节奏。'}\n"
            f"命中模式：{'；'.join(metadata.ai_trace_patterns) or '未提供'}\n"
            f"改写目标：{self._rewrite_target_context(metadata)}\n"
            f"block_map：\n{self._format_block_context(blocks, focus_block_ids=set(target_ids))}\n"
        )
        write_model = self.system_settings.phase4_write_model()
        try:
            return (
                self.llm.complete_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=write_model,
                    temperature=0.45,
                    json_mode=True,
                    timeout_seconds=self.settings.llm_write_timeout_seconds,
                ),
                write_model,
            )
        except Exception as exc:
            self._log_action(
                task_id,
                "phase4.humanize.fallback",
                {"reason": str(exc)[:500], "generation_id": generation.id},
            )
            raise

    def _build_generation_fallback(
        self,
        *,
        source: SourceArticle,
        analysis: ArticleAnalysis,
        brief: ContentBrief,
        related: list[RelatedArticle],
        style_assets: list[StyleAsset],
    ) -> dict[str, str]:
        must_cover = self._items_from_json(brief.must_cover)[:4]
        must_avoid = self._items_from_json(brief.must_avoid)[:3]
        outline = self._items_from_json(brief.outline)[:3]
        related_points = [item.title or item.url for item in related[:3]]
        opening_assets = self._style_asset_items(style_assets, "opening_hook", limit=1)
        title_assets = self._style_asset_items(style_assets, "title_direction", limit=1)
        structure_assets = self._style_asset_items(style_assets, "outline", limit=2) + self._style_asset_items(
            style_assets,
            "argument_frame",
            limit=1,
        )
        title = self._fallback_title(source, brief)
        if title_assets:
            title = self._limit(title_assets[0], 64)
        subtitle = brief.target_reader or analysis.audience or "给技术读者的一次重构解读"
        digest = self._fallback_digest(source, brief)
        markdown_lines = [
            f"# {title}",
            "",
            f"> {subtitle}",
            "",
            "## 先说结论：这篇内容为什么值得重写",
            f"{opening_assets[0] if opening_assets else (brief.new_angle or '这篇稿件将从新的判断框架切入，而不是重复原文顺序。')}",
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
        markdown_lines.extend(
            f"- {item}"
            for item in (structure_assets or outline or ["开头纠偏", "中段展开判断框架", "结尾给出落地结论"])
        )
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
        blocks: list[MarkdownBlock],
    ) -> dict[str, Any]:
        markdown = generation.markdown_content or ""
        similarity = self._similarity_heuristic(source.cleaned_text or "", markdown)
        readability = 88.0 if len(markdown) >= 600 and "## " in markdown else 66.0
        title_score = 84.0 if 8 <= len(generation.title or "") <= 32 else 68.0
        novelty = 84.0 if (brief.new_angle or "") and (brief.new_angle or "") not in (source.title or "") else 72.0
        policy_risk = 0.15 if not self._contains_policy_keywords(markdown) else 0.55
        factual_risk = 0.2 if len(related) >= 3 else 0.38
        ai_trace_metadata = self._estimate_ai_trace_metadata(blocks)

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
            "ai_trace_score": ai_trace_metadata.ai_trace_score,
            "ai_trace_patterns": ai_trace_metadata.ai_trace_patterns,
            "rewrite_targets": [
                {"block_id": item.block_id, "reason": item.reason, "instruction": item.instruction}
                for item in ai_trace_metadata.rewrite_targets
            ],
            "voice_summary": ai_trace_metadata.voice_summary,
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
        metadata = extract_review_metadata(review.issues, review.suggestions)
        return (
            overall >= self.settings.phase4_review_pass_score
            and similarity <= self.settings.phase4_similarity_max
            and policy_risk <= self.settings.phase4_policy_risk_max
            and factual_risk <= self.settings.phase4_factual_risk_max
            and (metadata.ai_trace_score is None or metadata.ai_trace_score <= self._AI_TRACE_REWRITE_THRESHOLD)
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

    def _should_run_humanize(self, review: ReviewReport) -> bool:
        metadata = extract_review_metadata(review.issues, review.suggestions)
        if metadata.ai_trace_score is None or metadata.ai_trace_score < self._AI_TRACE_REWRITE_THRESHOLD:
            return False
        if not metadata.rewrite_targets:
            return False
        if float(review.policy_risk_score or 0) > self.settings.phase4_policy_risk_max:
            return False
        if float(review.factual_risk_score or 0) > self.settings.phase4_factual_risk_max:
            return False
        return True

    def _split_markdown_blocks(self, markdown: str) -> list[MarkdownBlock]:
        segments = [segment.strip() for segment in re.split(r"\n\s*\n", str(markdown or "").strip()) if segment.strip()]
        return [MarkdownBlock(block_id=f"b{index}", markdown=segment) for index, segment in enumerate(segments, start=1)]

    def _format_block_context(
        self,
        blocks: list[MarkdownBlock],
        *,
        focus_block_ids: Optional[set[str]] = None,
    ) -> str:
        if not blocks:
            return "无"

        visible_ids = set(focus_block_ids or [])
        if visible_ids:
            for index, block in enumerate(blocks):
                if block.block_id not in visible_ids:
                    continue
                if index > 0:
                    visible_ids.add(blocks[index - 1].block_id)
                if index + 1 < len(blocks):
                    visible_ids.add(blocks[index + 1].block_id)
            selected_blocks = [block for block in blocks if block.block_id in visible_ids]
        else:
            selected_blocks = list(blocks)

        rendered_blocks: list[str] = []
        current_length = 0
        for block in selected_blocks:
            chunk = f"[{block.block_id}]\n{block.markdown}"
            if rendered_blocks and current_length + len(chunk) > self._REVIEW_BLOCK_CONTEXT_MAX_CHARS:
                rendered_blocks.append("...[已截断剩余 block]...")
                break
            rendered_blocks.append(chunk)
            current_length += len(chunk) + 2
        return "\n\n".join(rendered_blocks)

    def _estimate_ai_trace_metadata(self, blocks: list[MarkdownBlock]) -> ReviewMetadata:
        formula_terms = (
            "首先",
            "其次",
            "再次",
            "最后",
            "总之",
            "综上",
            "不难发现",
            "值得注意的是",
            "我们可以看到",
            "换句话说",
            "从某种意义上说",
        )
        heading_prefixes = ("先", "再", "最后", "总结", "收尾", "第一", "第二", "第三")

        paragraph_blocks = [block for block in blocks if not block.markdown.lstrip().startswith("#")]
        score = 34.0
        patterns: list[str] = []
        rewrite_targets: list[dict[str, str]] = []

        formula_hits: list[tuple[MarkdownBlock, list[str]]] = []
        for block in paragraph_blocks:
            hits = [term for term in formula_terms if term in block.markdown]
            if hits:
                formula_hits.append((block, hits))
        if formula_hits:
            patterns.append("承接词偏模板化，像按套路串段落")
            score += min(26.0, 10.0 + 6.0 * len(formula_hits))
            for block, hits in formula_hits:
                self._append_rewrite_target(
                    rewrite_targets,
                    block=block,
                    reason=f"出现模板化承接词：{' / '.join(hits[:2])}",
                    instruction="保留原有信息点，去掉首先/其次/总之等串联词，改成更具体的判断或观察。",
                )

        heading_hits = [
            block
            for block in blocks
            if block.markdown.startswith("## ")
            and any(block.markdown[3:].strip().startswith(prefix) for prefix in heading_prefixes)
        ]
        if len(heading_hits) >= 2:
            patterns.append("小标题推进过于工整，像提纲展开")
            score += 12.0
            for block in heading_hits[:2]:
                self._append_rewrite_target(
                    rewrite_targets,
                    block=block,
                    reason="二级标题太像模板推进",
                    instruction="保留章节意思，但把标题改得更具体、更有判断，而不是“先/再/最后”式的提纲口吻。",
                )

        paragraph_lengths = [length for length in (self._visible_markdown_length(block.markdown) for block in paragraph_blocks) if length > 0]
        if len(paragraph_lengths) >= 3 and max(paragraph_lengths) - min(paragraph_lengths) <= 24:
            patterns.append("段落节奏过匀，像机器平均发力")
            score += 8.0
            if paragraph_blocks:
                self._append_rewrite_target(
                    rewrite_targets,
                    block=paragraph_blocks[0],
                    reason="段落长度和句式太平均",
                    instruction="打破均匀讲解腔，补一点具体细节、判断力度或口语化停顿。",
                )

        if not patterns:
            score = 42.0

        voice_summary = (
            "整体信息是清楚的，但表达过于整齐，承接词和段落推进都有明显模板味。"
            if patterns
            else "整体口吻基本自然，但还可以再多一点具体观察和起伏。"
        )
        normalized_targets = extract_review_metadata({}, {"rewrite_targets": rewrite_targets}).rewrite_targets
        return ReviewMetadata(
            ai_trace_score=round(min(score, 96.0), 4),
            ai_trace_patterns=patterns[:4],
            rewrite_targets=normalized_targets[: self._MAX_HUMANIZE_TARGETS],
            voice_summary=voice_summary,
        )

    def _append_rewrite_target(
        self,
        targets: list[dict[str, str]],
        *,
        block: MarkdownBlock,
        reason: str,
        instruction: str,
    ) -> None:
        if len(targets) >= self._MAX_HUMANIZE_TARGETS:
            return
        if any(item.get("block_id") == block.block_id for item in targets):
            return
        targets.append(
            {
                "block_id": block.block_id,
                "reason": self._limit(reason, 120),
                "instruction": self._limit(instruction, 220),
            }
        )

    def _normalize_rewrite_targets(self, payload: Any, valid_block_ids: set[str]) -> list[dict[str, str]]:
        metadata = extract_review_metadata({}, {"rewrite_targets": payload})
        targets: list[dict[str, str]] = []
        for item in metadata.rewrite_targets:
            if item.block_id not in valid_block_ids:
                continue
            targets.append(
                {
                    "block_id": item.block_id,
                    "reason": item.reason,
                    "instruction": item.instruction,
                }
            )
            if len(targets) >= self._MAX_HUMANIZE_TARGETS:
                break
        return targets

    def _rewrite_target_context(self, metadata: ReviewMetadata) -> str:
        if not metadata.rewrite_targets:
            return "无"
        return " | ".join(
            f"{item.block_id}：{item.reason}；改写要求：{item.instruction}"
            for item in metadata.rewrite_targets[: self._MAX_HUMANIZE_TARGETS]
        )

    def _extract_rewritten_blocks(self, payload: dict[str, Any], *, valid_block_ids: set[str]) -> dict[str, str]:
        raw_items = payload.get("rewritten_blocks")
        if not isinstance(raw_items, list):
            return {}

        rewritten: dict[str, str] = {}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            block_id = str(item.get("block_id") or "").strip()
            if block_id not in valid_block_ids or block_id in rewritten:
                continue
            markdown = str(item.get("markdown") or item.get("content") or "").strip()
            if not markdown:
                continue
            rewritten[block_id] = markdown
            if len(rewritten) >= self._MAX_HUMANIZE_TARGETS:
                break
        return rewritten

    def _apply_rewritten_blocks(self, blocks: list[MarkdownBlock], rewritten_blocks: dict[str, str]) -> str:
        parts: list[str] = []
        for block in blocks:
            parts.append(rewritten_blocks.get(block.block_id, block.markdown).strip())
        return "\n\n".join(part for part in parts if part).strip()

    def _visible_markdown_length(self, markdown: str) -> int:
        text = re.sub(r"^#{1,3}\s+", "", markdown, flags=re.MULTILINE)
        text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = text.replace("**", "")
        return len(text.replace("\n", "").strip())

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

    def _select_style_assets(
        self,
        *,
        source: SourceArticle,
        analysis: ArticleAnalysis,
        brief: ContentBrief,
        related: list[RelatedArticle],
    ) -> list[StyleAsset]:
        candidates = self.style_assets.list_recent(limit=40, status="active")
        if not candidates:
            return []

        context = self._style_asset_context_text(source=source, analysis=analysis, brief=brief, related=related)
        scored: list[tuple[float, StyleAsset]] = []
        for asset in candidates:
            score = float(asset.weight or 1.0) * 100.0
            if asset.asset_type in {"title_direction", "opening_hook", "outline", "argument_frame"}:
                score += 10.0
            title = (asset.title or "").strip().lower()
            if title and title in context:
                score += 8.0
            for tag in asset.tags or []:
                normalized_tag = str(tag).strip().lower()
                if normalized_tag and normalized_tag in context:
                    score += 18.0
            scored.append((score, asset))

        selected: list[StyleAsset] = []
        per_type_count: dict[str, int] = {}
        for _, asset in sorted(
            scored,
            key=lambda item: (item[0], float(item[1].weight or 1.0), item[1].updated_at, item[1].created_at),
            reverse=True,
        ):
            current_count = per_type_count.get(asset.asset_type, 0)
            if current_count >= self._MAX_STYLE_ASSETS_PER_TYPE:
                continue
            selected.append(asset)
            per_type_count[asset.asset_type] = current_count + 1
            if len(selected) >= self._MAX_STYLE_ASSETS:
                break
        return selected

    def _style_asset_context_text(
        self,
        *,
        source: SourceArticle,
        analysis: ArticleAnalysis,
        brief: ContentBrief,
        related: list[RelatedArticle],
    ) -> str:
        fields = [
            source.title or "",
            source.summary or "",
            analysis.theme or "",
            analysis.angle or "",
            analysis.audience or "",
            brief.positioning or "",
            brief.new_angle or "",
            brief.target_reader or "",
            " ".join(self._items_from_json(brief.must_cover)),
            " ".join(self._items_from_json(brief.title_directions)),
            " ".join((item.title or "") for item in related[:5]),
        ]
        return " ".join(part.strip().lower() for part in fields if part and part.strip())

    def _style_asset_context(self, style_assets: list[StyleAsset]) -> str:
        if not style_assets:
            return "无"
        lines: list[str] = []
        for asset in style_assets:
            tags = ", ".join(asset.tags or [])
            content = self._limit((asset.content or "").strip().replace("\n", " "), 180)
            lines.append(
                f"[{asset.asset_type}] {asset.title}：{content}"
                + (f"（标签：{tags}）" if tags else "")
            )
        return " | ".join(lines)

    def _style_asset_items(self, style_assets: list[StyleAsset], asset_type: str, *, limit: int) -> list[str]:
        items: list[str] = []
        for asset in style_assets:
            if asset.asset_type != asset_type:
                continue
            content = (asset.content or "").strip()
            if content:
                items.append(self._limit(content.replace("\n", " "), 180))
            if len(items) >= limit:
                break
        return items

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
        self.tasks.update_runtime_state(
            task,
            status=status.value,
            error_code=None,
            error_message=None,
        )

    def _fail_task(self, task: Task, status: TaskStatus, error_code: str, error_message: str) -> None:
        self.tasks.update_runtime_state(
            task,
            status=status.value,
            error_code=error_code,
            error_message=error_message[:500],
        )
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
