from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
from typing import Optional

from fastapi import Cookie, Header, HTTPException, Response, status

from app.settings import get_settings

ADMIN_SESSION_COOKIE_NAME = "wechat_artical_admin_session"
ADMIN_SESSION_MAX_AGE_SECONDS = 60 * 60 * 8


def verify_bearer_token(
    authorization: Optional[str] = Header(default=None),
    admin_session: Optional[str] = Cookie(default=None, alias=ADMIN_SESSION_COOKIE_NAME),
) -> None:
    settings = get_settings()
    if authorization == f"Bearer {settings.api_bearer_token}":
        return
    if _matches_admin_session_cookie(admin_session, settings):
        return

    username, password = _get_admin_basic_auth_credentials(settings)
    if username or password:
        if not username or not password:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Admin auth is misconfigured.",
            )
        if authorization and authorization.startswith("Basic "):
            _verify_admin_basic_auth_header(authorization, username, password)
            return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authorization token.",
    )


def verify_admin_basic_auth(
    response: Response,
    authorization: Optional[str] = Header(default=None),
    admin_session: Optional[str] = Cookie(default=None, alias=ADMIN_SESSION_COOKIE_NAME),
) -> None:
    settings = get_settings()
    username, password = _get_admin_basic_auth_credentials(settings)
    if not username and not password:
        return
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin auth is misconfigured.",
        )
    if _matches_admin_session_cookie(admin_session, settings):
        _set_admin_session_cookie(response, settings, username, password)
        return
    _verify_admin_basic_auth_header(authorization, username, password)
    _set_admin_session_cookie(response, settings, username, password)

def _get_admin_basic_auth_credentials(settings) -> tuple[str, str]:
    username = (settings.admin_username or "").strip()
    password = settings.admin_password or ""
    return username, password


def _verify_admin_basic_auth_header(authorization: Optional[str], username: str, password: str) -> None:
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


def _matches_admin_session_cookie(admin_session: Optional[str], settings) -> bool:
    if not isinstance(admin_session, str) or not admin_session:
        return False
    username, password = _get_admin_basic_auth_credentials(settings)
    if not username or not password:
        return False
    expected = _build_admin_session_value(settings, username, password)
    return secrets.compare_digest(admin_session, expected)


def _build_admin_session_value(settings, username: str, password: str) -> str:
    payload = f"{username}:{password}".encode("utf-8")
    secret = settings.api_bearer_token.encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def _set_admin_session_cookie(response: Response, settings, username: str, password: str) -> None:
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE_NAME,
        value=_build_admin_session_value(settings, username, password),
        httponly=True,
        samesite="lax",
        secure=settings.app_base_url.startswith("https://"),
        max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        path="/",
    )


def _raise_admin_auth_error() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid admin credentials.",
        headers={"WWW-Authenticate": 'Basic realm="wechat_artical-admin"'},
    )
