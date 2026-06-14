from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.publication_metric import PublicationMetric


class PublicationMetricRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, metric_id: str) -> Optional[PublicationMetric]:
        return self.session.get(PublicationMetric, metric_id)

    def get_by_generation_id_and_day_offset(self, generation_id: str, day_offset: int) -> Optional[PublicationMetric]:
        statement = (
            select(PublicationMetric)
            .where(PublicationMetric.generation_id == generation_id)
            .where(PublicationMetric.day_offset == day_offset)
            .limit(1)
        )
        return self.session.scalar(statement)

    def list_by_task_id(self, task_id: str) -> list[PublicationMetric]:
        statement = (
            select(PublicationMetric)
            .where(PublicationMetric.task_id == task_id)
            .order_by(PublicationMetric.day_offset.asc(), PublicationMetric.snapshot_at.desc(), PublicationMetric.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def list_latest_by_task_ids(self, task_ids: list[str]) -> dict[str, PublicationMetric]:
        """Fetch the latest metric snapshot per task_id in ONE query.

        "Latest" means the row with the highest day_offset; ties broken by
        snapshot_at desc then created_at desc.  Returns a dict keyed by
        task_id so callers can map directly onto a list of tasks without an
        N+1 loop.
        """
        if not task_ids:
            return {}

        ranked = (
            select(
                PublicationMetric.id.label("metric_id"),
                PublicationMetric.task_id.label("task_id"),
                func.row_number()
                .over(
                    partition_by=PublicationMetric.task_id,
                    order_by=(
                        PublicationMetric.day_offset.desc(),
                        PublicationMetric.snapshot_at.desc(),
                        PublicationMetric.created_at.desc(),
                    ),
                )
                .label("row_no"),
            )
            .where(PublicationMetric.task_id.in_(task_ids))
            .subquery()
        )
        statement = (
            select(PublicationMetric)
            .join(ranked, PublicationMetric.id == ranked.c.metric_id)
            .where(ranked.c.row_no == 1)
        )
        return {item.task_id: item for item in self.session.scalars(statement)}

    def list_by_prompt_key(self, prompt_type: str, prompt_version: str, day_offset: int) -> list[PublicationMetric]:
        statement = (
            select(PublicationMetric)
            .where(PublicationMetric.prompt_type == prompt_type)
            .where(PublicationMetric.prompt_version == prompt_version)
            .where(PublicationMetric.day_offset == day_offset)
            .order_by(PublicationMetric.snapshot_at.desc(), PublicationMetric.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def create(self, metric: PublicationMetric) -> PublicationMetric:
        self.session.add(metric)
        self.session.flush()
        return metric

    def delete_by_task_id(self, task_id: str) -> None:
        self.session.execute(delete(PublicationMetric).where(PublicationMetric.task_id == task_id))

    def delete_by_generation_ids(self, generation_ids: list[str]) -> None:
        if not generation_ids:
            return
        self.session.execute(delete(PublicationMetric).where(PublicationMetric.generation_id.in_(generation_ids)))
