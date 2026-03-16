from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import verify_admin_api_auth
from app.db.session import get_db_session
from app.schemas.admin_llm import (
    AdminLLMConfigResponse,
    AdminLLMConfigUpdateRequest,
    AdminLLMTestRequest,
    AdminLLMTestResponse,
)
from app.schemas.admin_runtime import AdminAlertTestRequest, AdminAlertTestResponse, AdminRuntimeStatusResponse
from app.schemas.system_settings import SystemSettingResponse, SystemSettingUpdateRequest
from app.services.admin_runtime_service import AdminRuntimeService
from app.services.alert_service import AlertService
from app.services.llm_runtime_service import LLMRuntimeService
from app.services.system_setting_service import SystemSettingService


router = APIRouter()


@router.get("/admin/settings", response_model=list[SystemSettingResponse], dependencies=[Depends(verify_admin_api_auth)])
def list_admin_settings(session: Session = Depends(get_db_session)) -> list[SystemSettingResponse]:
    service = SystemSettingService(session)
    return [_build_response(item) for item in service.list_settings()]


@router.get("/admin/runtime-status", response_model=AdminRuntimeStatusResponse, dependencies=[Depends(verify_admin_api_auth)])
def get_admin_runtime_status(session: Session = Depends(get_db_session)) -> AdminRuntimeStatusResponse:
    return AdminRuntimeService(session).build_runtime_status()


@router.get("/admin/llm-config", response_model=AdminLLMConfigResponse, dependencies=[Depends(verify_admin_api_auth)])
def get_admin_llm_config(session: Session = Depends(get_db_session)) -> AdminLLMConfigResponse:
    return _build_llm_config_response(LLMRuntimeService(session).get_config_view())


@router.get("/admin/settings/{key}", response_model=SystemSettingResponse, dependencies=[Depends(verify_admin_api_auth)])
def get_admin_setting(key: str, session: Session = Depends(get_db_session)) -> SystemSettingResponse:
    service = SystemSettingService(session)
    try:
        return _build_response(service.get_setting(key))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.args[0]) from exc


@router.put("/admin/settings/{key}", response_model=SystemSettingResponse, dependencies=[Depends(verify_admin_api_auth)])
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


@router.put("/admin/llm-config", response_model=AdminLLMConfigResponse, dependencies=[Depends(verify_admin_api_auth)])
def update_admin_llm_config(
    payload: AdminLLMConfigUpdateRequest,
    session: Session = Depends(get_db_session),
) -> AdminLLMConfigResponse:
    service = LLMRuntimeService(session)
    try:
        result = service.update_config(
            providers=[item.model_dump() for item in payload.providers],
            active_provider_id=payload.active_provider_id,
            analyze_model=payload.analyze_model,
            write_model=payload.write_model,
            review_model=payload.review_model,
            operator=payload.operator,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _build_llm_config_response(result)


@router.post("/admin/llm-test", response_model=AdminLLMTestResponse, dependencies=[Depends(verify_admin_api_auth)])
def test_admin_llm_provider(
    payload: AdminLLMTestRequest,
    session: Session = Depends(get_db_session),
) -> AdminLLMTestResponse:
    service = LLMRuntimeService(session)
    try:
        result = service.test_provider(
            provider_id=payload.provider_id,
            model=payload.model,
            operator=payload.operator,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AdminLLMTestResponse(
        success=result.success,
        provider_id=result.provider_id,
        provider_label=result.provider_label,
        model=result.model,
        base_url_preview=result.base_url_preview,
        response_payload=result.response_payload,
        error=result.error,
        tested_at=result.tested_at,
        latency_ms=result.latency_ms,
    )


@router.post("/admin/alerts/test", response_model=AdminAlertTestResponse, dependencies=[Depends(verify_admin_api_auth)])
def send_admin_test_alert(
    payload: AdminAlertTestRequest,
    session: Session = Depends(get_db_session),
) -> AdminAlertTestResponse:
    service = AlertService(session)
    try:
        return service.send_test_alert(operator=payload.operator, note=payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


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


def _build_llm_config_response(config) -> AdminLLMConfigResponse:
    return AdminLLMConfigResponse(
        providers=[
            {
                "provider_id": item.provider_id,
                "vendor": item.vendor,
                "label": item.label,
                "api_base": item.api_base,
                "models": list(item.models),
                "has_api_key": item.has_api_key,
                "api_key_preview": item.api_key_preview,
                "is_env_default": item.is_env_default,
            }
            for item in config.providers
        ],
        selection={
            "active_provider_id": config.selection.active_provider_id,
            "analyze_model": config.selection.analyze_model,
            "write_model": config.selection.write_model,
            "review_model": config.selection.review_model,
        },
    )
