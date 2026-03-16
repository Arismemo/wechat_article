from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.wechat_draft import WechatDraft


class WechatDraftRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_latest_by_task_id(self, task_id: str) -> Optional[WechatDraft]:
        statement = (
            select(WechatDraft)
            .where(WechatDraft.task_id == task_id)
            .order_by(WechatDraft.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_latest_by_task_ids(self, task_ids: list[str]) -> dict[str, WechatDraft]:
        if not task_ids:
            return {}

        ranked_drafts = (
            select(
                WechatDraft.id.label("draft_id"),
                WechatDraft.task_id.label("task_id"),
                func.row_number()
                .over(
                    partition_by=WechatDraft.task_id,
                    order_by=(WechatDraft.created_at.desc(), WechatDraft.id.desc()),
                )
                .label("row_no"),
            )
            .where(WechatDraft.task_id.in_(task_ids))
            .subquery()
        )
        statement = (
            select(WechatDraft)
            .join(ranked_drafts, WechatDraft.id == ranked_drafts.c.draft_id)
            .where(ranked_drafts.c.row_no == 1)
        )
        return {item.task_id: item for item in self.session.scalars(statement)}

    def get_latest_by_generation_id(self, generation_id: str) -> Optional[WechatDraft]:
        statement = (
            select(WechatDraft)
            .where(WechatDraft.generation_id == generation_id)
            .order_by(WechatDraft.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_latest_successful_by_task_id(self, task_id: str) -> Optional[WechatDraft]:
        statement = (
            select(WechatDraft)
            .where(WechatDraft.task_id == task_id)
            .where(WechatDraft.push_status == "success")
            .where(WechatDraft.media_id.is_not(None))
            .order_by(WechatDraft.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def list_recent_successful(self, limit: int = 20) -> list[WechatDraft]:
        statement = (
            select(WechatDraft)
            .where(WechatDraft.push_status == "success")
            .where(WechatDraft.media_id.is_not(None))
            .order_by(WechatDraft.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def create(self, draft: WechatDraft) -> WechatDraft:
        self.session.add(draft)
        self.session.flush()
        return draft

    def delete_by_task_id(self, task_id: str) -> None:
        self.session.execute(delete(WechatDraft).where(WechatDraft.task_id == task_id))
