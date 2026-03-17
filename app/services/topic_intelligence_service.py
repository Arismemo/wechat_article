from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.core.enums import TopicCandidateStatus, TopicFetchRunStatus, TopicSourceType
from app.models.audit_log import AuditLog
from app.models.topic_candidate import TopicCandidate
from app.models.topic_candidate_signal import TopicCandidateSignal
from app.models.topic_fetch_run import TopicFetchRun
from app.models.topic_plan import TopicPlan
from app.models.topic_plan_task_link import TopicPlanTaskLink
from app.models.topic_signal import TopicSignal
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.topic_candidate_repository import TopicCandidateRepository
from app.repositories.topic_candidate_signal_repository import TopicCandidateSignalRepository
from app.repositories.topic_fetch_run_repository import TopicFetchRunRepository
from app.repositories.topic_plan_repository import TopicPlanRepository
from app.repositories.topic_plan_task_link_repository import TopicPlanTaskLinkRepository
from app.repositories.topic_signal_repository import TopicSignalRepository
from app.repositories.topic_source_repository import TopicSourceRepository
from app.schemas.ingest import IngestLinkRequest
from app.services.phase3_queue_service import Phase3QueueService
from app.services.search_service import SearchResult, SearchService
from app.services.task_service import TaskService
from app.services.topic_source_registry_service import TopicSourceRegistryService
from app.services.url_service import normalize_url
from app.settings import get_settings


@dataclass(frozen=True)
class TopicSourceRunResult:
    source_id: str
    source_key: str
    run_id: str
    status: str
    fetched_count: int
    new_signal_count: int
    candidate_count: int
    latest_plan_ids: list[str]


@dataclass(frozen=True)
class TopicSnapshotFilters:
    limit: int = 20
    status: Optional[str] = None
    content_pillar: Optional[str] = None
    selected_plan_id: Optional[str] = None
    selected_candidate_id: Optional[str] = None


@dataclass(frozen=True)
class TopicPromoteResult:
    plan_id: str
    candidate_id: str
    task_id: str
    task_code: str
    deduped: bool
    status: str
    enqueued: bool
    queue_depth: Optional[int]


@dataclass(frozen=True)
class TopicCandidateStatusUpdateResult:
    candidate_id: str
    previous_status: str
    status: str
    changed: bool


