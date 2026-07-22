from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class AuthorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    affiliation: str | None = None


class PaperSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    heading: str
    section_type: str
    order_index: int
    page_start: int | None = None
    page_end: int | None = None
    content: str


class PaperReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    raw_text: str
    parsed_title: str | None = None
    parsed_year: int | None = None
    parsed_authors: str | None = None


class PaperSummary(BaseModel):
    """Lightweight representation used in search/list results."""

    model_config = ConfigDict(from_attributes=True)
    id: str
    arxiv_id: str | None = None
    title: str
    abstract: str | None = None
    authors: list[AuthorOut] = []
    published_at: dt.datetime | None = None
    primary_category: str | None = None
    pdf_url: str | None = None
    extraction_status: str


class PaperDetail(PaperSummary):
    """Full representation including extracted structure."""

    full_text: str | None = None
    num_pages: int | None = None
    sections: list[PaperSectionOut] = []
    references: list[PaperReferenceOut] = []
    extraction_error: str | None = None


class ArxivSearchResult(BaseModel):
    """A raw search hit from arXiv, before it has been ingested into the DB."""

    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    published_at: dt.datetime | None
    updated_at: dt.datetime | None
    primary_category: str | None
    categories: list[str]
    pdf_url: str | None


class UnifiedSearchResult(BaseModel):
    """Pydantic mirror of services.discovery_types.UnifiedResult, used at
    the API boundary. See that module for why the split exists."""

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


class IngestRequest(BaseModel):
    arxiv_id: str


class IngestResponse(BaseModel):
    paper_id: str
    status: str
    message: str


class CorpusSearchResultOut(BaseModel):
    paper_id: str
    title: str
    score: float


class CorpusSearchResponse(BaseModel):
    query: str
    results: list[CorpusSearchResultOut]
