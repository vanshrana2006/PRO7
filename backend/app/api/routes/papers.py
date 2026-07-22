from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.paper import Paper
from app.schemas.paper import (
    ArxivSearchResult,
    CorpusSearchResponse,
    CorpusSearchResultOut,
    IngestRequest,
    IngestResponse,
    PaperDetail,
    PaperSummary,
    UnifiedSearchResult,
)
from app.services.arxiv_client import ArxivClient, ArxivClientError
from app.services.corpus_search import search_corpus
from app.services.discovery_service import DiscoveryError, search_all_sources
from app.services.ingest_service import IngestError, ingest_arxiv_paper
from app.core.middleware import require_permission

router = APIRouter(prefix="/api/papers", tags=["papers"])


@router.get("/search", response_model=list[ArxivSearchResult])
async def search_arxiv(
    q: str = Query(..., min_length=1, description="Free-text search query"),
    max_results: int = Query(20, ge=1, le=100),
):
    """Search arXiv directly (does not touch the local DB). Kept as a
    single-source endpoint for backward compatibility; new integrations
    should prefer GET /api/papers/discover, which searches every connected
    source at once."""
    client = ArxivClient()
    try:
        entries = await client.search(q, max_results=max_results)
    except ArxivClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return [
        ArxivSearchResult(
            arxiv_id=e.arxiv_id,
            title=e.title,
            abstract=e.abstract,
            authors=e.authors,
            published_at=e.published_at,
            updated_at=e.updated_at,
            primary_category=e.primary_category,
            categories=e.categories,
            pdf_url=e.pdf_url,
        )
        for e in entries
    ]


@router.get("/discover", response_model=list[UnifiedSearchResult])
async def discover(
    q: str = Query(..., min_length=1),
    max_results: int = Query(20, ge=1, le=100),
    sources: str = Query("arxiv,semantic_scholar", description="Comma-separated: arxiv, semantic_scholar"),
):
    """Searches every requested discovery source concurrently and returns
    normalized results. A source failing (e.g. a rate limit) doesn't fail
    the whole request as long as at least one source returns results."""
    source_tuple = tuple(s.strip() for s in sources.split(",") if s.strip())
    try:
        results = await search_all_sources(q, max_results=max_results, sources=source_tuple)
    except DiscoveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return [UnifiedSearchResult(**vars(r)) for r in results]


@router.post("/ingest", response_model=IngestResponse)
async def ingest_paper(
    req: IngestRequest, db: AsyncSession = Depends(get_db), _auth: dict = Depends(require_permission("papers:ingest"))
):
    """Pull a paper into the platform: fetch metadata, download the PDF,
    extract structure, and persist it. Synchronous in Phase 1 for
    simplicity/testability; Phase 3 moves this to a background task queue
    so large batches don't block the request."""
    try:
        paper = await ingest_arxiv_paper(db, req.arxiv_id)
    except IngestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if paper.extraction_status == "failed":
        return IngestResponse(
            paper_id=paper.id,
            status="failed",
            message=paper.extraction_error or "Unknown error during ingest",
        )
    return IngestResponse(
        paper_id=paper.id,
        status=paper.extraction_status,
        message="Ingest completed successfully",
    )


@router.get("", response_model=list[PaperSummary])
async def list_papers(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    result = await db.execute(
        select(Paper)
        .options(selectinload(Paper.authors))
        .order_by(Paper.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/corpus-search", response_model=CorpusSearchResponse)
async def corpus_search(
    q: str = Query(..., min_length=1, description="Free-text query"),
    top_k: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """BM25 sparse retrieval over every ingested paper's title/abstract/full
    text -- see services/retrieval.py. Distinct from GET /search and
    /discover, which query external sources; this searches what's already
    in your local corpus."""
    results = await search_corpus(db, q, top_k=top_k)
    return CorpusSearchResponse(
        query=q,
        results=[CorpusSearchResultOut(paper_id=p.id, title=p.title, score=score) for p, score in results],
    )


@router.get("/{paper_id}", response_model=PaperDetail)
async def get_paper(paper_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Paper)
        .options(
            selectinload(Paper.authors),
            selectinload(Paper.sections),
            selectinload(Paper.references),
        )
        .where(Paper.id == paper_id)
    )
    paper = result.scalar_one_or_none()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper
