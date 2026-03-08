from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import verify_bearer_token
from app.db.session import get_db_session
from app.schemas.system_settings import SystemSettingResponse, SystemSettingUpdateRequest
from app.services.system_setting_service import SystemSettingService


router = APIRouter()


@router.get("/admin/settings", response_model=list[SystemSettingResponse], dependencies=[Depends(verify_bearer_token)])
def list_admin_settings(session: Session = Depends(get_db_session)) -> list[SystemSettingResponse]:
    service = SystemSettingService(session)
    return [_build_response(item) for item in service.list_settings()]


@router.get("/admin/settings/{key}", response_model=SystemSettingResponse, dependencies=[Depends(verify_bearer_token)])
def get_admin_setting(key: str, session: Session = Depends(get_db_session)) -> SystemSettingResponse:
    service = SystemSettingService(session)
    try:
        return _build_response(service.get_setting(key))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.args[0]) from exc


@router.put("/admin/settings/{key}", response_model=SystemSettingResponse, dependencies=[Depends(verify_bearer_token)])
def update_admin_setting(
    key: str,
    payload: SystemSettingUpdateRequest,
    session: Session = Depends(get_db_session),
) -> SystemSettingResponse:
    service = SystemSettingService(session)
    try:
        if payload.reset_to_default:
            setting = service.reset_setting(key, operator=payload.operator, note=payload.note)
        else:
            if payload.value is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="value is required.")
            setting = service.update_setting(key, payload.value, operator=payload.operator, note=payload.note)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.args[0]) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _build_response(setting)


def _build_response(setting) -> SystemSettingResponse:
    return SystemSettingResponse(
        key=setting.key,
        label=setting.label,
        description=setting.description,
        category=setting.category,
        value_type=setting.value_type,
        default_value=setting.default_value,
        stored_value=setting.stored_value,
        effective_value=setting.effective_value,
        has_override=setting.has_override,
        options=[{"value": item.value, "label": item.label} for item in setting.options],
        requires_restart=setting.requires_restart,
        updated_at=setting.updated_at,
    )
