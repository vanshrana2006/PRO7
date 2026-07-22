from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.middleware import require_permission
from app.models.paper import Paper
from app.schemas.knowledge import ExtractResponse, GraphResponse
from app.services.graph_service import extract_and_persist_for_paper, get_graph_for_paper

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/extract/{paper_id}", response_model=ExtractResponse)
async def extract_knowledge(
    paper_id: str, db: AsyncSession = Depends(get_db), _auth: dict = Depends(require_permission("knowledge:extract"))
):
    """Extracts methods/datasets/metrics/claims from an already-ingested
    paper and merges them into the knowledge graph. Uses the LLM path if
    ANTHROPIC_API_KEY is set, heuristics otherwise -- see graph_service.py."""
    result = await db.execute(
        select(Paper)
        .options(selectinload(Paper.sections), selectinload(Paper.references))
        .where(Paper.id == paper_id)
    )
    paper = result.scalar_one_or_none()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    if paper.extraction_status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Paper has not finished PDF extraction yet (status: {paper.extraction_status})",
        )

    entities, relationships, method_used, _cited_titles = await extract_and_persist_for_paper(db, paper)
    return ExtractResponse(
        paper_id=paper_id,
        method_used=method_used,
        entities_created=len(entities),
        relationships_created=len(relationships),
    )


@router.get("/graph/{paper_id}", response_model=GraphResponse)
async def graph_for_paper(paper_id: str, db: AsyncSession = Depends(get_db)):
    graph = await get_graph_for_paper(db, paper_id)
    return graph
