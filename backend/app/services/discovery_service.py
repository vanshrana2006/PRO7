"""
Unifies discovery across arXiv and Semantic Scholar into one result shape
(UnifiedResult), so callers (API routes, DiscoveryAgent) don't need
per-source branching.

Adding another source (CrossRef, PubMed, OpenAlex, ACL Anthology -- see
GAP_ANALYSIS.md) means writing one more fetch/parse-split client following
the same pattern as arxiv_client.py/semantic_scholar_client.py, adding a
converter function to discovery_converters.py, and adding one branch here
-- not touching any caller.
"""
from __future__ import annotations

import asyncio

from app.services.arxiv_client import ArxivClient, ArxivClientError
from app.services.discovery_converters import from_arxiv, from_semantic_scholar
from app.services.discovery_types import UnifiedResult
from app.services.semantic_scholar_client import SemanticScholarClient, SemanticScholarClientError


class DiscoveryError(RuntimeError):
    pass


async def search_all_sources(
    query: str, max_results: int = 20, sources: tuple[str, ...] = ("arxiv", "semantic_scholar")
) -> list[UnifiedResult]:
    """Searches the requested sources concurrently. A single source failing
    (e.g. Semantic Scholar rate limit) does not fail the whole search --
    its results are simply omitted, since the other source(s) still return
    useful results. Only raises if every requested source fails."""
    tasks = []
    if "arxiv" in sources:
        tasks.append(("arxiv", ArxivClient().search(query, max_results=max_results)))
    if "semantic_scholar" in sources:
        tasks.append(("semantic_scholar", SemanticScholarClient().search(query, limit=max_results)))

    results: list[UnifiedResult] = []
    errors: list[str] = []

    outcomes = await asyncio.gather(*(t[1] for t in tasks), return_exceptions=True)
    for (source_name, _), outcome in zip(tasks, outcomes):
        if isinstance(outcome, (ArxivClientError, SemanticScholarClientError)):
            errors.append(f"{source_name}: {outcome}")
            continue
        if isinstance(outcome, Exception):
            errors.append(f"{source_name}: {outcome}")
            continue
        converter = from_arxiv if source_name == "arxiv" else from_semantic_scholar
        results.extend(converter(e) for e in outcome)

    if not results and errors:
        raise DiscoveryError("; ".join(errors))

    return results
