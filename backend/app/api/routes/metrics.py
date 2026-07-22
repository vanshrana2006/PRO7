from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.core.metrics_registry import registry

router = APIRouter(tags=["observability"])


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """Prometheus scrape target. Point a Prometheus `scrape_configs` entry
    at this path; see docs/DEPLOYMENT.md for a sample config."""
    return registry.render_prometheus()
