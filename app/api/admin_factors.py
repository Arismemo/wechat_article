"""因子库管理 API + 页面。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import verify_admin_api_auth
from app.db.session import get_db_session
from app.models.factor import Factor
from app.repositories.factor_repository import FactorRepository

router = APIRouter()


# ── Pydantic Schemas ──


class FactorCreate(BaseModel):
    name: str
    dimension: str
    technique: str
    effect: Optional[str] = None
    example_text: Optional[str] = None
    anti_example: Optional[str] = None
    tags: Optional[list[str]] = None
    applicable_domains: Optional[list[str]] = None
    conflict_group: Optional[str] = None
    source_url: Optional[str] = None
    source_type: str = "manual"
    status: str = "draft"


class FactorUpdate(BaseModel):
    name: Optional[str] = None
    dimension: Optional[str] = None
    technique: Optional[str] = None
    effect: Optional[str] = None
    example_text: Optional[str] = None
    anti_example: Optional[str] = None
    tags: Optional[list[str]] = None
    applicable_domains: Optional[list[str]] = None
    conflict_group: Optional[str] = None
    source_url: Optional[str] = None
    status: Optional[str] = None


class FactorStatusPatch(BaseModel):
    status: str


class FactorResponse(BaseModel):
    id: str
    name: str
    dimension: str
    technique: str
    effect: Optional[str] = None
    example_text: Optional[str] = None
    anti_example: Optional[str] = None
    tags: Optional[list] = None
    applicable_domains: Optional[list] = None
    conflict_group: Optional[str] = None
    source_url: Optional[str] = None
    source_type: str
    extract_count: int
    status: str
    avg_effect_score: Optional[float] = None
    usage_count: int
    created_at: str
    updated_at: str


def _to_response(f: Factor) -> FactorResponse:
    return FactorResponse(
        id=f.id,
        name=f.name,
        dimension=f.dimension,
        technique=f.technique,
        effect=f.effect,
        example_text=f.example_text,
        anti_example=f.anti_example,
        tags=f.tags or [],
        applicable_domains=f.applicable_domains or [],
        conflict_group=f.conflict_group,
        source_url=f.source_url,
        source_type=f.source_type,
        extract_count=f.extract_count,
        status=f.status,
        avg_effect_score=f.avg_effect_score,
        usage_count=f.usage_count,
        created_at=f.created_at.isoformat(),
        updated_at=f.updated_at.isoformat(),
    )


# ── CRUD API ──


@router.get("/admin/factors/list", response_model=list[FactorResponse], dependencies=[Depends(verify_admin_api_auth)])
def list_factors(
    dimension: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    session: Session = Depends(get_db_session),
) -> list[FactorResponse]:
    repo = FactorRepository(session)
    factors = repo.list_factors(dimension=dimension, status=status, query=query, limit=limit, offset=offset)
    return [_to_response(f) for f in factors]


@router.get("/admin/factors/stats", dependencies=[Depends(verify_admin_api_auth)])
def factor_stats(session: Session = Depends(get_db_session)):
    repo = FactorRepository(session)
    return repo.count_by_status()


@router.get("/admin/factors/{factor_id}", response_model=FactorResponse, dependencies=[Depends(verify_admin_api_auth)])
def get_factor(factor_id: str, session: Session = Depends(get_db_session)) -> FactorResponse:
    repo = FactorRepository(session)
    f = repo.get_by_id(factor_id)
    if f is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factor not found")
    return _to_response(f)


@router.post("/admin/factors", response_model=FactorResponse, dependencies=[Depends(verify_admin_api_auth)])
def create_factor(payload: FactorCreate, session: Session = Depends(get_db_session)) -> FactorResponse:
    repo = FactorRepository(session)
    factor = Factor(
        name=payload.name,
        dimension=payload.dimension,
        technique=payload.technique,
        effect=payload.effect,
        example_text=payload.example_text,
        anti_example=payload.anti_example,
        tags=payload.tags or [],
        applicable_domains=payload.applicable_domains or [],
        conflict_group=payload.conflict_group,
        source_url=payload.source_url,
        source_type=payload.source_type,
        status=payload.status,
    )
    factor = repo.create(factor)
    session.commit()
    return _to_response(factor)


@router.put("/admin/factors/{factor_id}", response_model=FactorResponse, dependencies=[Depends(verify_admin_api_auth)])
def update_factor(factor_id: str, payload: FactorUpdate, session: Session = Depends(get_db_session)) -> FactorResponse:
    repo = FactorRepository(session)
    factor = repo.get_by_id(factor_id)
    if factor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factor not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(factor, key, val)
    repo.update(factor)
    session.commit()
    return _to_response(factor)


@router.patch("/admin/factors/{factor_id}/status", response_model=FactorResponse, dependencies=[Depends(verify_admin_api_auth)])
def patch_factor_status(factor_id: str, payload: FactorStatusPatch, session: Session = Depends(get_db_session)) -> FactorResponse:
    repo = FactorRepository(session)
    factor = repo.update_status(factor_id, payload.status)
    if factor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factor not found")
    session.commit()
    return _to_response(factor)


@router.delete("/admin/factors/{factor_id}", dependencies=[Depends(verify_admin_api_auth)])
def delete_factor(factor_id: str, session: Session = Depends(get_db_session)):
    repo = FactorRepository(session)
    factor = repo.get_by_id(factor_id)
    if factor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factor not found")
    session.delete(factor)
    session.commit()
    return {"ok": True}
