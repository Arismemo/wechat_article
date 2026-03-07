from __future__ import annotations

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
