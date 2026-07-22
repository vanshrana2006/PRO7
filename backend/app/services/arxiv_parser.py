"""
Pure parsing logic for arXiv's Atom XML search responses.

Deliberately has ZERO third-party imports (stdlib xml.etree only) so it can
be unit-tested in any Python environment without installing httpx/pydantic/
fastapi -- including this sandbox. The network-fetching wrapper that uses
httpx lives in arxiv_client.py and imports this module.
"""
from __future__ import annotations

import datetime as dt
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


class ArxivParseError(RuntimeError):
    pass


@dataclass
class ArxivEntry:
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    published_at: dt.datetime | None
    updated_at: dt.datetime | None
    primary_category: str | None
    categories: list[str] = field(default_factory=list)
    pdf_url: str | None = None


def _clean_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _parse_datetime(text: str | None) -> dt.datetime | None:
    if not text:
        return None
    try:
        return dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _extract_arxiv_id(entry_id_url: str) -> str:
    """arXiv <id> looks like http://arxiv.org/abs/2301.12345v2 -- normalize
    to the bare id including version, e.g. '2301.12345v2'."""
    return entry_id_url.rstrip("/").split("/abs/")[-1]


def parse_atom_feed(xml_text: str) -> list[ArxivEntry]:
    """Parse arXiv's Atom XML search response into ArxivEntry objects.

    Raises ArxivParseError on malformed XML rather than failing silently --
    a Phase 1 principle: never swallow extraction errors, surface them so the
    caller can mark the ingest as failed with a real reason.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ArxivParseError(f"Malformed Atom XML from arXiv: {exc}") from exc

    entries: list[ArxivEntry] = []
    for entry_el in root.findall(f"{ATOM_NS}entry"):
        entry_id_el = entry_el.find(f"{ATOM_NS}id")
        if entry_id_el is None or not entry_id_el.text:
            continue
        arxiv_id = _extract_arxiv_id(entry_id_el.text.strip())

        title = _clean_text(entry_el.findtext(f"{ATOM_NS}title"))
        abstract = _clean_text(entry_el.findtext(f"{ATOM_NS}summary"))

        authors = [
            _clean_text(a.findtext(f"{ATOM_NS}name"))
            for a in entry_el.findall(f"{ATOM_NS}author")
            if a.findtext(f"{ATOM_NS}name")
        ]

        published_at = _parse_datetime(entry_el.findtext(f"{ATOM_NS}published"))
        updated_at = _parse_datetime(entry_el.findtext(f"{ATOM_NS}updated"))

        primary_category = None
        primary_cat_el = entry_el.find(f"{ARXIV_NS}primary_category")
        if primary_cat_el is not None:
            primary_category = primary_cat_el.get("term")

        categories = [
            c.get("term")
            for c in entry_el.findall(f"{ATOM_NS}category")
            if c.get("term")
        ]

        pdf_url = None
        for link_el in entry_el.findall(f"{ATOM_NS}link"):
            if link_el.get("title") == "pdf" or link_el.get("type") == "application/pdf":
                pdf_url = link_el.get("href")
                break
        if pdf_url is None:
            # Fallback: derive from abs URL convention.
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

        entries.append(
            ArxivEntry(
                arxiv_id=arxiv_id,
                title=title,
                abstract=abstract,
                authors=authors,
                published_at=published_at,
                updated_at=updated_at,
                primary_category=primary_category,
                categories=categories,
                pdf_url=pdf_url,
            )
        )
    return entries
