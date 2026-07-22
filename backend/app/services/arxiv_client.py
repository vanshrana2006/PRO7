"""
arXiv search client -- the httpx-based network layer.

Fetches raw Atom XML from the live arXiv API and delegates parsing to the
dependency-free `arxiv_parser.parse_atom_feed`. This module requires
network access + httpx installed; it is verified with a live smoke test
(see README "Verifying Phase 1 live") rather than in this offline sandbox.
"""
from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.services.arxiv_parser import ArxivEntry, ArxivParseError, parse_atom_feed

__all__ = ["ArxivClient", "ArxivClientError", "ArxivEntry"]


class ArxivClientError(RuntimeError):
    pass


class ArxivClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(
        self,
        query: str,
        max_results: int | None = None,
        start: int = 0,
        sort_by: str = "relevance",
    ) -> list[ArxivEntry]:
        params = {
            "search_query": f"all:{query}",
            "start": start,
            "max_results": max_results or self.settings.ARXIV_MAX_RESULTS_DEFAULT,
            "sortBy": sort_by,
            "sortOrder": "descending",
        }
        async with httpx.AsyncClient(
            timeout=self.settings.ARXIV_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            try:
                resp = await client.get(self.settings.ARXIV_API_BASE, params=params)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ArxivClientError(f"arXiv API request failed: {exc}") from exc

        try:
            return parse_atom_feed(resp.text)
        except ArxivParseError as exc:
            raise ArxivClientError(str(exc)) from exc

    async def get_by_id(self, arxiv_id: str) -> ArxivEntry | None:
        params = {"id_list": arxiv_id, "max_results": 1}
        async with httpx.AsyncClient(
            timeout=self.settings.ARXIV_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            try:
                resp = await client.get(self.settings.ARXIV_API_BASE, params=params)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ArxivClientError(f"arXiv API request failed: {exc}") from exc

        try:
            entries = parse_atom_feed(resp.text)
        except ArxivParseError as exc:
            raise ArxivClientError(str(exc)) from exc
        return entries[0] if entries else None
