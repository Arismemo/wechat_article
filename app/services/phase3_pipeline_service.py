from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.models.article_analysis import ArticleAnalysis
from app.models.audit_log import AuditLog
from app.models.content_brief import ContentBrief
from app.models.related_article import RelatedArticle
from app.models.source_article import SourceArticle
from app.models.task import Task
from app.repositories.article_analysis_repository import ArticleAnalysisRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.content_brief_repository import ContentBriefRepository
from app.repositories.related_article_repository import RelatedArticleRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.task_repository import TaskRepository
from app.services.llm_service import LLMService
from app.services.search_service import RankedSearchResult, SearchService
from app.services.source_fetch_service import FetchedArticle, SourceFetchService
from app.services.url_service import detect_source_type
from app.settings import get_settings


@dataclass
class Phase3PipelineResult:
    task_id: str
    status: str
    analysis_id: Optional[str]
    brief_id: Optional[str]
    related_count: int


class Phase3PipelineService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.tasks = TaskRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.source_articles = SourceArticleRepository(session)
        self.related_articles = RelatedArticleRepository(session)
        self.article_analysis = ArticleAnalysisRepository(session)
        self.content_briefs = ContentBriefRepository(session)
        self.fetcher = SourceFetchService()
        self.search = SearchService()
        self.llm = LLMService()

    def run(self, task_id: str) -> Phase3PipelineResult:
        task = self._require_task(task_id)
        source_article = self._ensure_source_article(task)

        try:
            self._set_task_status(task, TaskStatus.ANALYZING_SOURCE)
            self._log_action(task.id, "phase3.analysis.started", {"source_title": source_article.title})
            self.session.commit()

            analysis_payload = self._analyze_source(source_article)
            analysis = self.article_analysis.create(
                ArticleAnalysis(
                    task_id=task.id,
                    theme=analysis_payload["theme"],
                    audience=analysis_payload["audience"],
                    angle=analysis_payload["angle"],
                    tone=analysis_payload["tone"],
                    key_points=self._wrap_list(analysis_payload["key_points"]),
                    facts=self._wrap_list(analysis_payload["facts"]),
                    hooks=self._wrap_list(analysis_payload["hooks"]),
                    risks=self._wrap_list(analysis_payload["risks"]),
                    gaps=self._wrap_list(analysis_payload["gaps"]),
                    structure=self._wrap_list(analysis_payload["structure"]),
                )
            )
            self._log_action(task.id, "phase3.analysis.completed", {"analysis_id": analysis.id, "theme": analysis.theme})
            self.session.commit()
        except Exception as exc:
            self._fail_task(task, TaskStatus.ANALYZE_FAILED, "phase3_analyze_failed", str(exc))
            raise

        try:
            self._set_task_status(task, TaskStatus.SEARCHING_RELATED)
            queries = self._build_queries(source_article, analysis)
            self._log_action(task.id, "phase3.search.started", {"queries": queries})
            self.session.commit()

            raw_results = self.search.search_many(queries, count_per_query=self.settings.phase3_search_per_query)
            ranked_results = self.search.rank_results(
                source_url=source_article.url,
                source_title=source_article.title or "",
                analysis_theme=analysis.theme or "",
                query_texts=queries,
                results=raw_results,
            )
            if not ranked_results:
                raise RuntimeError("No related search results were found.")

            self._set_task_status(task, TaskStatus.FETCHING_RELATED)
            self.related_articles.delete_by_task_id(task.id)
            fetched_related = self._fetch_related_articles(task, ranked_results)
            if not fetched_related:
                raise RuntimeError("All selected related article fetches failed.")
            self._log_action(
                task.id,
                "phase3.search.completed",
                {"selected_count": len(fetched_related), "top_urls": [item.url for item in fetched_related]},
            )
            self.session.commit()
        except Exception as exc:
            self._fail_task(task, TaskStatus.SEARCH_FAILED, "phase3_search_failed", str(exc))
            raise

        try:
            self._set_task_status(task, TaskStatus.BUILDING_BRIEF)
            self._log_action(task.id, "phase3.brief.started", {"related_count": len(fetched_related)})
            self.session.commit()

            brief_payload = self._build_brief(source_article, analysis, fetched_related)
            brief = self.content_briefs.create(
                ContentBrief(
                    task_id=task.id,
                    brief_version=self.content_briefs.get_next_brief_version(task.id),
                    positioning=brief_payload["positioning"],
                    new_angle=brief_payload["new_angle"],
                    target_reader=brief_payload["target_reader"],
                    must_cover=self._wrap_list(brief_payload["must_cover"]),
                    must_avoid=self._wrap_list(brief_payload["must_avoid"]),
                    difference_matrix=self._wrap_list(brief_payload["difference_matrix"]),
                    outline=self._wrap_list(brief_payload["outline"]),
                    title_directions=self._wrap_list(brief_payload["title_directions"]),
                )
            )
            self._set_task_status(task, TaskStatus.BRIEF_READY)
            self._log_action(task.id, "phase3.brief.completed", {"brief_id": brief.id, "new_angle": brief.new_angle})
            self.session.commit()
        except Exception as exc:
            self._fail_task(task, TaskStatus.BRIEF_FAILED, "phase3_brief_failed", str(exc))
            raise

        return Phase3PipelineResult(
            task_id=task.id,
            status=task.status,
            analysis_id=analysis.id,
            brief_id=brief.id,
            related_count=len(fetched_related),
        )

    def _fetch_related_articles(self, task: Task, ranked_results: list[RankedSearchResult]) -> list[RelatedArticle]:
        selected_rows: list[RelatedArticle] = []
        candidate_limit = max(self.settings.phase3_related_top_k * 2, self.settings.phase3_related_top_k)
        for rank_no, candidate in enumerate(ranked_results[:candidate_limit], start=1):
            row = RelatedArticle(
                task_id=task.id,
                query_text=candidate.query_text,
                rank_no=rank_no,
                url=candidate.url,
                title=candidate.title,
                source_site=candidate.source_site,
                summary=candidate.summary,
                published_at=candidate.published_at,
                popularity_score=candidate.overall_score,
                relevance_score=candidate.relevance_score,
                diversity_score=candidate.diversity_score,
                factual_density_score=candidate.factual_density_score,
                selected=False,
            )
            try:
                fetched = self.fetcher.fetch(
                    task.id,
                    candidate.url,
                    detect_source_type(candidate.url),
                    snapshot_relative_path=f"related/{rank_no:02d}.html",
                )
                self._apply_fetched_related(row, fetched)
                row.selected = len(selected_rows) < self.settings.phase3_related_top_k
                row.fetch_status = "success"
            except Exception as exc:  # noqa: BLE001
                row.fetch_status = f"failed: {str(exc)[:240]}"
                row.selected = False
            self.related_articles.create(row)
            if row.selected:
                selected_rows.append(row)
        return selected_rows

    def _ensure_source_article(self, task: Task) -> SourceArticle:
        source_article = self.source_articles.get_latest_by_task_id(task.id)
        if source_article is not None:
            return source_article

        try:
            self._set_task_status(task, TaskStatus.FETCHING_SOURCE)
            self._log_action(task.id, "phase3.fetch.started", {"source_url": task.source_url})
            self.session.commit()

            fetched = self.fetcher.fetch(task.id, task.source_url, task.source_type or "web")
            source_article = self._save_source_article(task, fetched)
            self._set_task_status(task, TaskStatus.SOURCE_READY)
            self._log_action(
                task.id,
                "phase3.fetch.completed",
                {
                    "title": fetched.title,
                    "fetch_method": fetched.fetch_method,
                    "snapshot_path": fetched.snapshot_path,
                },
            )
            self.session.commit()
            return source_article
        except Exception as exc:
            self._fail_task(task, TaskStatus.FETCH_FAILED, "phase3_source_fetch_failed", str(exc))
            raise

    def _save_source_article(self, task: Task, fetched: FetchedArticle) -> SourceArticle:
        source_article = self.source_articles.get_latest_by_task_id(task.id)
        if source_article is None:
            source_article = self.source_articles.create(SourceArticle(task_id=task.id, url=fetched.final_url))

        source_article.url = fetched.final_url
        source_article.title = fetched.title
        source_article.author = fetched.author
        source_article.published_at = fetched.published_at
        source_article.cover_image_url = fetched.cover_image_url
        source_article.raw_html = fetched.raw_html
        source_article.cleaned_text = fetched.cleaned_text
        source_article.summary = fetched.summary
        source_article.snapshot_path = fetched.snapshot_path
        source_article.fetch_status = "success"
        source_article.word_count = fetched.word_count
        source_article.content_hash = fetched.content_hash
        self.session.flush()
        return source_article

    def _apply_fetched_related(self, row: RelatedArticle, fetched: FetchedArticle) -> None:
        row.title = fetched.title or row.title
        row.summary = fetched.summary or row.summary
        row.published_at = fetched.published_at or row.published_at
        row.raw_html = fetched.raw_html
        row.cleaned_text = fetched.cleaned_text
        row.snapshot_path = fetched.snapshot_path

    def _analyze_source(self, source_article: SourceArticle) -> dict[str, object]:
        system_prompt = (
            "你是内容研究编辑。请基于输入原文，输出严格 JSON。"
            "不要输出 Markdown，不要解释，只返回一个 JSON 对象。"
        )
        user_prompt = (
            "请分析这篇原文，并返回 JSON，字段固定为："
            "theme,audience,angle,tone,key_points,facts,hooks,risks,gaps,structure。"
            "其中 key_points/facts/hooks/risks/gaps 为字符串数组，"
            "structure 为对象数组，每项包含 section 与 purpose。\n\n"
            f"标题：{source_article.title or '未知'}\n"
            f"摘要：{source_article.summary or '无'}\n"
            f"正文节选：{(source_article.cleaned_text or '')[:3000]}"
        )
        try:
            payload = self.llm.complete_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self.settings.llm_model_analyze,
                temperature=0.2,
            )
            return self._normalize_analysis_payload(payload, source_article)
        except Exception:
            return self._fallback_analysis(source_article)

    def _build_brief(
        self,
        source_article: SourceArticle,
        analysis: ArticleAnalysis,
        related_articles: list[RelatedArticle],
    ) -> dict[str, object]:
        related_excerpt_lines = []
        for article in related_articles:
            related_excerpt_lines.append(
                f"- 标题：{article.title or '未知'}\n"
                f"  来源：{article.source_site or article.url}\n"
                f"  摘要：{(article.summary or article.cleaned_text or '')[:360]}"
            )

        system_prompt = (
            "你是资深公众号选题编辑。请基于原文分析和同题素材，输出严格 JSON。"
            "不要输出 Markdown，不要解释，只返回一个 JSON 对象。"
        )
        user_prompt = (
            "请生成一份内容重构 brief，字段固定为："
            "positioning,new_angle,target_reader,must_cover,must_avoid,difference_matrix,outline,title_directions。"
            "must_cover/must_avoid/title_directions 为字符串数组，"
            "difference_matrix 为对象数组，每项包含 topic,source_coverage,opportunity，"
            "outline 为对象数组，每项包含 heading 与 goal。\n\n"
            f"原文标题：{source_article.title or '未知'}\n"
            f"原文摘要：{source_article.summary or '无'}\n"
            f"分析主题：{analysis.theme or '未知'}\n"
            f"分析受众：{analysis.audience or '未知'}\n"
            f"分析角度：{analysis.angle or '未知'}\n"
            f"分析空白：{self._json_items(analysis.gaps)}\n"
            "同题素材：\n"
            + "\n".join(related_excerpt_lines)
        )
        try:
            payload = self.llm.complete_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self.settings.llm_model_write,
                temperature=0.4,
            )
            return self._normalize_brief_payload(payload, source_article, analysis, related_articles)
        except Exception:
            return self._fallback_brief(source_article, analysis, related_articles)

    def _fallback_analysis(self, source_article: SourceArticle) -> dict[str, object]:
        title = source_article.title or "未命名主题"
        summary = source_article.summary or ""
        cleaned = source_article.cleaned_text or ""
        key_points = [line.strip() for line in cleaned.splitlines() if line.strip()][:5] or [summary or title]
        return {
            "theme": title,
            "audience": "关注该主题、希望快速理解来龙去脉的公众号读者",
            "angle": summary[:120] or title,
            "tone": "理性拆解",
            "key_points": key_points,
            "facts": key_points[:3],
            "hooks": [title, summary[:60] or "为什么这件事值得重新讲一遍"],
            "risks": ["避免沿用原文论证顺序", "避免复述已被广泛覆盖的常识"],
            "gaps": ["补足背景与边界条件", "给出更适合公众号读者的行动建议"],
            "structure": [
                {"section": "先讲结论", "purpose": "快速给出读者收益"},
                {"section": "拆解事实", "purpose": "说明争议点和关键依据"},
                {"section": "给出建议", "purpose": "形成新信息增量"},
            ],
        }

    def _fallback_brief(
        self,
        source_article: SourceArticle,
        analysis: ArticleAnalysis,
        related_articles: list[RelatedArticle],
    ) -> dict[str, object]:
        related_titles = [article.title or article.url for article in related_articles[:3]]
        return {
            "positioning": "面向普通公众号读者的二次拆解稿，不重复原文顺序，而是强调信息增量和读者收益。",
            "new_angle": f"从“{analysis.theme or source_article.title or '原主题'}真正值得关注的判断框架”切入，而不是复述事件表层经过。",
            "target_reader": analysis.audience or "希望快速理解主题、并获得实际判断方法的读者",
            "must_cover": [
                "解释原话题为什么成立",
                "补足原文没有展开的背景或边界",
                "给出一组读者可直接带走的判断方法",
            ],
            "must_avoid": [
                "直接沿用原文段落顺序",
                "复刻原文金句和结论包装",
                "把未经验证的信息写成确定事实",
            ],
            "difference_matrix": [
                {
                    "topic": article.title or "同题文章",
                    "source_coverage": (article.summary or "覆盖了该主题的公开讨论")[:80],
                    "opportunity": "补充读者视角、场景化解释或误区纠偏",
                }
                for article in related_articles[:3]
            ],
            "outline": [
                {"heading": "开头先给结论", "goal": "用反常识或误区建立阅读动机"},
                {"heading": "第二部分讲事实与背景", "goal": "把事情说明白，不复述原文结构"},
                {"heading": "第三部分讲判断框架", "goal": "提供新的分析视角和实用收益"},
                {"heading": "结尾收束", "goal": "明确读者应该记住什么、避免什么"},
            ],
            "title_directions": [
                f"{source_article.title or '这个话题'}，真正值得讲的不是表面现象",
                f"同样在聊{analysis.theme or source_article.title or '这个主题'}，这几个关键点还没人讲透",
                f"看懂{analysis.theme or source_article.title or '这个话题'}，先别急着站队",
            ],
            "related_titles": related_titles,
        }

    def _build_queries(self, source_article: SourceArticle, analysis: ArticleAnalysis) -> list[str]:
        topic = (analysis.theme or source_article.title or "").strip() or "主题"
        concise_topic = topic.replace("【", " ").replace("】", " ").replace("|", " ").strip()
        return [
            f"{concise_topic} 分析",
            f"{concise_topic} 最新 争议 评价",
            f"{concise_topic} 误区 风险 高估 低估",
        ]

    def _normalize_analysis_payload(self, payload: dict, source_article: SourceArticle) -> dict[str, object]:
        fallback = self._fallback_analysis(source_article)
        normalized = {
            "theme": self._as_text(payload.get("theme")) or fallback["theme"],
            "audience": self._as_text(payload.get("audience")) or fallback["audience"],
            "angle": self._as_text(payload.get("angle")) or fallback["angle"],
            "tone": self._as_text(payload.get("tone")) or fallback["tone"],
            "key_points": self._as_list(payload.get("key_points")) or fallback["key_points"],
            "facts": self._as_list(payload.get("facts")) or fallback["facts"],
            "hooks": self._as_list(payload.get("hooks")) or fallback["hooks"],
            "risks": self._as_list(payload.get("risks")) or fallback["risks"],
            "gaps": self._as_list(payload.get("gaps")) or fallback["gaps"],
            "structure": self._as_object_list(payload.get("structure")) or fallback["structure"],
        }
        return normalized

    def _normalize_brief_payload(
        self,
        payload: dict,
        source_article: SourceArticle,
        analysis: ArticleAnalysis,
        related_articles: list[RelatedArticle],
    ) -> dict[str, object]:
        fallback = self._fallback_brief(source_article, analysis, related_articles)
        return {
            "positioning": self._as_text(payload.get("positioning")) or fallback["positioning"],
            "new_angle": self._as_text(payload.get("new_angle")) or fallback["new_angle"],
            "target_reader": self._as_text(payload.get("target_reader")) or fallback["target_reader"],
            "must_cover": self._as_list(payload.get("must_cover")) or fallback["must_cover"],
            "must_avoid": self._as_list(payload.get("must_avoid")) or fallback["must_avoid"],
            "difference_matrix": self._as_object_list(payload.get("difference_matrix")) or fallback["difference_matrix"],
            "outline": self._as_object_list(payload.get("outline")) or fallback["outline"],
            "title_directions": self._as_list(payload.get("title_directions")) or fallback["title_directions"],
        }

    def _wrap_list(self, values: object) -> dict[str, object]:
        if isinstance(values, dict) and "items" in values:
            return values
        if isinstance(values, list):
            return {"items": values}
        if values is None:
            return {"items": []}
        return {"items": [values]}

    def _json_items(self, payload: Optional[dict]) -> list[object]:
        if not isinstance(payload, dict):
            return []
        items = payload.get("items")
        return items if isinstance(items, list) else []

    def _as_text(self, value: object) -> str:
        if isinstance(value, str):
            return value.strip()
        return ""

    def _as_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        items = [str(item).strip() for item in value if str(item).strip()]
        return items

    def _as_object_list(self, value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        objects = [item for item in value if isinstance(item, dict)]
        return objects

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
        task.error_message = error_message[:1000]
        self._log_action(task.id, f"phase3.failed.{status.value}", {"error_code": error_code, "error_message": error_message})
        self.session.commit()

    def _log_action(self, task_id: str, action: str, payload: Optional[dict]) -> None:
        self.audit_logs.create(AuditLog(task_id=task_id, action=action, operator="system", payload=payload))
