from __future__ import annotations

from typing import Optional

from sqlalchemy import select
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

    def get_latest_by_generation_id(self, generation_id: str) -> Optional[WechatDraft]:
        statement = (
            select(WechatDraft)
            .where(WechatDraft.generation_id == generation_id)
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
