"""Task 5: Tests for RoleSpec + 16-role EDITORIAL_ROLES + active_roles()."""
from __future__ import annotations

import unittest

from app.services.editorial_roles import EDITORIAL_ROLES, RoleSpec, active_roles

EXPECTED_KEYS = {
    "chief_editor",
    "managing_editor",
    "content_editor",
    "copy_editor",
    "proofreader",
    "fact_checker",
    "compliance",
    "legal_copyright",
    "reader_advocate",
    "headline_editor",
    "growth_editor",
    "layout_editor",
    "platform_seo",
    "topic_strategist",
    "domain_expert",
    "brand_voice",
}


class RoleSpecStructureTests(unittest.TestCase):
    def test_exactly_16_roles(self) -> None:
        self.assertEqual(len(EDITORIAL_ROLES), 16)

    def test_all_expected_keys_present(self) -> None:
        actual_keys = {r.key for r in EDITORIAL_ROLES}
        self.assertEqual(actual_keys, EXPECTED_KEYS)

    def test_unique_keys(self) -> None:
        keys = [r.key for r in EDITORIAL_ROLES]
        self.assertEqual(len(keys), len(set(keys)), "Duplicate role keys detected")

    def test_all_roles_are_rolespec_instances(self) -> None:
        for role in EDITORIAL_ROLES:
            self.assertIsInstance(role, RoleSpec)

    def test_non_empty_required_fields(self) -> None:
        for role in EDITORIAL_ROLES:
            with self.subTest(role=role.key):
                self.assertTrue(role.key.strip(), f"{role.key}: key is empty")
                self.assertTrue(role.name.strip(), f"{role.key}: name is empty")
                self.assertTrue(
                    role.department.strip(), f"{role.key}: department is empty"
                )
                self.assertTrue(
                    role.system_prompt.strip(),
                    f"{role.key}: system_prompt is empty",
                )
                self.assertTrue(role.rubric.strip(), f"{role.key}: rubric is empty")

    def test_enabled_defaults_true(self) -> None:
        for role in EDITORIAL_ROLES:
            with self.subTest(role=role.key):
                self.assertTrue(role.enabled)

    def test_weight_defaults_1(self) -> None:
        for role in EDITORIAL_ROLES:
            with self.subTest(role=role.key):
                self.assertEqual(role.weight, 1.0)

    def test_chief_editor_present(self) -> None:
        keys = {r.key for r in EDITORIAL_ROLES}
        self.assertIn("chief_editor", keys)


class ActiveRolesTests(unittest.TestCase):
    def test_active_roles_no_disabled_returns_all_16(self) -> None:
        roles = active_roles("")
        self.assertEqual(len(roles), 16)

    def test_active_roles_filters_disabled_keys(self) -> None:
        roles = active_roles("copy_editor,proofreader")
        keys = {r.key for r in roles}
        self.assertNotIn("copy_editor", keys)
        self.assertNotIn("proofreader", keys)
        self.assertEqual(len(roles), 14)

    def test_active_roles_keeps_chief_editor_even_if_disabled(self) -> None:
        roles = active_roles("chief_editor")
        keys = {r.key for r in roles}
        self.assertIn("chief_editor", keys)

    def test_active_roles_chief_editor_survives_combined_disabled(self) -> None:
        roles = active_roles("chief_editor,copy_editor,proofreader")
        keys = {r.key for r in roles}
        self.assertIn("chief_editor", keys)
        self.assertNotIn("copy_editor", keys)
        self.assertNotIn("proofreader", keys)
        self.assertEqual(len(roles), 14)

    def test_active_roles_ignores_whitespace_in_disabled(self) -> None:
        roles = active_roles(" copy_editor , proofreader ")
        keys = {r.key for r in roles}
        self.assertNotIn("copy_editor", keys)
        self.assertNotIn("proofreader", keys)

    def test_active_roles_empty_string_returns_all(self) -> None:
        roles_empty = active_roles("")
        roles_default = active_roles()
        self.assertEqual(len(roles_empty), len(roles_default))

    def test_active_roles_unknown_key_has_no_effect(self) -> None:
        roles = active_roles("nonexistent_role")
        self.assertEqual(len(roles), 16)


if __name__ == "__main__":
    unittest.main()
