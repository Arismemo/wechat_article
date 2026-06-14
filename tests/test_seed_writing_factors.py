from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers all ORM models with Base.metadata
from app.db.base import Base
from scripts.seed_writing_factors import WRITING_FACTORS, seed


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class SeedWritingFactorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)

    # ── helpers ──────────────────────────────────────────────────────────

    def _count_factors(self, session) -> int:
        from sqlalchemy import func, select
        from app.models.factor import Factor

        return session.scalar(select(func.count()).select_from(Factor))

    # ── tests ────────────────────────────────────────────────────────────

    def test_seed_inserts_all_factors(self) -> None:
        """First seed call inserts every factor in WRITING_FACTORS."""
        session = self.Session()
        try:
            result = seed(session)
            session.commit()

            self.assertEqual(result["inserted"], len(WRITING_FACTORS))
            self.assertEqual(result["skipped"], 0)
            self.assertEqual(self._count_factors(session), len(WRITING_FACTORS))
        finally:
            session.close()

    def test_seed_inserts_expected_names_and_dimensions(self) -> None:
        """Spot-check specific names and dimensions after seeding."""
        session = self.Session()
        try:
            seed(session)
            session.commit()

            from sqlalchemy import select
            from app.models.factor import Factor

            factors = {f.name: f for f in session.scalars(select(Factor)).all()}

            # 去AI味类 → rhetoric
            self.assertIn("排序词口语化", factors)
            self.assertEqual(factors["排序词口语化"].dimension, "rhetoric")

            self.assertIn("书面大词清洗", factors)
            self.assertEqual(factors["书面大词清洗"].dimension, "rhetoric")

            self.assertIn("人设四件套", factors)
            self.assertEqual(factors["人设四件套"].dimension, "rhetoric")

            # 节奏类 → rhythm
            self.assertIn("长短句交替", factors)
            self.assertEqual(factors["长短句交替"].dimension, "rhythm")

            self.assertIn("句子开头多样化", factors)
            self.assertEqual(factors["句子开头多样化"].dimension, "rhythm")

            # 钩子类 → opening
            self.assertIn("缺口甜区标题", factors)
            self.assertEqual(factors["缺口甜区标题"].dimension, "opening")

            self.assertIn("开头三模板", factors)
            self.assertEqual(factors["开头三模板"].dimension, "opening")

            # 传播类 → structure
            self.assertIn("故事容器", factors)
            self.assertEqual(factors["故事容器"].dimension, "structure")

            self.assertIn("awe认知冲击", factors)
            self.assertEqual(factors["awe认知冲击"].dimension, "structure")

            # CTA类 → closing
            self.assertIn("单一CTA", factors)
            self.assertEqual(factors["单一CTA"].dimension, "closing")

            self.assertIn("四选一收口", factors)
            self.assertEqual(factors["四选一收口"].dimension, "closing")

            self.assertIn("推荐语五件套", factors)
            self.assertEqual(factors["推荐语五件套"].dimension, "closing")
        finally:
            session.close()

    def test_seed_idempotent_second_call_inserts_nothing(self) -> None:
        """Calling seed() twice: second call inserts 0, skips all."""
        session = self.Session()
        try:
            result1 = seed(session)
            session.commit()

            result2 = seed(session)
            session.commit()

            self.assertEqual(result1["inserted"], len(WRITING_FACTORS))
            self.assertEqual(result2["inserted"], 0)
            self.assertEqual(result2["skipped"], len(WRITING_FACTORS))
            # Total rows in DB unchanged
            self.assertEqual(self._count_factors(session), len(WRITING_FACTORS))
        finally:
            session.close()

    def test_dry_run_inserts_nothing(self) -> None:
        """dry_run=True should not write any rows to the database."""
        session = self.Session()
        try:
            result = seed(session, dry_run=True)
            session.commit()

            self.assertEqual(result["inserted"], 0)
            self.assertEqual(self._count_factors(session), 0)
        finally:
            session.close()

    def test_dry_run_reports_correct_skipped_when_some_exist(self) -> None:
        """dry_run after a real seed reports all as skipped."""
        session = self.Session()
        try:
            seed(session)
            session.commit()

            result = seed(session, dry_run=True)
            self.assertEqual(result["inserted"], 0)
            self.assertEqual(result["skipped"], len(WRITING_FACTORS))
        finally:
            session.close()

    def test_factor_count_matches_writing_factors_list(self) -> None:
        """WRITING_FACTORS list has the expected minimum count (~28)."""
        self.assertGreaterEqual(len(WRITING_FACTORS), 28)

    def test_all_factors_have_required_fields(self) -> None:
        """Every entry in WRITING_FACTORS has name, dimension, technique, status, source_type."""
        valid_dimensions = {"opening", "structure", "rhetoric", "rhythm", "layout", "closing"}
        valid_statuses = {"pending", "draft", "active", "deprecated", "archived"}
        valid_source_types = {"ai_extracted", "manual"}

        for factor in WRITING_FACTORS:
            name = factor.get("name", "")
            with self.subTest(factor=name):
                self.assertTrue(name, "name must not be empty")
                self.assertIn(factor.get("dimension"), valid_dimensions)
                self.assertTrue(factor.get("technique"), "technique must not be empty")
                self.assertIn(factor.get("status"), valid_statuses)
                self.assertIn(factor.get("source_type"), valid_source_types)

    def test_factor_names_are_unique(self) -> None:
        """No duplicate names in WRITING_FACTORS."""
        names = [f["name"] for f in WRITING_FACTORS]
        self.assertEqual(len(names), len(set(names)), "Duplicate factor names found")


if __name__ == "__main__":
    unittest.main()
