"""
Offline tests for the HMAC-signed token module.

Run with:  python3 -m unittest tests.test_auth -v
"""
import pathlib
import sys
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.core.auth import TokenError, issue_token, verify_token  # noqa: E402

SECRET = "test-secret-do-not-use-in-production"


class TestIssueAndVerifyToken(unittest.TestCase):
    def test_issued_token_verifies_successfully(self):
        token = issue_token(SECRET, subject="test-client", ttl_seconds=3600)
        payload = verify_token(SECRET, token)
        self.assertEqual(payload["sub"], "test-client")

    def test_token_has_two_dot_separated_parts(self):
        token = issue_token(SECRET, subject="x")
        self.assertEqual(len(token.split(".")), 2)

    def test_wrong_secret_fails_verification(self):
        token = issue_token(SECRET, subject="x")
        with self.assertRaises(TokenError):
            verify_token("a-different-secret", token)

    def test_tampered_payload_fails_verification(self):
        token = issue_token(SECRET, subject="x")
        payload_b64, sig_b64 = token.split(".")
        tampered = payload_b64 + "TAMPERED" + "." + sig_b64
        with self.assertRaises(TokenError):
            verify_token(SECRET, tampered)

    def test_malformed_token_missing_separator_fails(self):
        with self.assertRaises(TokenError):
            verify_token(SECRET, "not-a-valid-token-at-all")

    def test_expired_token_fails_verification(self):
        token = issue_token(SECRET, subject="x", ttl_seconds=-10)  # already expired
        with self.assertRaises(TokenError):
            verify_token(SECRET, token)

    def test_scopes_round_trip(self):
        token = issue_token(SECRET, subject="x", scopes=["write:papers", "read:graph"])
        payload = verify_token(SECRET, token)
        self.assertEqual(set(payload["scopes"]), {"write:papers", "read:graph"})

    def test_required_scope_present_passes(self):
        token = issue_token(SECRET, subject="x", scopes=["write:papers"])
        payload = verify_token(SECRET, token, required_scope="write:papers")
        self.assertEqual(payload["sub"], "x")

    def test_required_scope_missing_fails(self):
        token = issue_token(SECRET, subject="x", scopes=["read:graph"])
        with self.assertRaises(TokenError):
            verify_token(SECRET, token, required_scope="write:papers")

    def test_empty_secret_rejected_on_issue(self):
        with self.assertRaises(TokenError):
            issue_token("", subject="x")

    def test_empty_secret_rejected_on_verify(self):
        token = issue_token(SECRET, subject="x")
        with self.assertRaises(TokenError):
            verify_token("", token)

    def test_iat_is_recent(self):
        before = int(time.time())
        token = issue_token(SECRET, subject="x")
        payload = verify_token(SECRET, token)
        self.assertGreaterEqual(payload["iat"], before)
        self.assertLessEqual(payload["iat"], before + 2)


if __name__ == "__main__":
    unittest.main()
