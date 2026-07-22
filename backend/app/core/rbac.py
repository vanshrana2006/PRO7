"""
Role-Based Access Control, layered on the HMAC token scopes already issued
by app/core/auth.py -- roles are just named, reusable sets of scopes, so
`scripts/issue_token.py --role researcher` expands to the concrete scope
list below instead of operators needing to memorize/type every scope.

Kept as pure logic (no FastAPI/Starlette imports) so it's fully testable
offline; app/core/middleware.py wires `require_role()` into route
dependencies the same way it already wires `require_auth()`.
"""
from __future__ import annotations

# Every permission the platform currently gates. Adding a new protected
# endpoint means adding one string here and referencing it in that route's
# dependency -- roles below just group these into reusable sets.
PERMISSIONS = frozenset(
    {
        "papers:ingest",
        "knowledge:extract",
        "research:run",
        "admin:issue_tokens",
    }
)

ROLES: dict[str, frozenset[str]] = {
    # Read-only: can query everything (no auth required for reads at all
    # today -- see middleware.py), never mutates.
    "viewer": frozenset(),
    # Normal day-to-day platform use.
    "researcher": frozenset({"papers:ingest", "knowledge:extract", "research:run"}),
    # Full access, including minting tokens for other users.
    "admin": PERMISSIONS,
}


class RBACError(RuntimeError):
    pass


def scopes_for_role(role: str) -> list[str]:
    """Expands a role name into its concrete scope list, for
    scripts/issue_token.py to pass to issue_token(). Raises RBACError for
    an unknown role rather than silently granting zero or all permissions
    -- an unrecognized role name is a configuration mistake that should
    fail loudly, not fail open or fail closed by accident."""
    if role not in ROLES:
        raise RBACError(f"Unknown role '{role}'. Valid roles: {sorted(ROLES)}")
    return sorted(ROLES[role])


def has_permission(granted_scopes: list[str] | set[str], required_permission: str) -> bool:
    """Checks whether a token's granted scopes include the required
    permission. A permission not in PERMISSIONS is a caller bug (a typo'd
    permission string that could never be satisfied) -- raised loudly
    rather than silently always returning False, which would look
    identical to "correctly denied" in logs and hide the real bug."""
    if required_permission not in PERMISSIONS:
        raise RBACError(f"'{required_permission}' is not a recognized permission")
    return required_permission in set(granted_scopes)
