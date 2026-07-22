"""
Wires the pure, tested rate_limiter.py, auth.py, and rbac.py modules into
FastAPI: a global rate-limiting middleware, and per-route auth/permission
dependencies for mutating endpoints.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.auth import TokenError, verify_token
from app.core.config import get_settings
from app.core.rate_limiter import TokenBucketLimiter
from app.core.rbac import RBACError, has_permission

settings = get_settings()

_limiter = TokenBucketLimiter(
    capacity=settings.RATE_LIMIT_CAPACITY,
    refill_per_second=settings.RATE_LIMIT_REFILL_PER_SECOND,
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client-IP token bucket. Returns 429 with a Retry-After hint
    rather than silently dropping or queuing requests. /api/health is
    exempt so load balancer health checks are never throttled."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/api/health":
            return await call_next(request)

        client_key = request.client.host if request.client else "unknown"
        if not _limiter.allow(client_key):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please slow down and try again shortly."},
                headers={"Retry-After": "1"},
            )
        return await call_next(request)


def _verify_bearer_token(authorization: str | None) -> dict:
    """Shared token-verification logic for require_auth/require_permission
    below. Returns {} (no-op) when REQUIRE_API_AUTH is False, which is the
    default -- so this platform runs fully functional out of the box, and
    operators opt into requiring tokens once they've distributed one (see
    scripts/issue_token.py) rather than being locked out by default."""
    if not settings.REQUIRE_API_AUTH:
        return {}

    if not settings.API_AUTH_SECRET:
        raise HTTPException(
            status_code=500,
            detail="REQUIRE_API_AUTH is enabled but API_AUTH_SECRET is not configured",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        return verify_token(settings.API_AUTH_SECRET, token)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def require_auth(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: any validly-signed, unexpired token (no specific
    permission required). No-op when REQUIRE_API_AUTH is False."""
    return _verify_bearer_token(authorization)


def require_permission(permission: str):
    """FastAPI dependency FACTORY: returns a dependency that requires a
    valid token AND that the token's scopes grant `permission` (see
    rbac.py). Use per-route: `Depends(require_permission("papers:ingest"))`.
    Still a no-op when REQUIRE_API_AUTH is False, consistent with
    require_auth -- RBAC only activates once auth itself is turned on.
    """

    async def _dependency(authorization: str | None = Header(default=None)) -> dict:
        payload = _verify_bearer_token(authorization)
        if not settings.REQUIRE_API_AUTH:
            return payload

        try:
            allowed = has_permission(payload.get("scopes", []), permission)
        except RBACError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        if not allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Token does not have the required '{permission}' permission",
            )
        return payload

    return _dependency
