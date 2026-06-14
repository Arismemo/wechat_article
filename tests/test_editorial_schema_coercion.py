import unittest

from pydantic import ValidationError

from app.schemas.editorial import EditorialVerdict, RoleOpinion


class SchemaCoercionTests(unittest.TestCase):
    def test_issues_dicts_coerced_to_strings(self) -> None:
        # GLM-5.2 真跑曾返回 issues 为 dict 列表
        o = RoleOpinion.model_validate(
            {"role_key": "proofreader", "stance": "revise",
             "issues": [{"type": "标点遗漏", "detail": "句末缺标点"}, "另一个问题"]}
        )
        self.assertEqual(len(o.issues), 2)
        self.assertTrue(all(isinstance(x, str) for x in o.issues))
        self.assertIn("标点遗漏", o.issues[0])

    def test_stance_chinese_mapped(self) -> None:
        self.assertEqual(RoleOpinion.model_validate({"role_key": "x", "stance": "通过"}).stance, "pass")
        self.assertEqual(RoleOpinion.model_validate({"role_key": "x", "stance": "驳回重写"}).stance, "reject")

    def test_stance_still_rejects_garbage(self) -> None:
        with self.assertRaises(ValidationError):
            RoleOpinion.model_validate({"role_key": "x", "stance": "maybe"})

    def test_scores_string_values_coerced(self) -> None:
        o = RoleOpinion.model_validate({"role_key": "x", "stance": "pass", "scores": {"clarity": "80", "bad": "n/a"}})
        self.assertEqual(o.scores["clarity"], 80.0)
        self.assertNotIn("bad", o.scores)  # 不可解析的丢弃

    def test_verdict_decision_chinese_and_string_directive(self) -> None:
        v = EditorialVerdict.model_validate(
            {"decision": "修改", "final_scores": {"overall": "72"},
             "revision_directives": ["把标题加上数字"]}
        )
        self.assertEqual(v.decision, "revise")
        self.assertEqual(v.final_scores["overall"], 72.0)
        self.assertEqual(v.revision_directives[0].fix, "把标题加上数字")


if __name__ == "__main__":
    unittest.main()
