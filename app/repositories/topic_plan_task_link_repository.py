from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.topic_plan_task_link import TopicPlanTaskLink


class TopicPlanTaskLinkRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_task_id(self, task_id: str) -> Optional[TopicPlanTaskLink]:
        statement = select(TopicPlanTaskLink).where(TopicPlanTaskLink.task_id == task_id).limit(1)
        return self.session.scalar(statement)

    def list_by_plan_id(self, plan_id: str) -> list[TopicPlanTaskLink]:
        statement = (
            select(TopicPlanTaskLink)
            .where(TopicPlanTaskLink.plan_id == plan_id)
            .order_by(TopicPlanTaskLink.created_at.asc())
        )
        return list(self.session.scalars(statement))

    def create(self, link: TopicPlanTaskLink) -> TopicPlanTaskLink:
        self.session.add(link)
        self.session.flush()
        return link
