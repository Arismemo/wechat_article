from __future__ import annotations

from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.style_asset import StyleAsset


class StyleAssetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, asset_id: str) -> Optional[StyleAsset]:
        return self.session.get(StyleAsset, asset_id)

    def list_recent(
        self,
        *,
        limit: int = 20,
        asset_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[StyleAsset]:
        statement = select(StyleAsset)
        if asset_type is not None:
            statement = statement.where(StyleAsset.asset_type == asset_type)
        if status is not None:
            statement = statement.where(StyleAsset.status == status)
        statement = statement.order_by(StyleAsset.updated_at.desc(), StyleAsset.created_at.desc()).limit(limit)
        return list(self.session.scalars(statement))

    def create(self, asset: StyleAsset) -> StyleAsset:
        self.session.add(asset)
        self.session.flush()
        return asset

    def clear_source_task_refs(self, task_id: str) -> None:
        self.session.execute(
            update(StyleAsset)
            .where(StyleAsset.source_task_id == task_id)
            .values(source_task_id=None)
        )

    def clear_source_generation_refs(self, generation_ids: list[str]) -> None:
        if not generation_ids:
            return
        self.session.execute(
            update(StyleAsset)
            .where(StyleAsset.source_generation_id.in_(generation_ids))
            .values(source_generation_id=None)
        )
