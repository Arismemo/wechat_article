from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.prompt_experiment import PromptExperiment


class PromptExperimentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_key(self, prompt_type: str, prompt_version: str, day_offset: int) -> Optional[PromptExperiment]:
        statement = (
            select(PromptExperiment)
            .where(PromptExperiment.prompt_type == prompt_type)
            .where(PromptExperiment.prompt_version == prompt_version)
            .where(PromptExperiment.day_offset == day_offset)
            .limit(1)
        )
        return self.session.scalar(statement)

    def list_recent(
        self,
        *,
        limit: int = 20,
        prompt_type: Optional[str] = None,
        day_offset: Optional[int] = None,
    ) -> list[PromptExperiment]:
        statement = select(PromptExperiment)
        if prompt_type is not None:
            statement = statement.where(PromptExperiment.prompt_type == prompt_type)
        if day_offset is not None:
            statement = statement.where(PromptExperiment.day_offset == day_offset)
        statement = statement.order_by(
            PromptExperiment.sample_count.desc(),
            PromptExperiment.latest_metric_at.desc(),
            PromptExperiment.updated_at.desc(),
        ).limit(limit)
        return list(self.session.scalars(statement))

    def create(self, experiment: PromptExperiment) -> PromptExperiment:
        self.session.add(experiment)
        self.session.flush()
        return experiment
