from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.topic_plan import TopicPlan


class TopicPlanRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, plan_id: str) -> Optional[TopicPlan]:
        return self.session.get(TopicPlan, plan_id)

    def get_latest_by_candidate_id(self, candidate_id: str) -> Optional[TopicPlan]:
        statement = (
            select(TopicPlan)
            .where(TopicPlan.candidate_id == candidate_id)
            .order_by(TopicPlan.plan_version.desc(), TopicPlan.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def list_by_candidate_id(self, candidate_id: str) -> list[TopicPlan]:
        statement = (
            select(TopicPlan)
            .where(TopicPlan.candidate_id == candidate_id)
            .order_by(TopicPlan.plan_version.asc(), TopicPlan.created_at.asc())
        )
        return list(self.session.scalars(statement))

    def get_next_plan_version(self, candidate_id: str) -> int:
        statement = select(func.coalesce(func.max(TopicPlan.plan_version), 0)).where(TopicPlan.candidate_id == candidate_id)
        return int(self.session.scalar(statement) or 0) + 1

    def create(self, plan: TopicPlan) -> TopicPlan:
        self.session.add(plan)
        self.session.flush()
        return plan
