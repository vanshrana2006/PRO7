"""
Offline tests for the RBAC role/scope/permission logic.

Run with:  python3 -m unittest tests.test_rbac -v
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.core.rbac import RBACError, has_permission, scopes_for_role  # noqa: E402


class TestScopesForRole(unittest.TestCase):
    def test_viewer_has_no_scopes(self):
        self.assertEqual(scopes_for_role("viewer"), [])

    def test_researcher_has_expected_scopes(self):
        scopes = scopes_for_role("researcher")
        self.assertIn("papers:ingest", scopes)
        self.assertIn("knowledge:extract", scopes)
        self.assertIn("research:run", scopes)
        self.assertNotIn("admin:issue_tokens", scopes)

    def test_admin_has_every_permission(self):
        from app.core.rbac import PERMISSIONS

        self.assertEqual(set(scopes_for_role("admin")), PERMISSIONS)

    def test_unknown_role_raises_loudly(self):
        with self.assertRaises(RBACError):
            scopes_for_role("superuser")

    def test_result_is_sorted_for_deterministic_output(self):
        scopes = scopes_for_role("researcher")
        self.assertEqual(scopes, sorted(scopes))


class TestHasPermission(unittest.TestCase):
    def test_granted_scope_allows_permission(self):
        self.assertTrue(has_permission(["papers:ingest"], "papers:ingest"))

    def test_missing_scope_denies_permission(self):
        self.assertFalse(has_permission(["papers:ingest"], "admin:issue_tokens"))

    def test_empty_scopes_denies_everything(self):
        self.assertFalse(has_permission([], "papers:ingest"))

    def test_accepts_set_as_well_as_list(self):
        self.assertTrue(has_permission({"research:run"}, "research:run"))

    def test_unrecognized_permission_raises_rather_than_silently_denying(self):
        with self.assertRaises(RBACError):
            has_permission(["papers:ingest"], "papers:delete_everything")

    def test_extra_unrelated_scopes_dont_grant_unrequested_permission(self):
        self.assertFalse(has_permission(["papers:ingest", "research:run"], "admin:issue_tokens"))


if __name__ == "__main__":
    unittest.main()
