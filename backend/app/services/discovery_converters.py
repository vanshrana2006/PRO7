"""Pure conversion functions from source-specific entry types to the
unified, dependency-free UnifiedResult shape. No httpx/pydantic imports,
so this is testable offline even though the network clients it converts
output from are not."""
from __future__ import annotations

from app.services.arxiv_parser import ArxivEntry
from app.services.discovery_types import UnifiedResult
from app.services.semantic_scholar_parser import SemanticScholarEntry


def from_arxiv(entry: ArxivEntry) -> UnifiedResult:
    return UnifiedResult(
        source="arxiv",
        source_id=entry.arxiv_id,
        arxiv_id=entry.arxiv_id,
        title=entry.title,
        abstract=entry.abstract,
        authors=entry.authors,
        year=entry.published_at.year if entry.published_at else None,
        venue=None,
        citation_count=None,
        pdf_url=entry.pdf_url,
    )


def from_semantic_scholar(entry: SemanticScholarEntry) -> UnifiedResult:
    return UnifiedResult(
        source="semantic_scholar",
        source_id=entry.paper_id,
        arxiv_id=entry.arxiv_id,
        title=entry.title,
        abstract=entry.abstract,
        authors=entry.authors,
        year=entry.year,
        venue=entry.venue,
        citation_count=entry.citation_count,
        pdf_url=entry.pdf_url,
    )
