import unittest
from pydantic import ValidationError
from app.schemas.editorial import RoleOpinion, ConvergenceJudgement, EditorialVerdict, RevisionDirective  # noqa: F401


class EditorialSchemaTests(unittest.TestCase):
    def test_role_opinion_ok(self) -> None:
        o = RoleOpinion(role_key="copy_editor", scores={"ai_trace": 70}, issues=["排序词过多"], stance="revise", key_argument="机械腔重")
        self.assertEqual(o.stance, "revise")

    def test_stance_rejects_invalid(self) -> None:
        with self.assertRaises(ValidationError):
            RoleOpinion(role_key="x", scores={}, issues=[], stance="maybe", key_argument="")

    def test_verdict_with_directives(self) -> None:
        v = EditorialVerdict(decision="revise", final_scores={"overall": 72},
                             rationale="标题弱", revision_directives=[RevisionDirective(location="标题", problem="无数字", fix="加具体数字")],
                             dissent_summary="法务保留")
        self.assertEqual(v.revision_directives[0].location, "标题")
