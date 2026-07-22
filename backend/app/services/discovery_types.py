"""Pure dataclass mirror of schemas.paper.UnifiedSearchResult. Kept
dependency-free (no pydantic import) so the normalization logic in
discovery_service.py can be unit-tested in this sandbox without installing
pydantic. The API layer (routes/papers.py) converts this into the pydantic
schema at the response boundary."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UnifiedResult:
    source: str
    source_id: str
    arxiv_id: str | None
    title: str
    abstract: str
    authors: list[str]
    year: int | None
    venue: str | None
    citation_count: int | None
    pdf_url: str | None
