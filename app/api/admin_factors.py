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


# ── 因子提取 API ──


class FactorExtractRequest(BaseModel):
    url: str
    max_factors: int = 5


@router.post("/admin/factors/extract", dependencies=[Depends(verify_admin_api_auth)])
def extract_factors(payload: FactorExtractRequest, session: Session = Depends(get_db_session)):
    """调用 LLM 分析文章内容，提取写作因子。"""
    import logging

    from app.services.llm_runtime_service import LLMRuntimeService
    from app.services.source_fetch_service import SourceFetchService

    log = logging.getLogger(__name__)

    # 1. 抓取文章内容
    try:
        fetcher = SourceFetchService()
        source_type = "wechat" if "mp.weixin.qq.com" in payload.url else "generic"
        fetched = fetcher.fetch(
            task_id="factor-extract-temp",
            url=payload.url,
            source_type=source_type,
        )
    except Exception as exc:
        log.warning("因子提取：文章抓取失败 url=%s err=%s", payload.url, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"文章抓取失败：{exc}",
        )

    # 2. 截取文章内容（避免 token 过长）
    article_text = fetched.cleaned_text[:6000]
    article_title = fetched.title or "未知标题"

    # 3. 构造提取 Prompt
    system_prompt = (
        "你是写作技巧分析专家。"
        "请从文章中提取通用的、和话题无关的写作技巧因子。"
        "每个因子代表一个可迁移到其他主题文章中的写作技法。"
        "只返回严格 JSON，不要输出 Markdown 或解释。"
    )
    user_prompt = (
        f"请分析以下文章，提取最多 {payload.max_factors} 个写作因子。\n\n"
        "每个因子必须：\n"
        "1. 和话题无关，是通用的写作技巧\n"
        "2. 粒度尽可能小，只描述一个具体技法\n"
        "3. 可迁移到其他主题的文章中\n\n"
        '返回 JSON：{"factors": [{"name": "因子名称（4-15字）", '
        '"dimension": "opening|structure|rhetoric|rhythm|layout|closing", '
        '"technique": "给 AI 的写作指令（20-100字）", '
        '"confidence": 0到100的置信度}]}\n\n'
        "dimension 取值说明：\n"
        "- opening: 开头技巧（钩子、数据、场景带入等）\n"
        "- structure: 结构技巧（论证框架、总分总、递进等）\n"
        "- rhetoric: 修辞技巧（类比、隐喻、对比、拟人等）\n"
        "- rhythm: 节奏技巧（长短句、变速、停顿等）\n"
        "- layout: 排版技巧（段落节奏、留白、视觉层次等）\n"
        "- closing: 结尾技巧（回环、升华、开放式结尾等）\n\n"
        f"文章标题：{article_title}\n\n"
        f"文章正文：\n{article_text}\n"
    )

    # 4. 调用 LLM
    try:
        llm_runtime = LLMRuntimeService(session)
        llm = llm_runtime.build_llm_service()
        analyze_model = llm_runtime.analyze_model()
        result = llm.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=analyze_model,
            temperature=0.3,
            json_mode=True,
            timeout_seconds=60,
        )
    except Exception as exc:
        log.warning("因子提取：LLM 调用失败 err=%s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 提取失败：{exc}",
        )

    # 5. 解析并规范化结果
    raw_factors = result.get("factors", []) if isinstance(result, dict) else []
    valid_dims = {"opening", "structure", "rhetoric", "rhythm", "layout", "closing"}
    factors = []
    for f in raw_factors[:payload.max_factors]:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name", "")).strip()
        dim = str(f.get("dimension", "")).strip()
        technique = str(f.get("technique", "")).strip()
        if not name or not technique:
            continue
        if dim not in valid_dims:
            dim = "rhetoric"
        factors.append({
            "name": name,
            "dimension": dim,
            "technique": technique,
            "confidence": min(100, max(0, int(f.get("confidence", 70)))),
        })

    return {
        "factors": factors,
        "article_title": article_title,
        "article_url": payload.url,
    }


# ── 因子绑定到 Brief ──


class FactorBindRequest(BaseModel):
    brief_id: str
    factor_ids: list[str]


@router.patch("/admin/factors/bind-to-brief", dependencies=[Depends(verify_admin_api_auth)])
def bind_factors_to_brief(payload: FactorBindRequest, session: Session = Depends(get_db_session)):
    """将指定因子绑定到 ContentBrief 的 writing_factors 中。"""
    from app.repositories.content_brief_repository import ContentBriefRepository

    brief_repo = ContentBriefRepository(session)
    brief = brief_repo.get_by_id(payload.brief_id)
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brief not found")

    factor_repo = FactorRepository(session)
    factors_data = []
    for fid in payload.factor_ids:
        f = factor_repo.get_by_id(fid)
        if f is None or f.status != "active":
            continue
        factors_data.append({
            "id": f.id,
            "name": f.name,
            "dimension": f.dimension,
            "technique": f.technique,
            "example_text": f.example_text or "",
        })

    brief.writing_factors = {
        "factors": factors_data,
        "selection_mode": "manual",
    }
    session.commit()

    return {
        "ok": True,
        "brief_id": brief.id,
        "factor_count": len(factors_data),
        "writing_factors": brief.writing_factors,
    }

