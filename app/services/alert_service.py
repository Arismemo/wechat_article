from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.repositories.audit_log_repository import AuditLogRepository
from app.schemas.admin_runtime import AdminAlertTestResponse
from app.settings import get_settings


class AlertService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.audit_logs = AuditLogRepository(session)

    def send_test_alert(self, *, operator: Optional[str] = None, note: Optional[str] = None) -> AdminAlertTestResponse:
        webhook_url = (self.settings.alert_webhook_url or "").strip()
        if not webhook_url:
            raise ValueError("ALERT_WEBHOOK_URL is not configured.")

        sent_at = datetime.now(timezone.utc)
        payload = {
            "event": "phase7.test_alert",
            "app": "wechat_artical",
            "app_env": self.settings.app_env,
            "base_url": self.settings.app_base_url,
            "sent_at": sent_at.isoformat(),
            "operator": (operator or "admin-console").strip() or "admin-console",
            "note": note.strip() if note else None,
            "message": "Phase 7D test alert",
        }
        response = httpx.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()

        destination_preview = self._preview_destination(webhook_url)
        self.audit_logs.create(
            AuditLog(
                task_id=None,
                action="phase7.alert.test_sent",
                operator=(operator or "admin-console").strip() or "admin-console",
                payload={
                    "destination": destination_preview,
                    "status_code": response.status_code,
                    "note": note.strip() if note else None,
                    "sent_at": sent_at.isoformat(),
                },
            )
        )
        self.session.commit()
        return AdminAlertTestResponse(
            sent=True,
            provider="webhook",
            destination_preview=destination_preview,
            sent_at=sent_at,
            note=note.strip() if note else None,
        )

    @staticmethod
    def _preview_destination(value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return value
