"""Builds a BM25Index from ingested papers' full text on demand and
searches it. Rebuild-per-request is fine at this platform's realistic
scale (see retrieval.py's docstring); if corpus size grows enough to make
that slow, this is the seam to add caching/incremental indexing behind,
without changing the search() call signature."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.services.retrieval import BM25Index, ScoredDocument


async def search_corpus(db: AsyncSession, query: str, top_k: int = 10) -> list[tuple[Paper, float]]:
    """Full-text search over every successfully-extracted paper's title +
    abstract + full text. Returns (Paper, score) pairs, highest first."""
    result = await db.execute(
        select(Paper).where(Paper.extraction_status == "completed")
    )
    papers = result.scalars().all()
    if not papers:
        return []

    documents = {
        p.id: " ".join(filter(None, [p.title, p.abstract, p.full_text]))
        for p in papers
    }

    index = BM25Index()
    index.build(documents)
    scored: list[ScoredDocument] = index.search(query, top_k=top_k)

    papers_by_id = {p.id: p for p in papers}
    return [(papers_by_id[s.doc_id], s.score) for s in scored if s.doc_id in papers_by_id]
