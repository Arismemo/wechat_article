from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.system_setting import SystemSetting
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.system_setting_repository import SystemSettingRepository
from app.settings import Settings, get_settings


@dataclass(frozen=True)
class SystemSettingOption:
    value: str
    label: str


@dataclass(frozen=True)
class SystemSettingDefinition:
    key: str
    label: str
    description: str
    category: str
    value_type: str
    default_resolver: Callable[[Settings], Any]
    normalizer: Callable[[Any], Any]
    options: tuple[SystemSettingOption, ...] = ()
    requires_restart: bool = False


@dataclass
class SystemSettingView:
    key: str
    label: str
    description: str
    category: str
    value_type: str
    default_value: Any
    stored_value: Optional[Any]
    effective_value: Any
    has_override: bool
    options: list[SystemSettingOption]
    requires_restart: bool
    updated_at: Optional[datetime]


class SystemSettingService:
    _CATEGORY_ORDER = {"phase4": 0, "feedback": 1}
    _SETTING_ORDER = {
        "phase4.write_model": 0,
        "phase4.review_model": 1,
        "phase4.auto_push_wechat_draft": 2,
        "phase4.review_pass_score": 3,
        "phase4.similarity_max": 4,
        "phase4.policy_risk_max": 5,
        "phase4.factual_risk_max": 6,
        "phase4.ai_trace_rewrite_threshold": 7,
        "phase4.max_auto_revisions": 8,
        "feedback.sync_provider": 10,
        "feedback.sync_day_offsets": 11,
    }
    _SETTING_DEFINITIONS = (
        SystemSettingDefinition(
            key="phase4.write_model",
            label="Phase 4 写稿模型",
            description="用于正文生成的 LLM 模型名。只覆盖模型名，不覆盖 API Key 和 Provider。",
            category="phase4",
            value_type="string",
            default_resolver=lambda settings: settings.llm_model_write,
            normalizer=lambda value: SystemSettingService._normalize_non_empty_string(
                value,
                field_name="phase4.write_model",
            ),
        ),
        SystemSettingDefinition(
            key="phase4.review_model",
            label="Phase 4 审稿模型",
            description="用于结构化审稿的 LLM 模型名。只覆盖模型名，不覆盖 API Key 和 Provider。",
            category="phase4",
            value_type="string",
            default_resolver=lambda settings: settings.llm_model_review,
            normalizer=lambda value: SystemSettingService._normalize_non_empty_string(
                value,
                field_name="phase4.review_model",
            ),
        ),
        SystemSettingDefinition(
            key="phase4.auto_push_wechat_draft",
            label="审稿通过后自动推草稿",
            description="开启后，Phase 4 在 review_passed 后会自动尝试推送到微信草稿箱。",
            category="phase4",
            value_type="boolean",
            default_resolver=lambda settings: settings.phase4_auto_push_wechat_draft,
            normalizer=lambda value: SystemSettingService._normalize_bool(
                value,
                field_name="phase4.auto_push_wechat_draft",
            ),
        ),
        SystemSettingDefinition(
            key="feedback.sync_provider",
            label="自动反馈 Provider",
            description="控制反馈同步入口使用 disabled、mock 或 http Provider。HTTP 端点和密钥仍由 .env 提供。",
            category="feedback",
            value_type="enum",
            default_resolver=lambda settings: (settings.feedback_sync_provider or "").strip().lower() or "disabled",
            normalizer=lambda value: SystemSettingService._normalize_enum(
                value,
                field_name="feedback.sync_provider",
                allowed_values={"disabled", "mock", "http"},
            ),
            options=(
                SystemSettingOption(value="disabled", label="关闭"),
                SystemSettingOption(value="mock", label="Mock"),
                SystemSettingOption(value="http", label="HTTP Provider"),
            ),
        ),
        SystemSettingDefinition(
            key="feedback.sync_day_offsets",
            label="自动反馈 day offsets",
            description="控制自动反馈默认抓取哪些 T+n 快照，支持非负整数列表。",
            category="feedback",
            value_type="integer_list",
            default_resolver=lambda settings: SystemSettingService._normalize_integer_list(
                settings.feedback_sync_day_offsets,
                field_name="feedback.sync_day_offsets",
            ),
            normalizer=lambda value: SystemSettingService._normalize_integer_list(
                value,
                field_name="feedback.sync_day_offsets",
            ),
        ),
        SystemSettingDefinition(
            key="phase4.review_pass_score",
            label="综合通过分",
            description="AI 审核综合得分达到此阈值才判定为 pass。范围 0-100。",
            category="phase4",
            value_type="float",
            default_resolver=lambda settings: settings.phase4_review_pass_score,
            normalizer=lambda value: SystemSettingService._normalize_float(
                value, field_name="phase4.review_pass_score", min_val=0, max_val=100,
            ),
        ),
        SystemSettingDefinition(
            key="phase4.similarity_max",
            label="相似度上限",
            description="生成稿与原文的相似度不得超过此值。范围 0-1。",
            category="phase4",
            value_type="float",
            default_resolver=lambda settings: settings.phase4_similarity_max,
            normalizer=lambda value: SystemSettingService._normalize_float(
                value, field_name="phase4.similarity_max", min_val=0, max_val=1,
            ),
        ),
        SystemSettingDefinition(
            key="phase4.policy_risk_max",
            label="政策风险上限",
            description="政策风险评分不得超过此值。范围 0-1。",
            category="phase4",
            value_type="float",
            default_resolver=lambda settings: settings.phase4_policy_risk_max,
            normalizer=lambda value: SystemSettingService._normalize_float(
                value, field_name="phase4.policy_risk_max", min_val=0, max_val=1,
            ),
        ),
        SystemSettingDefinition(
            key="phase4.factual_risk_max",
            label="事实风险上限",
            description="事实风险评分不得超过此值。范围 0-1。",
            category="phase4",
            value_type="float",
            default_resolver=lambda settings: settings.phase4_factual_risk_max,
            normalizer=lambda value: SystemSettingService._normalize_float(
                value, field_name="phase4.factual_risk_max", min_val=0, max_val=1,
            ),
        ),
        SystemSettingDefinition(
            key="phase4.ai_trace_rewrite_threshold",
            label="AI 痕迹改写阈值",
            description="AI 痕迹评分超过此值时触发人类化改写。范围 0-100。",
            category="phase4",
            value_type="float",
            default_resolver=lambda _settings: 70.0,
            normalizer=lambda value: SystemSettingService._normalize_float(
                value, field_name="phase4.ai_trace_rewrite_threshold", min_val=0, max_val=100,
            ),
        ),
        SystemSettingDefinition(
            key="phase4.max_auto_revisions",
            label="最大自动修订次数",
            description="审核未通过时允许自动修订的最大次数。",
            category="phase4",
            value_type="integer",
            default_resolver=lambda settings: settings.phase4_max_auto_revisions,
            normalizer=lambda value: SystemSettingService._normalize_positive_integer(
                value, field_name="phase4.max_auto_revisions",
            ),
        ),
    )
    _DEFINITION_MAP = {item.key: item for item in _SETTING_DEFINITIONS}

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.system_settings = SystemSettingRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self._stored_settings_cache: Optional[dict[str, SystemSetting]] = None

    def list_settings(self) -> list[SystemSettingView]:
        return sorted(
            (self._build_view(item) for item in self._SETTING_DEFINITIONS),
            key=lambda item: (self._CATEGORY_ORDER.get(item.category, 99), self._SETTING_ORDER.get(item.key, 999)),
        )

    def get_setting(self, key: str) -> SystemSettingView:
        definition = self._require_definition(key)
        return self._build_view(definition)

    def update_setting(
        self,
        key: str,
        value: Any,
        *,
        operator: Optional[str] = None,
        note: Optional[str] = None,
    ) -> SystemSettingView:
        definition = self._require_definition(key)
        normalized_value = definition.normalizer(value)
        stored_map = self._stored_settings()
        previous_setting = stored_map.get(key)
        previous_stored_value = previous_setting.value if previous_setting is not None else None
        self.system_settings.upsert(key=key, value=normalized_value)
        self._stored_settings_cache = None
        view = self.get_setting(key)
        self.audit_logs.create(
            AuditLog(
                task_id=None,
                action="phase7.system_setting.updated",
                operator=self._normalize_operator(operator),
                payload={
                    "setting_key": key,
                    "previous_stored_value": previous_stored_value,
                    "new_stored_value": view.stored_value,
                    "effective_value": view.effective_value,
                    "note": self._normalize_note(note),
                },
            )
        )
        self.session.commit()
        return view

    def reset_setting(
        self,
        key: str,
        *,
        operator: Optional[str] = None,
        note: Optional[str] = None,
    ) -> SystemSettingView:
        definition = self._require_definition(key)
        stored_map = self._stored_settings()
        previous_setting = stored_map.get(key)
        previous_stored_value = previous_setting.value if previous_setting is not None else None
        if previous_setting is not None:
            self.system_settings.delete(previous_setting)
            self._stored_settings_cache = None
        view = self._build_view(definition)
        self.audit_logs.create(
            AuditLog(
                task_id=None,
                action="phase7.system_setting.reset",
                operator=self._normalize_operator(operator),
                payload={
                    "setting_key": key,
                    "previous_stored_value": previous_stored_value,
                    "effective_value": view.effective_value,
                    "note": self._normalize_note(note),
                },
            )
        )
        self.session.commit()
        return view

    def phase4_write_model(self) -> str:
        return str(self.get_setting("phase4.write_model").effective_value)

    def phase4_review_model(self) -> str:
        return str(self.get_setting("phase4.review_model").effective_value)

    def phase4_auto_push_wechat_draft(self) -> bool:
        return bool(self.get_setting("phase4.auto_push_wechat_draft").effective_value)

    def feedback_sync_provider(self) -> str:
        return str(self.get_setting("feedback.sync_provider").effective_value)

    def feedback_sync_day_offsets(self) -> list[int]:
        value = self.get_setting("feedback.sync_day_offsets").effective_value
        return [int(item) for item in value]

    def phase4_review_pass_score(self) -> float:
        return float(self.get_setting("phase4.review_pass_score").effective_value)

    def phase4_similarity_max(self) -> float:
        return float(self.get_setting("phase4.similarity_max").effective_value)

    def phase4_policy_risk_max(self) -> float:
        return float(self.get_setting("phase4.policy_risk_max").effective_value)

    def phase4_factual_risk_max(self) -> float:
        return float(self.get_setting("phase4.factual_risk_max").effective_value)

    def phase4_ai_trace_rewrite_threshold(self) -> float:
        return float(self.get_setting("phase4.ai_trace_rewrite_threshold").effective_value)

    def phase4_max_auto_revisions(self) -> int:
        return int(self.get_setting("phase4.max_auto_revisions").effective_value)

    def _build_view(self, definition: SystemSettingDefinition) -> SystemSettingView:
        stored_setting = self._stored_settings().get(definition.key)
        default_value = definition.default_resolver(self.settings)
        effective_value = stored_setting.value if stored_setting is not None else default_value
        return SystemSettingView(
            key=definition.key,
            label=definition.label,
            description=definition.description,
            category=definition.category,
            value_type=definition.value_type,
            default_value=default_value,
            stored_value=stored_setting.value if stored_setting is not None else None,
            effective_value=effective_value,
            has_override=stored_setting is not None,
            options=list(definition.options),
            requires_restart=definition.requires_restart,
            updated_at=stored_setting.updated_at if stored_setting is not None else None,
        )

    def _stored_settings(self) -> dict[str, SystemSetting]:
        if self._stored_settings_cache is None:
            self._stored_settings_cache = {item.key: item for item in self.system_settings.list_all()}
        return self._stored_settings_cache

    def _require_definition(self, key: str) -> SystemSettingDefinition:
        definition = self._DEFINITION_MAP.get(key)
        if definition is None:
            raise KeyError(f"Unsupported setting key: {key}")
        return definition

    @staticmethod
    def _normalize_non_empty_string(value: Any, *, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} must be a non-empty string.")
        return normalized

    @staticmethod
    def _normalize_bool(value: Any, *, field_name: str) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            if value in (0, 1):
                return bool(value)
            raise ValueError(f"{field_name} must be true or false.")
        normalized = str(value or "").strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        raise ValueError(f"{field_name} must be true or false.")

    @staticmethod
    def _normalize_enum(value: Any, *, field_name: str, allowed_values: set[str]) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in allowed_values:
            raise ValueError(f"{field_name} must be one of: {', '.join(sorted(allowed_values))}.")
        return normalized

    @staticmethod
    def _normalize_integer_list(value: Any, *, field_name: str) -> list[int]:
        if isinstance(value, str):
            raw_items = [item.strip() for item in value.split(",")]
        elif isinstance(value, (list, tuple)):
            raw_items = list(value)
        else:
            raise ValueError(f"{field_name} must be a comma-separated string or an integer array.")

        normalized: list[int] = []
        for raw_item in raw_items:
            if raw_item in (None, ""):
                continue
            try:
                parsed = int(raw_item)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field_name} must contain integers only.") from exc
            if parsed < 0:
                raise ValueError(f"{field_name} must contain non-negative integers.")
            normalized.append(parsed)
        deduped = sorted(set(normalized))
        if not deduped:
            raise ValueError(f"{field_name} must contain at least one non-negative integer.")
        return deduped

    @staticmethod
    def _normalize_float(value: Any, *, field_name: str, min_val: float = 0, max_val: float = 100) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} 必须是数字。") from exc
        if parsed < min_val or parsed > max_val:
            raise ValueError(f"{field_name} 必须在 {min_val} 到 {max_val} 之间。")
        return round(parsed, 4)

    @staticmethod
    def _normalize_positive_integer(value: Any, *, field_name: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} 必须是整数。") from exc
        if parsed < 0:
            raise ValueError(f"{field_name} 必须 >= 0。")
        return parsed

    @staticmethod
    def _normalize_operator(operator: Optional[str]) -> str:
        return (operator or "").strip() or "admin-console"

    @staticmethod
    def _normalize_note(note: Optional[str]) -> Optional[str]:
        normalized = (note or "").strip()
        return normalized or None