class TopicIntelligenceService:
    _PILLAR_READER_MAP = {
        "wechat_ecosystem": "关注微信生态与内容分发变化的公众号操盘者",
        "ai_industry": "关注 AI 落地、产业判断和政策窗口的行业读者",
        "solopreneur_methods": "想提升单人运营效率和增长质量的内容创业者",
    }
    _PILLAR_GOAL_MAP = {
        "wechat_ecosystem": "build_trust",
        "ai_industry": "build_trust",
        "solopreneur_methods": "generate_leads",
    }
    _PILLAR_ARTICLE_TYPE_MAP = {
        "wechat_ecosystem": "industry_analysis",
        "ai_industry": "decision_guide",
        "solopreneur_methods": "methodology",
    }

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.registry = TopicSourceRegistryService(session)
        self.sources = TopicSourceRepository(session)
        self.fetch_runs = TopicFetchRunRepository(session)
        self.signals = TopicSignalRepository(session)
        self.candidates = TopicCandidateRepository(session)
        self.candidate_signals = TopicCandidateSignalRepository(session)
        self.plans = TopicPlanRepository(session)
        self.plan_task_links = TopicPlanTaskLinkRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.search = SearchService()
        self.task_service = TaskService(session)

    def sync_registry(self) -> list:
        rows = self.registry.sync_sources()
        self.session.commit()
        return rows

    def list_sources(self) -> list:
        self.sync_registry()
        signal_counts = self._signal_counts_by_source_id()
        rows = self.sources.list_all()
        for row in rows:
            setattr(row, "_signal_count", signal_counts.get(row.id, 0))
        return rows

    def run_source(self, source_id: str, *, trigger_type: str = "manual") -> TopicSourceRunResult:
        self.sync_registry()
        source = self.sources.get_by_id(source_id)
        if source is None:
            raise ValueError("Topic source not found.")

        run = self.fetch_runs.create(
            TopicFetchRun(
                source_id=source.id,
                trigger_type=trigger_type,
                status=TopicFetchRunStatus.RUNNING.value,
            )
        )
        self.session.flush()

        fetched_count = 0
        new_signal_count = 0
        latest_plan_ids: list[str] = []
        run_id = run.id
        source_key = source.source_key
        now = datetime.now(timezone.utc)
        self.sources.update_runtime_state(source, last_fetched_at=now, last_error=None)
        self.session.commit()

        try:
            search_results = self._fetch_source_results(source)
            fetched_count = len(search_results)
            new_signal_count = self._store_signals(source.id, run.id, search_results)
            latest_plan_ids = self.refresh_candidates()
            self.fetch_runs.mark_finished(
                run,
                status=TopicFetchRunStatus.SUCCEEDED.value,
                finished_at=datetime.now(timezone.utc),
                fetched_count=fetched_count,
                new_signal_count=new_signal_count,
                error_message=None,
            )
            self.sources.update_runtime_state(
                source,
                last_success_at=datetime.now(timezone.utc),
                last_error=None,
            )
            self.audit_logs.create(
                AuditLog(
                    task_id=None,
                    action="topics.source.run.completed",
                    operator="system",
                    payload={
                        "source_id": source.id,
                        "source_key": source.source_key,
                        "run_id": run.id,
                        "fetched_count": fetched_count,
                        "new_signal_count": new_signal_count,
                        "candidate_count": len(latest_plan_ids),
                    },
                )
            )
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            run = self.fetch_runs.get_by_id(run_id)
            source = self.sources.get_by_id(source_id)
            if run is None or source is None:
                raise
            self.fetch_runs.mark_finished(
                run,
                status=TopicFetchRunStatus.FAILED.value,
                finished_at=datetime.now(timezone.utc),
                fetched_count=fetched_count,
                new_signal_count=new_signal_count,
                error_message=str(exc)[:500],
            )
            self.sources.update_runtime_state(
                source,
                last_error=str(exc)[:500],
            )
            self.audit_logs.create(
                AuditLog(
                    task_id=None,
                    action="topics.source.run.failed",
                    operator="system",
                    payload={
                        "source_id": source.id,
                        "source_key": source_key,
                        "run_id": run.id,
                        "error": str(exc)[:500],
                    },
                )
            )
            self.session.commit()
            raise

        return TopicSourceRunResult(
            source_id=source.id,
            source_key=source.source_key,
            run_id=run.id,
            status=run.status,
            fetched_count=fetched_count,
            new_signal_count=new_signal_count,
            candidate_count=len(latest_plan_ids),
            latest_plan_ids=latest_plan_ids,
        )

    def refresh_candidates(self) -> list[str]:
        recent_signals = self.signals.list_recent(limit=self.settings.topics_candidate_signal_limit)
        groups: dict[str, list[TopicSignal]] = {}
        for signal in recent_signals:
            groups.setdefault(self._cluster_key(signal), []).append(signal)

        latest_plan_ids: list[str] = []
        for cluster_key, items in groups.items():
            items.sort(key=lambda item: item.published_at or item.discovered_at or item.created_at, reverse=True)
            lead = items[0]
            existing = self.candidates.get_by_cluster_key(cluster_key)
            candidate_status = existing.status if existing is not None else TopicCandidateStatus.NEW.value
            candidate = self.candidates.upsert(
                cluster_key=cluster_key,
                topic_title=lead.title,
                topic_summary=self._compose_topic_summary(items),
                content_pillar=self._resolve_content_pillar(items),
                hotness_score=self._hotness_score(items),
                commercial_fit_score=self._commercial_fit_score(items),
                evidence_score=self._evidence_score(items),
                novelty_score=self._novelty_score(items),
                wechat_fit_score=self._wechat_fit_score(items),
                risk_score=self._risk_score(items),
                total_score=self._total_score(items),
                recommended_business_goal=self._recommended_business_goal(items),
                recommended_article_type=self._recommended_article_type(items),
                canonical_seed_url=self._canonical_seed_url(items),
                status=candidate_status,
                signal_count=len(items),
                latest_signal_at=lead.published_at or lead.discovered_at,
            )
            self.candidate_signals.delete_by_candidate_id(candidate.id)
            self.session.flush()
            for rank_no, signal in enumerate(items, start=1):
                self.candidate_signals.create(
                    TopicCandidateSignal(candidate_id=candidate.id, signal_id=signal.id, rank_no=rank_no)
                )
            plan_payload = self._build_plan_payload(candidate, items)
            latest_plan = self.plans.get_latest_by_candidate_id(candidate.id)
            if self._plan_changed(latest_plan, plan_payload):
                latest_plan = self.plans.create(
                    TopicPlan(
                        candidate_id=candidate.id,
                        plan_version=self.plans.get_next_plan_version(candidate.id),
                        **plan_payload,
                    )
                )
            if candidate.status == TopicCandidateStatus.NEW.value:
                candidate.status = TopicCandidateStatus.PLANNED.value
            latest_plan_ids.append(latest_plan.id)
        self.session.flush()
        return latest_plan_ids

    def list_candidates(
        self,
        limit: int = 50,
        *,
        status: Optional[str] = None,
        content_pillar: Optional[str] = None,
    ) -> list:
        self.sync_registry()
        return self.candidates.list_recent(limit=limit, status=status, content_pillar=content_pillar)

    def get_plan_workspace(self, plan_id: str) -> dict[str, Any]:
        plan = self.plans.get_by_id(plan_id)
        if plan is None:
            raise ValueError("Topic plan not found.")
        candidate = self.candidates.get_by_id(plan.candidate_id)
        if candidate is None:
            raise ValueError("Topic candidate not found.")
        signal_links = self.candidate_signals.list_by_candidate_id(candidate.id)
        signals = [self.signals.get_by_id(item.signal_id) for item in signal_links]
        signals = [item for item in signals if item is not None]
        links = self.plan_task_links.list_by_plan_id(plan.id)
        return {
            "candidate": candidate,
            "plan": plan,
            "signals": signals,
            "task_links": links,
        }

    def build_snapshot(self, filters: TopicSnapshotFilters) -> dict[str, Any]:
        self.sync_registry()
        sources = self.sources.list_all()
        candidates = self.candidates.list_recent(limit=filters.limit, status=filters.status, content_pillar=filters.content_pillar)
        status_counts = self._candidate_status_counts()
        selected_plan_workspace = None
        if filters.selected_plan_id:
            selected_plan_workspace = self.get_plan_workspace(filters.selected_plan_id)
        elif filters.selected_candidate_id:
            candidate = self.candidates.get_by_id(filters.selected_candidate_id)
            if candidate is not None:
                latest_plan = self.plans.get_latest_by_candidate_id(candidate.id)
                if latest_plan is not None:
                    selected_plan_workspace = self.get_plan_workspace(latest_plan.id)

        return {
            "summary": {
                "source_total": len(sources),
                "source_enabled": sum(1 for item in sources if item.enabled),
                "candidate_total": sum(status_counts.values()),
                "planned_total": status_counts.get(TopicCandidateStatus.PLANNED.value, 0),
                "promoted_total": status_counts.get(TopicCandidateStatus.PROMOTED.value, 0),
                "ignored_total": status_counts.get(TopicCandidateStatus.IGNORED.value, 0),
                "new_signal_24h": self._count_signals_since(datetime.now(timezone.utc) - timedelta(hours=24)),
                "generated_at": datetime.now(timezone.utc),
                "status_counts": status_counts,
            },
            "sources": sources,
            "candidates": candidates,
            "workspace": selected_plan_workspace,
        }

    def promote_plan(
        self,
        plan_id: str,
        *,
        operator: Optional[str] = None,
        note: Optional[str] = None,
        enqueue_phase3: bool = True,
    ) -> TopicPromoteResult:
        plan = self.plans.get_by_id(plan_id)
        if plan is None:
            raise ValueError("Topic plan not found.")
        candidate = self.candidates.get_by_id(plan.candidate_id)
        if candidate is None:
            raise ValueError("Topic candidate not found.")
        seed_url = (candidate.canonical_seed_url or "").strip()
        if not seed_url:
            raise ValueError("Topic plan has no canonical seed URL.")

        try:
            ingest_request = IngestLinkRequest(
                url=seed_url,
                source="topic-intelligence",
                device_id=f"topic-plan:{plan.id}",
                trigger="topic-promote",
                note=note,
                dispatch_mode="ingest_only",
            )
        except ValidationError as exc:
            raise ValueError("Topic plan has invalid canonical seed URL.") from exc

        task, deduped = self.task_service.ingest_link(ingest_request)
        queue_depth: Optional[int] = None
        enqueued = False
        if enqueue_phase3:
            task = self.task_service.mark_queued_for_phase3(task, reason="topic-plan-promote")
            queue_result = Phase3QueueService().enqueue(task.id)
            enqueued = queue_result.enqueued
            queue_depth = queue_result.queue_depth

        existing_link = self.plan_task_links.get_by_task_id(task.id)
        if existing_link is None or existing_link.plan_id != plan.id:
            self.plan_task_links.create(
                TopicPlanTaskLink(
                    plan_id=plan.id,
                    task_id=task.id,
                    operator=(operator or "system").strip() or "system",
                    note=note,
                )
            )
        candidate.status = TopicCandidateStatus.PROMOTED.value
        self.audit_logs.create(
            AuditLog(
                task_id=task.id,
                action="topics.plan.promoted",
                operator=(operator or "system").strip() or "system",
                payload={
                    "plan_id": plan.id,
                    "candidate_id": candidate.id,
                    "seed_url": seed_url,
                    "deduped": deduped,
                    "enqueue_phase3": enqueue_phase3,
                    "note": note,
                },
            )
        )
        self.session.commit()

        return TopicPromoteResult(
            plan_id=plan.id,
            candidate_id=candidate.id,
            task_id=task.id,
            task_code=task.task_code,
            deduped=deduped,
            status=task.status,
            enqueued=enqueued,
            queue_depth=queue_depth,
        )

    def update_candidate_status(
        self,
        candidate_id: str,
        *,
        status: str,
        operator: Optional[str] = None,
        note: Optional[str] = None,
    ) -> TopicCandidateStatusUpdateResult:
        candidate = self.candidates.get_by_id(candidate_id)
        if candidate is None:
            raise ValueError("Topic candidate not found.")

        allowed_targets = {
            TopicCandidateStatus.PLANNED.value,
            TopicCandidateStatus.WATCHING.value,
            TopicCandidateStatus.IGNORED.value,
        }
        target_status = (status or "").strip().lower()
        if target_status not in allowed_targets:
            raise ValueError("Unsupported topic candidate status target.")

        previous_status = (candidate.status or "").strip().lower()
        if previous_status == TopicCandidateStatus.PROMOTED.value and target_status != previous_status:
            raise ValueError("Promoted topic candidate cannot be manually reverted.")
        if previous_status == target_status:
            return TopicCandidateStatusUpdateResult(
                candidate_id=candidate.id,
                previous_status=previous_status,
                status=target_status,
                changed=False,
            )

        normalized_operator = (operator or "system").strip() or "system"
        normalized_note = (note or "").strip() or None
        candidate.status = target_status
        self.audit_logs.create(
            AuditLog(
                task_id=None,
                action="topics.candidate.status_updated",
                operator=normalized_operator,
                payload={
                    "candidate_id": candidate.id,
                    "from_status": previous_status,
                    "to_status": target_status,
                    "note": normalized_note,
                },
            )
        )
        self.session.commit()
        return TopicCandidateStatusUpdateResult(
            candidate_id=candidate.id,
            previous_status=previous_status,
            status=target_status,
            changed=True,
        )

    def _fetch_source_results(self, source) -> list[SearchResult]:
        source_type = (source.source_type or "").strip()
        config = source.config if isinstance(source.config, dict) else {}
        if source_type != TopicSourceType.SEARCH_WATCHLIST.value:
            raise ValueError(f"Unsupported topic source type: {source_type}")
        queries = config.get("queries")
        if not isinstance(queries, list) or not queries:
            raise ValueError("Topic source queries are not configured.")
        normalized_queries = [str(item).strip() for item in queries if str(item or "").strip()]
        if not normalized_queries:
            raise ValueError("Topic source queries are empty.")
        count_per_query = int(config.get("count_per_query") or self.settings.topics_search_per_query)
        return self.search.search_many(normalized_queries, count_per_query=count_per_query)

    def _store_signals(self, source_id: str, run_id: str, items: list[SearchResult]) -> int:
        created = 0
        for item in items:
            normalized_url = normalize_url(item.url) if item.url else None
            if normalized_url:
                latest = self.signals.get_latest_by_source_and_normalized_url(source_id, normalized_url)
                if latest is not None:
                    continue
            signal = TopicSignal(
                source_id=source_id,
                fetch_run_id=run_id,
                signal_type="search_result",
                title=item.title,
                url=item.url,
                normalized_url=normalized_url,
                summary=item.summary,
                source_site=item.source_site,
                published_at=item.published_at,
                raw_payload={
                    "query_text": item.query_text,
                    "summary": item.summary,
                    "source_site": item.source_site,
                },
                content_hash=self._signal_hash(item),
                source_tier=self._source_tier(item.url, item.source_site),
                fetch_status="discovered",
            )
            self.signals.create(signal)
            created += 1
        self.session.flush()
        return created

    def _cluster_key(self, signal: TopicSignal) -> str:
        if signal.normalized_url:
            return f"url:{signal.normalized_url}"
        title = self._normalize_text(signal.title)
        source_pillar = self._signal_content_pillar(signal) or "general"
        digest = hashlib.sha1(f"{source_pillar}:{title}".encode("utf-8")).hexdigest()[:20]
        return f"title:{source_pillar}:{digest}"

    def _compose_topic_summary(self, items: list[TopicSignal]) -> Optional[str]:
        lead = items[0]
        summary = (lead.summary or "").strip()
        if summary:
            return summary[:200]
        if len(items) > 1:
            return f"该主题当前汇聚 {len(items)} 条公开信号，适合进一步加工为公众号选题。"
        return f"围绕《{lead.title}》延展出的公开信号，适合进一步加工为公众号选题。"

    def _resolve_content_pillar(self, items: list[TopicSignal]) -> Optional[str]:
        for item in items:
            pillar = self._signal_content_pillar(item)
            if pillar:
                return pillar
        return None

    def _signal_content_pillar(self, signal: TopicSignal) -> Optional[str]:
        source = self.sources.get_by_id(signal.source_id)
        return source.content_pillar if source is not None else None

    def _hotness_score(self, items: list[TopicSignal]) -> float:
        lead_time = self._as_utc_datetime(items[0].published_at or items[0].discovered_at) or datetime.now(timezone.utc)
        age_days = max((datetime.now(timezone.utc) - lead_time).days, 0)
        if age_days <= 1:
            base = 92.0
        elif age_days <= 3:
            base = 84.0
        elif age_days <= 7:
            base = 76.0
        elif age_days <= 30:
            base = 64.0
        else:
            base = 52.0
        return round(min(base + max(len(items) - 1, 0) * 3.0, 99.0), 2)

    def _commercial_fit_score(self, items: list[TopicSignal]) -> float:
        pillar = self._resolve_content_pillar(items)
        base = {
            "wechat_ecosystem": 86.0,
            "ai_industry": 84.0,
            "solopreneur_methods": 88.0,
        }.get(pillar or "", 72.0)
        return round(base, 2)

    def _evidence_score(self, items: list[TopicSignal]) -> float:
        lead = items[0]
        tier = lead.source_tier or "C"
        tier_score = {"S": 92.0, "A": 84.0, "B": 72.0, "C": 58.0}.get(tier, 58.0)
        text = " ".join(filter(None, [lead.title, lead.summary or ""]))
        digits = sum(char.isdigit() for char in text)
        evidence_markers = sum(text.count(marker) for marker in ("报告", "数据", "%", "研究", "财报", "政策"))
        bonus = min(digits * 1.2 + evidence_markers * 4.0, 12.0)
        return round(min(tier_score + bonus, 99.0), 2)

    def _novelty_score(self, items: list[TopicSignal]) -> float:
        lead_text = " ".join(filter(None, [items[0].title, items[0].summary or ""]))
        markers = ("机会", "误区", "判断", "风险", "趋势", "窗口")
        score = 68.0 + sum(4.0 for marker in markers if marker in lead_text)
        return round(min(score, 96.0), 2)

    def _wechat_fit_score(self, items: list[TopicSignal]) -> float:
        title_length = len(items[0].title or "")
        score = 82.0
        if 10 <= title_length <= 28:
            score += 8.0
        pillar = self._resolve_content_pillar(items)
        if pillar in {"wechat_ecosystem", "solopreneur_methods"}:
            score += 4.0
        return round(min(score, 96.0), 2)

    def _risk_score(self, items: list[TopicSignal]) -> float:
        text = " ".join(filter(None, [items[0].title, items[0].summary or ""]))
        high_risk_markers = ("医疗", "金融", "证券", "疫情", "事故", "突发", "战争")
        risk = 12.0
        for marker in high_risk_markers:
            if marker in text:
                risk += 18.0
        return round(min(risk, 95.0), 2)

    def _total_score(self, items: list[TopicSignal]) -> float:
        hotness = self._hotness_score(items)
        commercial = self._commercial_fit_score(items)
        evidence = self._evidence_score(items)
        novelty = self._novelty_score(items)
        wechat_fit = self._wechat_fit_score(items)
        risk = self._risk_score(items)
        total = commercial * 0.25 + hotness * 0.20 + evidence * 0.15 + novelty * 0.15 + wechat_fit * 0.15 + 80.0 * 0.10 - risk * 0.10
        return round(max(min(total, 99.0), 0.0), 2)

    def _recommended_business_goal(self, items: list[TopicSignal]) -> str:
        pillar = self._resolve_content_pillar(items)
        return self._PILLAR_GOAL_MAP.get(pillar or "", "build_trust")

    def _recommended_article_type(self, items: list[TopicSignal]) -> str:
        pillar = self._resolve_content_pillar(items)
        return self._PILLAR_ARTICLE_TYPE_MAP.get(pillar or "", "industry_analysis")

    def _canonical_seed_url(self, items: list[TopicSignal]) -> Optional[str]:
        for item in items:
            if item.url:
                return item.url
        return None

    def _build_plan_payload(self, candidate, items: list[TopicSignal]) -> dict[str, Any]:
        pillar = candidate.content_pillar or "general"
        lead = items[0]
        business_goal = candidate.recommended_business_goal or self._PILLAR_GOAL_MAP.get(pillar, "build_trust")
        article_type = candidate.recommended_article_type or self._PILLAR_ARTICLE_TYPE_MAP.get(pillar, "industry_analysis")
        target_reader = self._PILLAR_READER_MAP.get(pillar, "希望获得新判断和可执行建议的公众号读者")
        summary = candidate.topic_summary or f"围绕《{candidate.topic_title}》形成的选题计划。"
        angle = self._plan_angle(candidate.topic_title, pillar)
        keywords = self._keywords(candidate.topic_title, lead.summary or "")
        return {
            "business_goal": business_goal,
            "article_type": article_type,
            "angle": angle,
            "why_now": self._why_now(lead),
            "target_reader": target_reader,
            "must_cover": {
                "items": [
                    "这个主题为什么现在值得写",
                    "公开信息里最容易被忽略的判断点",
                    "给公众号读者可直接带走的结论或动作",
                ]
            },
            "must_avoid": {
                "items": [
                    "复述资讯摘要而没有新判断",
                    "把未经验证的信息写成确定事实",
                    "直接沿用原文叙事顺序",
                ]
            },
            "keywords": {"items": keywords[:8]},
            "search_friendly_title": f"{candidate.topic_title}：这件事对公众号运营意味着什么",
            "distribution_friendly_title": f"{candidate.topic_title}，真正值得关注的不是表面热闹",
            "summary": summary,
            "cta_mode": "soft_follow",
            "source_grade": lead.source_tier,
            "recommended_queries": {"items": self._recommended_queries(candidate.topic_title, keywords)},
            "seed_source_pack": {
                "items": [
                    {
                        "signal_id": item.id,
                        "title": item.title,
                        "url": item.url,
                        "source_site": item.source_site,
                        "source_tier": item.source_tier,
                    }
                    for item in items[:5]
                ]
            },
        }

    def _plan_changed(self, latest_plan: Optional[TopicPlan], payload: dict[str, Any]) -> bool:
        if latest_plan is None:
            return True
        comparable_fields = [
            "business_goal",
            "article_type",
            "angle",
            "why_now",
            "target_reader",
            "must_cover",
            "must_avoid",
            "keywords",
            "search_friendly_title",
            "distribution_friendly_title",
            "summary",
            "cta_mode",
            "source_grade",
            "recommended_queries",
            "seed_source_pack",
        ]
        for field in comparable_fields:
            if getattr(latest_plan, field) != payload.get(field):
                return True
        return False

    def _signal_counts_by_source_id(self) -> dict[str, int]:
        statement = select(TopicSignal.source_id, func.count(TopicSignal.id)).group_by(TopicSignal.source_id)
        return {str(source_id): int(count) for source_id, count in self.session.execute(statement)}

    def _candidate_status_counts(self) -> dict[str, int]:
        rows = self.session.execute(select(TopicCandidate.status, func.count()).group_by(TopicCandidate.status))
        return {str(status): int(count) for status, count in rows}

    def _count_signals_since(self, created_after: datetime) -> int:
        statement = select(func.count(TopicSignal.id)).where(TopicSignal.discovered_at >= created_after)
        return int(self.session.scalar(statement) or 0)

    @staticmethod
    def _source_tier(url: str, source_site: Optional[str]) -> str:
        host = urlparse(url).netloc.lower()
        label = (source_site or "").lower()
        if any(item in host or item in label for item in ("gov", "新华社", "人民网", "www.gov.cn")):
            return "S"
        if any(item in host or item in label for item in ("edu", "questmobile", "腾讯", "36kr", "huxiu", "geekpark")):
            return "A"
        if host.endswith(".org") or host.endswith(".com"):
            return "B"
        return "C"

    @staticmethod
    def _signal_hash(item: SearchResult) -> str:
        payload = f"{item.title}|{item.url}|{item.summary}|{item.query_text}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_text(text: str) -> str:
        compact = re.sub(r"[\W_]+", "", (text or "").lower())
        return compact[:120]

    @staticmethod
    def _plan_angle(topic_title: str, pillar: str) -> str:
        if pillar == "wechat_ecosystem":
            return f"不复述《{topic_title}》本身，而是拆解它对微信内容分发和公众号运营的实际影响。"
        if pillar == "ai_industry":
            return f"围绕《{topic_title}》输出产业判断，而不是停留在技术热闹和表层新闻。"
        if pillar == "solopreneur_methods":
            return f"把《{topic_title}》转成单人运营者可执行的方法，而不是泛泛而谈的鸡汤。"
        return f"围绕《{topic_title}》输出新的判断框架，而不是重复原始信息。"

    @staticmethod
    def _why_now(signal: TopicSignal) -> str:
        published = TopicIntelligenceService._as_utc_datetime(signal.published_at or signal.discovered_at)
        if published is None:
            return "最近公开讨论开始增多，值得尽快形成判断。"
        age_hours = max(int((datetime.now(timezone.utc) - published).total_seconds() // 3600), 0)
        if age_hours <= 24:
            return "这是最近 24 小时内的新信号，适合快速形成公众号判断稿。"
        if age_hours <= 72:
            return "这类信号仍在上升讨论期，现在切入还有时效性优势。"
        return "这个主题虽然不是突发，但仍有继续拆解的传播和搜索价值。"

    @staticmethod
    def _keywords(*texts: str) -> list[str]:
        tokens: list[str] = []
        seen: set[str] = set()
        for text in texts:
            cleaned = re.sub(r"[|｜,，。！？!?:：/\s]+", " ", text or "")
            for token in cleaned.split():
                item = token.strip().lower()
                if len(item) < 2 or item in seen:
                    continue
                seen.add(item)
                tokens.append(item)
        if tokens:
            return tokens
        compact = "".join(re.sub(r"\s+", "", text or "") for text in texts)
        fallback: list[str] = []
        for size in (2, 3, 4):
            for index in range(max(len(compact) - size + 1, 0)):
                token = compact[index : index + size]
                if token and token not in seen:
                    seen.add(token)
                    fallback.append(token)
        return fallback

    @staticmethod
    def _recommended_queries(topic_title: str, keywords: list[str]) -> list[str]:
        seed = keywords[0] if keywords else topic_title
        return [
            f"{topic_title} 分析",
            f"{topic_title} 最新 影响",
            f"{seed} 机会 风险",
        ]

    @staticmethod
    def _as_utc_datetime(value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
