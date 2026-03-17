from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.topic_candidate import TopicCandidate


class TopicCandidateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, candidate_id: str) -> Optional[TopicCandidate]:
        return self.session.get(TopicCandidate, candidate_id)

    def get_by_cluster_key(self, cluster_key: str) -> Optional[TopicCandidate]:
        statement = select(TopicCandidate).where(TopicCandidate.cluster_key == cluster_key).limit(1)
        return self.session.scalar(statement)

    def list_recent(
        self,
        limit: int = 50,
        *,
        status: Optional[str] = None,
        content_pillar: Optional[str] = None,
    ) -> list[TopicCandidate]:
        statement = select(TopicCandidate)
        if status:
            statement = statement.where(TopicCandidate.status == status)
        if content_pillar:
            statement = statement.where(TopicCandidate.content_pillar == content_pillar)
        statement = statement.order_by(TopicCandidate.total_score.desc(), TopicCandidate.updated_at.desc()).limit(limit)
        return list(self.session.scalars(statement))

    def create(self, candidate: TopicCandidate) -> TopicCandidate:
        self.session.add(candidate)
        self.session.flush()
        return candidate

    def upsert(
        self,
        *,
        cluster_key: str,
        topic_title: str,
        topic_summary: Optional[str],
        content_pillar: Optional[str],
        hotness_score: Optional[float],
        commercial_fit_score: Optional[float],
        evidence_score: Optional[float],
        novelty_score: Optional[float],
        wechat_fit_score: Optional[float],
        risk_score: Optional[float],
        total_score: Optional[float],
        recommended_business_goal: Optional[str],
        recommended_article_type: Optional[str],
        canonical_seed_url: Optional[str],
        status: str,
        signal_count: int,
        latest_signal_at: Optional[datetime],
    ) -> TopicCandidate:
        candidate = self.get_by_cluster_key(cluster_key)
        if candidate is None:
            candidate = TopicCandidate(cluster_key=cluster_key, topic_title=topic_title, status=status)
            self.session.add(candidate)

        candidate.topic_title = topic_title
        candidate.topic_summary = topic_summary
        candidate.content_pillar = content_pillar
        candidate.hotness_score = hotness_score
        candidate.commercial_fit_score = commercial_fit_score
        candidate.evidence_score = evidence_score
        candidate.novelty_score = novelty_score
        candidate.wechat_fit_score = wechat_fit_score
        candidate.risk_score = risk_score
        candidate.total_score = total_score
        candidate.recommended_business_goal = recommended_business_goal
        candidate.recommended_article_type = recommended_article_type
        candidate.canonical_seed_url = canonical_seed_url
        candidate.status = status
        candidate.signal_count = signal_count
        candidate.latest_signal_at = latest_signal_at
        self.session.flush()
        return candidate
