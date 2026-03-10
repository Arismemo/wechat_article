from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.system_setting import SystemSetting
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.system_setting_repository import SystemSettingRepository
from app.services.llm_service import LLMService
from app.settings import get_settings


@dataclass(frozen=True)
class LLMProviderConfig:
    provider_id: str
    vendor: str
    label: str
    api_base: str
    api_key: str
    models: list[str]
    is_env_default: bool = False


@dataclass(frozen=True)
class LLMProviderView:
    provider_id: str
    vendor: str
    label: str
    api_base: str
    models: list[str]
    has_api_key: bool
    api_key_preview: Optional[str]
    is_env_default: bool


@dataclass(frozen=True)
class LLMSelectionView:
    active_provider_id: str
    analyze_model: str
    write_model: str
    review_model: str


@dataclass(frozen=True)
class LLMRuntimeConfigView:
    providers: list[LLMProviderView]
    selection: LLMSelectionView


@dataclass(frozen=True)
class EffectiveLLMRuntimeConfig:
    active_provider_id: str
    active_provider_label: str
    vendor: str
    api_base: str
    api_key: str
    analyze_model: str
    write_model: str
    review_model: str
    providers: tuple[LLMProviderConfig, ...]


@dataclass(frozen=True)
class LLMConnectivityTestResult:
    success: bool
    provider_id: str
    provider_label: str
    model: str
    base_url_preview: Optional[str]
    response_payload: Optional[dict[str, Any]]
    error: Optional[str]
    tested_at: datetime
    latency_ms: int


