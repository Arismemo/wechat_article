import unittest

from app.services.editorial_board_service import _unwrap_envelope


class UnwrapEnvelopeTests(unittest.TestCase):
    def test_passthrough_when_field_present(self) -> None:
        raw = {"stance": "pass", "role_key": "x"}
        self.assertIs(_unwrap_envelope(raw, "stance"), raw)

    def test_unwraps_answer_envelope(self) -> None:
        raw = {"answer": {"stance": "revise", "role_key": "copy_editor"}}
        out = _unwrap_envelope(raw, "stance", "role_key")
        self.assertEqual(out["stance"], "revise")
        self.assertEqual(out["role_key"], "copy_editor")

    def test_unwraps_common_keys(self) -> None:
        for key in ("result", "output", "data", "response", "json", "content"):
            raw = {key: {"decision": "pass", "final_scores": {}}}
            self.assertEqual(_unwrap_envelope(raw, "decision", "final_scores")["decision"], "pass")

    def test_unwraps_single_nested_dict(self) -> None:
        raw = {"weird_wrapper": {"new_substantive_objection": False}}
        self.assertFalse(_unwrap_envelope(raw, "new_substantive_objection")["new_substantive_objection"])

    def test_non_dict_returns_empty(self) -> None:
        self.assertEqual(_unwrap_envelope(None, "stance"), {})
        self.assertEqual(_unwrap_envelope("nope", "stance"), {})

    def test_returns_raw_when_no_match(self) -> None:
        raw = {"foo": 1, "bar": 2}
        self.assertIs(_unwrap_envelope(raw, "stance"), raw)


if __name__ == "__main__":
    unittest.main()
