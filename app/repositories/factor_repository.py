from __future__ import annotations

from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.factor import Factor


class FactorRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ── 查询 ──

    def get_by_id(self, factor_id: str) -> Optional[Factor]:
        return self.session.get(Factor, factor_id)

    def list_factors(
        self,
        *,
        dimension: Optional[str] = None,
        status: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Factor]:
        statement = select(Factor)
        if dimension:
            statement = statement.where(Factor.dimension == dimension)
        if status:
            statement = statement.where(Factor.status == status)
        if query:
            pattern = f"%{query.strip()}%"
            statement = statement.where(
                or_(
                    Factor.name.ilike(pattern),
                    Factor.technique.ilike(pattern),
                    Factor.tags.cast(str).ilike(pattern),
                )
            )
        statement = statement.order_by(Factor.created_at.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(statement))

    def list_by_status(self, status: str, *, limit: int = 50) -> list[Factor]:
        statement = (
            select(Factor)
            .where(Factor.status == status)
            .order_by(Factor.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def count_by_status(self) -> dict[str, int]:
        """返回各状态的因子数量。"""
        factors = self.session.scalars(select(Factor)).all()
        counts: dict[str, int] = {}
        for f in factors:
            counts[f.status] = counts.get(f.status, 0) + 1
        return counts

    # ── 写入 ──

    def create(self, factor: Factor) -> Factor:
        self.session.add(factor)
        self.session.flush()
        return factor

    def update(self, factor: Factor) -> Factor:
        self.session.flush()
        return factor

    def update_status(self, factor_id: str, new_status: str) -> Optional[Factor]:
        factor = self.get_by_id(factor_id)
        if factor is None:
            return None
        factor.status = new_status
        self.session.flush()
        return factor
