"""Semantic Scholar Graph API client -- httpx network layer over the tested
pure parser in semantic_scholar_parser.py. Free tier works keyless at a
lower rate limit; set SEMANTIC_SCHOLAR_API_KEY to raise it."""
from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.services.semantic_scholar_parser import (
    SemanticScholarEntry,
    SemanticScholarParseError,
    parse_search_response,
)

__all__ = ["SemanticScholarClient", "SemanticScholarClientError", "SemanticScholarEntry"]

FIELDS = "paperId,title,abstract,year,venue,citationCount,authors,externalIds,openAccessPdf"


class SemanticScholarClientError(RuntimeError):
    pass


class SemanticScholarClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(self, query: str, limit: int = 20) -> list[SemanticScholarEntry]:
        headers = {}
        if self.settings.SEMANTIC_SCHOLAR_API_KEY:
            headers["x-api-key"] = self.settings.SEMANTIC_SCHOLAR_API_KEY

        params = {"query": query, "limit": limit, "fields": FIELDS}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    self.settings.SEMANTIC_SCHOLAR_API_BASE, params=params, headers=headers
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise SemanticScholarClientError(f"Semantic Scholar request failed: {exc}") from exc

        try:
            return parse_search_response(resp.json())
        except SemanticScholarParseError as exc:
            raise SemanticScholarClientError(str(exc)) from exc
