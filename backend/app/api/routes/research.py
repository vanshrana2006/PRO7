from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.research_pipeline import run_research_pipeline, run_research_pipeline_streaming
from app.core.database import get_db
from app.core.middleware import require_permission
from app.schemas.research import ResearchRunRequest, ResearchRunResponse

router = APIRouter(prefix="/api/research", tags=["research"])


@router.post("/run", response_model=ResearchRunResponse)
async def run_research(
    req: ResearchRunRequest, db: AsyncSession = Depends(get_db), _auth: dict = Depends(require_permission("research:run"))
):
    """The one-command autonomous research workflow: discovers papers on
    arXiv for `query`, ingests and extracts each, and produces a literature
    review. Returns the complete result in one response; for real-time
    per-agent progress instead, use GET /api/research/run/stream."""
    result = await run_research_pipeline(db, req.query, max_papers=req.max_papers)
    return result


@router.get("/run/stream")
async def run_research_stream(
    query: str = Query(..., min_length=1),
    max_papers: int = Query(5, ge=1, le=15),
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_permission("research:run")),
):
    """Server-Sent Events version of the research pipeline: streams one
    `progress` event per agent as it finishes (so the UI can show live
    status -- "Discovery Agent: found 5 papers" -- instead of a blank
    spinner for the whole multi-minute run), then a final `result` event
    with the complete payload (same shape as POST /api/research/run).

    A GET endpoint (not POST) because the browser's native EventSource API
    -- the standard way to consume SSE -- only supports GET and can't send
    a request body or custom headers. This means if REQUIRE_API_AUTH is
    enabled, a plain `new EventSource(url)` in the browser can't attach the
    Bearer token; consuming this endpoint with auth enabled requires an
    SSE client that supports custom headers (e.g. fetch + a streaming body
    reader) rather than the native EventSource object. Documented here
    rather than silently broken -- auth is off by default, so this only
    matters once an operator opts into REQUIRE_API_AUTH.

    Each event is formatted as standard SSE: `data: <json>\\n\\n`.
    """

    async def event_stream():
        async for event in run_research_pipeline_streaming(db, query, max_papers=max_papers):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering so events flush immediately
        },
    )
