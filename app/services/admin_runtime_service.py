from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.schemas.admin_runtime import AdminRuntimeStatusResponse, RuntimeAlertStatusResponse, RuntimeEnvStatusResponse
from app.services.system_setting_service import SystemSettingService
from app.settings import Settings, get_settings


@dataclass(frozen=True)
class RuntimeEnvDefinition:
    key: str
    label: str
    category: str
    required: bool
    secret: bool
    resolver: Callable[[Settings], object]
    note_resolver: Optional[Callable[[Settings, SystemSettingService], Optional[str]]] = None


class AdminRuntimeService:
    _DEFINITIONS = (
        RuntimeEnvDefinition(
            key="APP_ENV",
            label="运行环境",
            category="app",
            required=True,
            secret=False,
            resolver=lambda settings: settings.app_env,
        ),
        RuntimeEnvDefinition(
            key="APP_BASE_URL",
            label="对外服务地址",
            category="app",
            required=True,
            secret=False,
            resolver=lambda settings: settings.app_base_url,
        ),
        RuntimeEnvDefinition(
            key="TIMEZONE",
            label="系统时区",
            category="app",
            required=True,
            secret=False,
            resolver=lambda settings: settings.timezone,
        ),
        RuntimeEnvDefinition(
            key="DATABASE_URL",
            label="数据库连接",
            category="infra",
            required=True,
            secret=True,
            resolver=lambda settings: settings.database_url,
        ),
        RuntimeEnvDefinition(
            key="REDIS_URL",
            label="Redis 连接",
            category="infra",
            required=True,
            secret=True,
            resolver=lambda settings: settings.redis_url,
        ),
        RuntimeEnvDefinition(
            key="ADMIN_USERNAME",
            label="后台用户名",
            category="security",
            required=False,
            secret=False,
            resolver=lambda settings: settings.admin_username,
            note_resolver=lambda _settings, _runtime: "仅控制后台 Basic Auth 用户名。",
        ),
        RuntimeEnvDefinition(
            key="ADMIN_PASSWORD",
            label="后台密码",
            category="security",
            required=False,
            secret=True,
            resolver=lambda settings: settings.admin_password,
            note_resolver=lambda _settings, _runtime: "Basic Auth 关闭时可留空。",
        ),
        RuntimeEnvDefinition(
            key="API_BEARER_TOKEN",
            label="API Bearer Token",
            category="security",
            required=True,
            secret=True,
            resolver=lambda settings: settings.api_bearer_token,
        ),
        RuntimeEnvDefinition(
            key="INGEST_SHORTCUT_SHARED_KEY",
            label="快捷指令共享密钥",
            category="security",
            required=False,
            secret=True,
            resolver=lambda settings: settings.ingest_shortcut_shared_key,
            note_resolver=lambda _settings, _runtime: "未配置时快捷指令入口会回退使用 API_BEARER_TOKEN。",
        ),
        RuntimeEnvDefinition(
            key="LLM_API_KEY",
            label="写稿/审稿 API Key",
            category="integrations",
            required=True,
            secret=True,
            resolver=lambda settings: settings.llm_api_key,
        ),
        RuntimeEnvDefinition(
            key="WECHAT_APP_SECRET",
            label="微信 App Secret",
            category="integrations",
            required=True,
            secret=True,
            resolver=lambda settings: settings.wechat_app_secret,
        ),
        RuntimeEnvDefinition(
            key="FEEDBACK_SYNC_HTTP_URL",
            label="自动反馈 HTTP Provider",
            category="integrations",
            required=False,
            secret=False,
            resolver=lambda settings: settings.feedback_sync_http_url,
            note_resolver=lambda _settings, runtime: (
                "当前 feedback.sync_provider=http，必须配置。"
                if runtime.feedback_sync_provider() == "http"
                else "仅当自动反馈 Provider 切到 http 时需要。"
            ),
        ),
        RuntimeEnvDefinition(
            key="ALERT_WEBHOOK_URL",
            label="告警 Webhook",
            category="observability",
            required=False,
            secret=False,
            resolver=lambda settings: settings.alert_webhook_url,
            note_resolver=lambda _settings, _runtime: "配置后可在后台发送测试告警。",
        ),
    )

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.runtime_settings = SystemSettingService(session)

    def build_runtime_status(self) -> AdminRuntimeStatusResponse:
        environment = [
            RuntimeEnvStatusResponse(
                key=item.key,
                label=item.label,
                category=item.category,
                configured=self._is_configured(value := item.resolver(self.settings)),
                required=item.required,
                secret=item.secret,
                preview=self._preview_value(value, secret=item.secret),
                note=item.note_resolver(self.settings, self.runtime_settings) if item.note_resolver else None,
            )
            for item in self._DEFINITIONS
        ]
        return AdminRuntimeStatusResponse(
            environment=environment,
            alerts=RuntimeAlertStatusResponse(
                enabled=self._is_configured(self.settings.alert_webhook_url),
                provider="webhook",
                destination_preview=self._preview_value(self.settings.alert_webhook_url, secret=False),
                note="未配置时只会关闭测试告警入口，不影响主流程。" if not self.settings.alert_webhook_url else None,
            ),
        )

    @staticmethod
    def _is_configured(value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return True
        return bool(str(value).strip())

    @staticmethod
    def _preview_value(value: object, *, secret: bool) -> Optional[str]:
        if value is None:
            return None
        if secret:
            return None
        rendered = str(value).strip()
        if not rendered:
            return None
        if rendered.startswith("http://") or rendered.startswith("https://"):
            parsed = urlparse(rendered)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        return rendered