class LLMRuntimeService:
    PROVIDERS_KEY = "llm.providers"
    ACTIVE_PROVIDER_KEY = "llm.active_provider"
    ANALYZE_MODEL_KEY = "llm.analyze_model"
    ENV_PROVIDER_ID = "env-default"

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.system_settings = SystemSettingRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self._stored_settings_cache: Optional[dict[str, SystemSetting]] = None

    def get_config_view(self) -> LLMRuntimeConfigView:
        effective = self.resolve_effective_config()
        providers = [
            LLMProviderView(
                provider_id=item.provider_id,
                vendor=item.vendor,
                label=item.label,
                api_base=item.api_base,
                models=list(item.models),
                has_api_key=bool(item.api_key),
                api_key_preview=self._preview_secret(item.api_key),
                is_env_default=item.is_env_default,
            )
            for item in effective.providers
        ]
        return LLMRuntimeConfigView(
            providers=providers,
            selection=LLMSelectionView(
                active_provider_id=effective.active_provider_id,
                analyze_model=effective.analyze_model,
                write_model=effective.write_model,
                review_model=effective.review_model,
            ),
        )

    def resolve_effective_config(self) -> EffectiveLLMRuntimeConfig:
        providers = self._load_provider_configs()
        if not providers:
            providers = [self._build_env_provider()]

        active_provider_id = self._stored_string(self.ACTIVE_PROVIDER_KEY) or providers[0].provider_id
        provider_map = {item.provider_id: item for item in providers}
        active_provider = provider_map.get(active_provider_id) or providers[0]

        analyze_model = self._resolve_model(
            stored_key=self.ANALYZE_MODEL_KEY,
            default_value=self.settings.llm_model_analyze,
            provider=active_provider,
        )
        write_model = self._resolve_model(
            stored_key="phase4.write_model",
            default_value=self.settings.llm_model_write,
            provider=active_provider,
        )
        review_model = self._resolve_model(
            stored_key="phase4.review_model",
            default_value=self.settings.llm_model_review,
            provider=active_provider,
        )

        return EffectiveLLMRuntimeConfig(
            active_provider_id=active_provider.provider_id,
            active_provider_label=active_provider.label,
            vendor=active_provider.vendor,
            api_base=active_provider.api_base,
            api_key=active_provider.api_key,
            analyze_model=analyze_model,
            write_model=write_model,
            review_model=review_model,
            providers=tuple(providers),
        )

    def build_llm_service(self) -> LLMService:
        effective = self.resolve_effective_config()
        return LLMService(
            api_base=effective.api_base,
            api_key=effective.api_key,
            default_model=effective.analyze_model,
        )

    def analyze_model(self) -> str:
        return self.resolve_effective_config().analyze_model

    def write_model(self) -> str:
        return self.resolve_effective_config().write_model

    def review_model(self) -> str:
        return self.resolve_effective_config().review_model

    def update_config(
        self,
        *,
        providers: list[dict[str, Any]],
        active_provider_id: str,
        analyze_model: str,
        write_model: str,
        review_model: str,
        operator: Optional[str] = None,
        note: Optional[str] = None,
    ) -> LLMRuntimeConfigView:
        previous = self.resolve_effective_config()
        normalized_providers = self._normalize_provider_updates(providers)
        provider_map = {item.provider_id: item for item in normalized_providers}
        if active_provider_id not in provider_map:
            raise ValueError("active_provider_id must reference an existing provider.")
        active_provider = provider_map[active_provider_id]
        normalized_analyze_model = self._normalize_selected_model(analyze_model, active_provider, field_name=self.ANALYZE_MODEL_KEY)
        normalized_write_model = self._normalize_selected_model(write_model, active_provider, field_name="phase4.write_model")
        normalized_review_model = self._normalize_selected_model(
            review_model,
            active_provider,
            field_name="phase4.review_model",
        )

        self.system_settings.upsert(
            key=self.PROVIDERS_KEY,
            value=[self._serialize_provider(item) for item in normalized_providers],
        )
        self.system_settings.upsert(key=self.ACTIVE_PROVIDER_KEY, value=active_provider.provider_id)
        self.system_settings.upsert(key=self.ANALYZE_MODEL_KEY, value=normalized_analyze_model)
        self.system_settings.upsert(key="phase4.write_model", value=normalized_write_model)
        self.system_settings.upsert(key="phase4.review_model", value=normalized_review_model)
        self._stored_settings_cache = None

        current = self.resolve_effective_config()
        self.audit_logs.create(
            AuditLog(
                task_id=None,
                action="phase7.llm_runtime.updated",
                operator=self._normalize_operator(operator),
                payload={
                    "previous_active_provider_id": previous.active_provider_id,
                    "new_active_provider_id": current.active_provider_id,
                    "previous_models": {
                        "analyze": previous.analyze_model,
                        "write": previous.write_model,
                        "review": previous.review_model,
                    },
                    "new_models": {
                        "analyze": current.analyze_model,
                        "write": current.write_model,
                        "review": current.review_model,
                    },
                    "provider_count": len(current.providers),
                    "note": self._normalize_note(note),
                },
            )
        )
        self.session.commit()
        return self.get_config_view()

    def test_provider(
        self,
        *,
        provider_id: str,
        model: Optional[str] = None,
        operator: Optional[str] = None,
        note: Optional[str] = None,
    ) -> LLMConnectivityTestResult:
        effective = self.resolve_effective_config()
        provider_map = {item.provider_id: item for item in effective.providers}
        provider = provider_map.get((provider_id or "").strip())
        if provider is None:
            raise ValueError("provider_id does not exist.")
        selected_model = self._normalize_selected_model(
            model or effective.analyze_model,
            provider,
            field_name="test.model",
        )
        llm = LLMService(api_base=provider.api_base, api_key=provider.api_key, default_model=selected_model)
        started = time.perf_counter()
        tested_at = datetime.now(timezone.utc)
        try:
            response_payload = llm.complete_json(
                system_prompt="你是连通性测试助手。只返回严格 JSON。",
                user_prompt='请返回 JSON：{"ok": true, "message": "llm connectivity test"}',
                model=selected_model,
                temperature=0.1,
                json_mode=True,
                timeout_seconds=min(self.settings.llm_timeout_seconds, 30),
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            result = LLMConnectivityTestResult(
                success=True,
                provider_id=provider.provider_id,
                provider_label=provider.label,
                model=selected_model,
                base_url_preview=self._preview_url(provider.api_base),
                response_payload=response_payload,
                error=None,
                tested_at=tested_at,
                latency_ms=latency_ms,
            )
            self._log_test_result(result=result, operator=operator, note=note)
            self.session.commit()
            return result
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            result = LLMConnectivityTestResult(
                success=False,
                provider_id=provider.provider_id,
                provider_label=provider.label,
                model=selected_model,
                base_url_preview=self._preview_url(provider.api_base),
                response_payload=None,
                error=str(exc),
                tested_at=tested_at,
                latency_ms=latency_ms,
            )
            self._log_test_result(result=result, operator=operator, note=note)
            self.session.commit()
            return result

    def _log_test_result(
        self,
        *,
        result: LLMConnectivityTestResult,
        operator: Optional[str],
        note: Optional[str],
    ) -> None:
        self.audit_logs.create(
            AuditLog(
                task_id=None,
                action="phase7.llm.tested",
                operator=self._normalize_operator(operator),
                payload={
                    "provider_id": result.provider_id,
                    "provider_label": result.provider_label,
                    "model": result.model,
                    "success": result.success,
                    "base_url_preview": result.base_url_preview,
                    "latency_ms": result.latency_ms,
                    "response_payload": result.response_payload,
                    "error": result.error,
                    "note": self._normalize_note(note),
                },
            )
        )

    def _load_provider_configs(self) -> list[LLMProviderConfig]:
        raw = self._stored_value(self.PROVIDERS_KEY)
        if not isinstance(raw, list):
            return []
        providers: list[LLMProviderConfig] = []
        for item in raw:
            try:
                providers.append(self._normalize_provider_record(item, allow_missing_api_key=False))
            except ValueError:
                continue
        return providers

    def _build_env_provider(self) -> LLMProviderConfig:
        env_models = self._normalize_models(
            [self.settings.llm_model_analyze, self.settings.llm_model_write, self.settings.llm_model_review],
            field_name="env.models",
        )
        return LLMProviderConfig(
            provider_id=self.ENV_PROVIDER_ID,
            vendor=(self.settings.llm_provider or "").strip() or "env",
            label="环境默认供应商",
            api_base=self._normalize_api_base(
                self.settings.llm_api_base or "https://open.bigmodel.cn/api/coding/paas/v4"
            ),
            api_key=(self.settings.llm_api_key or "").strip(),
            models=env_models,
            is_env_default=True,
        )

    def _normalize_provider_updates(self, providers: list[dict[str, Any]]) -> list[LLMProviderConfig]:
        if not providers:
            raise ValueError("providers must contain at least one provider.")
        existing_by_id = {item.provider_id: item for item in self.resolve_effective_config().providers}
        normalized: list[LLMProviderConfig] = []
        seen_ids: set[str] = set()
        for raw_item in providers:
            if not isinstance(raw_item, dict):
                raise ValueError("Each provider must be an object.")
            provider = self._normalize_provider_record(
                raw_item,
                allow_missing_api_key=True,
                existing_provider=existing_by_id.get(str(raw_item.get("provider_id") or "").strip()),
            )
            if provider.provider_id in seen_ids:
                raise ValueError("provider_id must be unique.")
            seen_ids.add(provider.provider_id)
            normalized.append(provider)
        return normalized

    def _normalize_provider_record(
        self,
        raw_item: dict[str, Any],
        *,
        allow_missing_api_key: bool,
        existing_provider: Optional[LLMProviderConfig] = None,
    ) -> LLMProviderConfig:
        provider_id = self._normalize_non_empty_string(raw_item.get("provider_id"), field_name="provider_id")
        vendor = self._normalize_non_empty_string(raw_item.get("vendor"), field_name=f"{provider_id}.vendor")
        label = self._normalize_non_empty_string(raw_item.get("label"), field_name=f"{provider_id}.label")
        api_base = self._normalize_api_base(raw_item.get("api_base"))
        models = self._normalize_models(raw_item.get("models"), field_name=f"{provider_id}.models")
        raw_api_key = raw_item.get("api_key")
        if raw_api_key is None and existing_provider is not None:
            api_key = existing_provider.api_key
        else:
            api_key = str(raw_api_key or "").strip()
            if not api_key and existing_provider is not None:
                api_key = existing_provider.api_key
        if not api_key and not allow_missing_api_key:
            raise ValueError(f"{provider_id}.api_key must be configured.")
        if not api_key:
            raise ValueError(f"{provider_id}.api_key must be configured.")
        return LLMProviderConfig(
            provider_id=provider_id,
            vendor=vendor,
            label=label,
            api_base=api_base,
            api_key=api_key,
            models=models,
            is_env_default=provider_id == self.ENV_PROVIDER_ID,
        )

    def _resolve_model(self, *, stored_key: str, default_value: str, provider: LLMProviderConfig) -> str:
        stored = self._stored_string(stored_key)
        candidate = stored or (default_value or "").strip()
        if candidate and not isinstance(self._stored_value(self.PROVIDERS_KEY), list):
            return candidate
        if candidate in provider.models:
            return candidate
        if provider.models:
            return provider.models[0]
        return candidate

    def _normalize_selected_model(self, value: Any, provider: LLMProviderConfig, *, field_name: str) -> str:
        normalized = self._normalize_non_empty_string(value, field_name=field_name)
        if normalized not in provider.models:
            raise ValueError(f"{field_name} must reference one of the selected provider models.")
        return normalized

    def _serialize_provider(self, provider: LLMProviderConfig) -> dict[str, Any]:
        return {
            "provider_id": provider.provider_id,
            "vendor": provider.vendor,
            "label": provider.label,
            "api_base": provider.api_base,
            "api_key": provider.api_key,
            "models": list(provider.models),
        }

    def _stored_settings(self) -> dict[str, SystemSetting]:
        if self._stored_settings_cache is None:
            self._stored_settings_cache = {item.key: item for item in self.system_settings.list_all()}
        return self._stored_settings_cache

    def _stored_value(self, key: str) -> Any:
        setting = self._stored_settings().get(key)
        return setting.value if setting is not None else None

    def _stored_string(self, key: str) -> Optional[str]:
        value = self._stored_value(key)
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _normalize_non_empty_string(value: Any, *, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} must be a non-empty string.")
        return normalized

    def _normalize_api_base(self, value: Any) -> str:
        normalized = self._normalize_non_empty_string(value, field_name="api_base").rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("api_base must be a valid http(s) URL.")
        return normalized

    def _normalize_models(self, value: Any, *, field_name: str) -> list[str]:
        if isinstance(value, str):
            raw_items = [item.strip() for item in value.split(",")]
        elif isinstance(value, (list, tuple)):
            raw_items = [str(item).strip() for item in value]
        else:
            raise ValueError(f"{field_name} must be an array of model names.")
        normalized: list[str] = []
        for item in raw_items:
            if not item:
                continue
            if item not in normalized:
                normalized.append(item)
        if not normalized:
            raise ValueError(f"{field_name} must contain at least one model.")
        return normalized

    @staticmethod
    def _preview_secret(value: str) -> Optional[str]:
        normalized = (value or "").strip()
        if not normalized:
            return None
        if len(normalized) <= 8:
            return "*" * len(normalized)
        return f"{normalized[:4]}...{normalized[-4:]}"

    @staticmethod
    def _preview_url(value: str) -> Optional[str]:
        rendered = (value or "").strip()
        if not rendered:
            return None
        parsed = urlparse(rendered)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return rendered

    @staticmethod
    def _normalize_operator(operator: Optional[str]) -> str:
        return (operator or "").strip() or "admin-console"

    @staticmethod
    def _normalize_note(note: Optional[str]) -> Optional[str]:
        normalized = (note or "").strip()
        return normalized or None
