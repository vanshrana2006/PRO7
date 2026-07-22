"""
Lightweight signed API tokens using stdlib hmac/hashlib -- deliberately not
a JWT library dependency, since the platform's actual auth need right now
(protect write endpoints with a server-issued token, no user login flow
yet) doesn't require JWT's claims/algorithm-negotiation surface, and a
hand-rolled HMAC scheme is small enough to fully unit-test here with zero
new dependencies.

Format: base64url(payload_json) + "." + base64url(hmac_sha256(secret, payload_b64))
This is intentionally close to a JWT's structure (header-less, HS256-only)
so migrating to PyJWT later -- e.g. once real OAuth/user accounts are
added, see GAP_ANALYSIS.md -- is a drop-in swap of this module, not a
rewrite of every call site.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


class TokenError(RuntimeError):
    pass


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def issue_token(secret: str, subject: str, ttl_seconds: int = 3600, scopes: list[str] | None = None) -> str:
    if not secret:
        raise TokenError("Cannot issue a token with an empty secret")

    payload = {
        "sub": subject,
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl_seconds,
        "scopes": scopes or [],
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64encode(payload_bytes)
    signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    signature_b64 = _b64encode(signature)
    return f"{payload_b64}.{signature_b64}"


def verify_token(secret: str, token: str, required_scope: str | None = None) -> dict:
    """Returns the decoded payload if the token is valid, unexpired, and
    (when required_scope is given) has that scope. Raises TokenError for
    every failure mode with a distinct, honest message -- never returns a
    partially-valid result."""
    if not secret:
        raise TokenError("Cannot verify a token with an empty secret")

    parts = token.split(".")
    if len(parts) != 2:
        raise TokenError("Malformed token: expected exactly one '.' separator")

    payload_b64, signature_b64 = parts
    expected_signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()

    try:
        provided_signature = _b64decode(signature_b64)
    except Exception as exc:
        raise TokenError(f"Malformed token signature: {exc}") from exc

    if not hmac.compare_digest(expected_signature, provided_signature):
        raise TokenError("Invalid token signature")

    try:
        payload = json.loads(_b64decode(payload_b64))
    except Exception as exc:
        raise TokenError(f"Malformed token payload: {exc}") from exc

    if payload.get("exp", 0) < time.time():
        raise TokenError("Token has expired")

    if required_scope is not None and required_scope not in payload.get("scopes", []):
        raise TokenError(f"Token missing required scope '{required_scope}'")

    return payload
