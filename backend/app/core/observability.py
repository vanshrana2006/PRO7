"""HTTP-layer glue between FastAPI's request/response cycle and the pure,
tested MetricsRegistry. Kept separate from metrics_registry.py so the
counting/formatting logic stays testable without spinning up FastAPI."""
from __future__ import annotations

import time

from app.core.metrics_registry import registry


async def track_request(request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start
    # Use route path template where available (e.g. "/api/papers/{paper_id}")
    # rather than the raw URL, so metrics aggregate across different ids
    # instead of creating one series per paper.
    route = request.scope.get("route")
    path = route.path if route is not None else request.url.path
    registry.record(request.method, path, response.status_code, duration)
    return response
