from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.topic_candidate_signal import TopicCandidateSignal


class TopicCandidateSignalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_candidate_id(self, candidate_id: str) -> list[TopicCandidateSignal]:
        statement = (
            select(TopicCandidateSignal)
            .where(TopicCandidateSignal.candidate_id == candidate_id)
            .order_by(TopicCandidateSignal.rank_no.asc(), TopicCandidateSignal.created_at.asc())
        )
        return list(self.session.scalars(statement))

    def create(self, link: TopicCandidateSignal) -> TopicCandidateSignal:
        self.session.add(link)
        self.session.flush()
        return link

    def delete_by_candidate_id(self, candidate_id: str) -> None:
        self.session.execute(delete(TopicCandidateSignal).where(TopicCandidateSignal.candidate_id == candidate_id))
