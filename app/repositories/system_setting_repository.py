from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.system_setting import SystemSetting


class SystemSettingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self) -> list[SystemSetting]:
        statement = select(SystemSetting).order_by(SystemSetting.key.asc())
        return list(self.session.scalars(statement))

    def get_by_key(self, key: str) -> Optional[SystemSetting]:
        statement = select(SystemSetting).where(SystemSetting.key == key).limit(1)
        return self.session.scalar(statement)

    def upsert(self, *, key: str, value: Any) -> SystemSetting:
        setting = self.get_by_key(key)
        if setting is None:
            setting = SystemSetting(key=key, value=value)
            self.session.add(setting)
        else:
            setting.value = value
        self.session.flush()
        return setting

    def delete(self, setting: SystemSetting) -> None:
        self.session.delete(setting)
        self.session.flush()
