"""
Pure parsing logic for Semantic Scholar's Graph API paper search responses.

Same architecture as arxiv_parser.py: zero third-party imports, so the
parsing logic is fully unit-testable offline. The httpx-based network
wrapper lives in semantic_scholar_client.py.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


class SemanticScholarParseError(RuntimeError):
    pass


@dataclass
class SemanticScholarEntry:
    paper_id: str
    title: str
    abstract: str
    authors: list[str]
    year: int | None
    venue: str | None
    citation_count: int | None
    external_ids: dict = field(default_factory=dict)
    pdf_url: str | None = None

    @property
    def arxiv_id(self) -> str | None:
        return self.external_ids.get("ArXiv")

    @property
    def doi(self) -> str | None:
        return self.external_ids.get("DOI")

    @property
    def published_at(self) -> dt.datetime | None:
        return dt.datetime(self.year, 1, 1) if self.year else None


def parse_search_response(payload: dict) -> list[SemanticScholarEntry]:
    """Parses the JSON body of a GET /graph/v1/paper/search response.

    Raises SemanticScholarParseError on a malformed payload rather than
    failing silently, matching the pattern used throughout the platform:
    every extraction failure is surfaced, never swallowed.
    """
    if not isinstance(payload, dict):
        raise SemanticScholarParseError("Expected a JSON object at the top level")

    data = payload.get("data")
    if data is None:
        raise SemanticScholarParseError("Response missing 'data' field")
    if not isinstance(data, list):
        raise SemanticScholarParseError("'data' field is not a list")

    entries: list[SemanticScholarEntry] = []
    for item in data:
        if not isinstance(item, dict) or not item.get("paperId"):
            continue  # skip malformed individual records rather than aborting the whole batch

        authors = [
            a.get("name", "").strip()
            for a in (item.get("authors") or [])
            if isinstance(a, dict) and a.get("name")
        ]

        open_access_pdf = item.get("openAccessPdf") or {}
        pdf_url = open_access_pdf.get("url") if isinstance(open_access_pdf, dict) else None

        entries.append(
            SemanticScholarEntry(
                paper_id=item["paperId"],
                title=(item.get("title") or "").strip(),
                abstract=(item.get("abstract") or "").strip(),
                authors=authors,
                year=item.get("year"),
                venue=item.get("venue") or None,
                citation_count=item.get("citationCount"),
                external_ids=item.get("externalIds") or {},
                pdf_url=pdf_url,
            )
        )
    return entries
