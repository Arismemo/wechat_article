from __future__ import annotations

import base64
import binascii
import secrets
from typing import Optional

from fastapi import Header, HTTPException, status

from app.settings import get_settings


def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    settings = get_settings()
    expected = f"Bearer {settings.api_bearer_token}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token.",
        )


def verify_admin_basic_auth(authorization: Optional[str] = Header(default=None)) -> None:
    settings = get_settings()
    username = (settings.admin_username or "").strip()
    password = settings.admin_password or ""
    if not username and not password:
        return
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin auth is misconfigured.",
        )

    if not authorization or not authorization.startswith("Basic "):
        _raise_admin_auth_error()

    try:
        raw_value = authorization.split(" ", 1)[1]
        decoded = base64.b64decode(raw_value).decode("utf-8")
        supplied_username, supplied_password = decoded.split(":", 1)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        _raise_admin_auth_error()
        return

    if not secrets.compare_digest(supplied_username, username) or not secrets.compare_digest(supplied_password, password):
        _raise_admin_auth_error()


def _raise_admin_auth_error() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid admin credentials.",
        headers={"WWW-Authenticate": 'Basic realm="wechat_artical-admin"'},
    )
