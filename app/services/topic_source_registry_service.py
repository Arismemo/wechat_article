from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.enums import TopicSourceType
from app.models.topic_source import TopicSource
from app.repositories.system_setting_repository import SystemSettingRepository
from app.repositories.topic_source_repository import TopicSourceRepository


@dataclass(frozen=True)
class TopicSourceDefinition:
    source_key: str
    name: str
    source_type: str
    content_pillar: Optional[str] = None
    enabled: bool = True
    fetch_interval_minutes: int = 240
    config: dict[str, Any] = field(default_factory=dict)


class TopicSourceRegistryService:
    SETTINGS_KEY = "topics.source_registry"
    DEFAULT_DEFINITIONS = (
        TopicSourceDefinition(
            source_key="wechat_ecosystem_watchlist",
            name="微信生态机会监控",
            source_type=TopicSourceType.SEARCH_WATCHLIST.value,
            content_pillar="wechat_ecosystem",
            fetch_interval_minutes=240,
            config={
                "queries": [
                    "微信公众号 生态 变化",
                    "微信搜一搜 内容 机会",
                    "公众号 流量 变化",
                ],
                "recommended_business_goal": "build_trust",
            },
        ),
        TopicSourceDefinition(
            source_key="ai_industry_watchlist",
            name="AI 产业判断监控",
            source_type=TopicSourceType.SEARCH_WATCHLIST.value,
            content_pillar="ai_industry",
            fetch_interval_minutes=180,
            config={
                "queries": [
                    "人工智能 制造业 最新 进展",
                    "智能体 产业 应用",
                    "AI 政策 产业 数字化",
                ],
                "recommended_business_goal": "build_trust",
            },
        ),
        TopicSourceDefinition(
            source_key="solopreneur_methods_watchlist",
            name="单人运营方法监控",
            source_type=TopicSourceType.SEARCH_WATCHLIST.value,
            content_pillar="solopreneur_methods",
            fetch_interval_minutes=360,
            config={
                "queries": [
                    "单人公司 内容 运营",
                    "自动化 运营 工作流",
                    "公众号 增长 方法",
                ],
                "recommended_business_goal": "generate_leads",
            },
        ),
    )
    ALLOWED_SOURCE_TYPES = {item.value for item in TopicSourceType}

    def __init__(self, session: Session) -> None:
        self.session = session
        self.system_settings = SystemSettingRepository(session)
        self.sources = TopicSourceRepository(session)

    def list_definitions(self) -> list[TopicSourceDefinition]:
        merged = {item.source_key: item for item in self.DEFAULT_DEFINITIONS}
        override_setting = self.system_settings.get_by_key(self.SETTINGS_KEY)
        if override_setting is not None:
            for item in self._normalize_override_definitions(override_setting.value):
                merged[item.source_key] = item
        return [merged[key] for key in sorted(merged.keys())]

    def sync_sources(self) -> list[TopicSource]:
        rows: list[TopicSource] = []
        for definition in self.list_definitions():
            rows.append(
                self.sources.upsert(
                    source_key=definition.source_key,
                    name=definition.name,
                    source_type=definition.source_type,
                    content_pillar=definition.content_pillar,
                    enabled=definition.enabled,
                    fetch_interval_minutes=definition.fetch_interval_minutes,
                    config=dict(definition.config),
                )
            )
        self.session.flush()
        return rows

    def list_enabled_sources(self) -> list[TopicSource]:
        return self.sources.list_enabled()

    def _normalize_override_definitions(self, raw_value: object) -> list[TopicSourceDefinition]:
        if raw_value is None:
            return []
        if not isinstance(raw_value, list):
            raise ValueError(f"{self.SETTINGS_KEY} must be a JSON array.")

        defaults = {item.source_key: item for item in self.DEFAULT_DEFINITIONS}
        items: list[TopicSourceDefinition] = []
        for raw_item in raw_value:
            if not isinstance(raw_item, dict):
                raise ValueError(f"{self.SETTINGS_KEY} items must be JSON objects.")
            source_key = self._require_text(raw_item.get("source_key"), field_name="source_key")
            items.append(self._normalize_definition(raw_item, base=defaults.get(source_key)))
        return items

    def _normalize_definition(
        self,
        raw_item: dict[str, Any],
        *,
        base: Optional[TopicSourceDefinition],
    ) -> TopicSourceDefinition:
        source_key = self._require_text(raw_item.get("source_key"), field_name="source_key")
        name = self._coalesce_text(raw_item.get("name"), base.name if base else None, field_name="name")
        source_type = self._coalesce_text(raw_item.get("source_type"), base.source_type if base else None, field_name="source_type")
        if source_type not in self.ALLOWED_SOURCE_TYPES:
            raise ValueError(f"Unsupported topic source type: {source_type}")

        content_pillar = self._optional_text(raw_item.get("content_pillar"))
        if content_pillar is None and base is not None:
            content_pillar = base.content_pillar

        enabled = raw_item.get("enabled", base.enabled if base else True)
        if not isinstance(enabled, bool):
            raise ValueError("topic source enabled must be a boolean.")

        fetch_interval_minutes = raw_item.get("fetch_interval_minutes", base.fetch_interval_minutes if base else 240)
        if isinstance(fetch_interval_minutes, bool):
            raise ValueError("fetch_interval_minutes must be a positive integer.")
        try:
            fetch_interval_minutes = int(fetch_interval_minutes)
        except (TypeError, ValueError) as exc:
            raise ValueError("fetch_interval_minutes must be a positive integer.") from exc
        if fetch_interval_minutes <= 0:
            raise ValueError("fetch_interval_minutes must be a positive integer.")

        base_config = dict(base.config) if base is not None else {}
        raw_config = raw_item.get("config")
        if raw_config is None:
            config = base_config
        elif isinstance(raw_config, dict):
            config = {**base_config, **raw_config}
        else:
            raise ValueError("topic source config must be a JSON object.")

        return TopicSourceDefinition(
            source_key=source_key,
            name=name,
            source_type=source_type,
            content_pillar=content_pillar,
            enabled=enabled,
            fetch_interval_minutes=fetch_interval_minutes,
            config=config,
        )

    @staticmethod
    def _require_text(value: object, *, field_name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"Missing required topic source field: {field_name}")
        return text

    @staticmethod
    def _coalesce_text(value: object, fallback: Optional[str], *, field_name: str) -> str:
        text = str(value or "").strip()
        if text:
            return text
        if fallback:
            return fallback
        raise ValueError(f"Missing required topic source field: {field_name}")

    @staticmethod
    def _optional_text(value: object) -> Optional[str]:
        text = str(value or "").strip()
        return text or None
