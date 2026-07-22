"""
PDF intelligence: extracts structure from a research paper PDF rather than
treating it as a flat text blob.

Two layers, on purpose:

  1. `extract_pages_text`     -- low-level, per-page text via pdfplumber.
  2. `segment_into_sections`  -- heuristic layout understanding: detects
     section headings (Abstract, Introduction, Related Work, Methodology,
     Experiments, Results, Discussion, Limitations, Future Work, Conclusion,
     References) from font/line patterns and groups text under them.
  3. `extract_references`     -- splits the References section into
     individual bibliography entries.

This heuristic layer runs today with zero API keys. Phase 2 adds an
LLM-backed refinement pass (behind the same interface) for papers whose
layout doesn't match the common patterns -- but heuristics-first means the
platform is never dead in the water without a key, exactly per the
"no feature requires credentials to run degraded" architecture principle.

Fully unit-tested offline in tests/test_pdf_extractor.py using a real PDF
generated on the fly with pypdf (no network, no fixtures needed).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pdfplumber

# Canonical section types we try to recognize, in typical paper order.
SECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("abstract", re.compile(r"^\s*abstract\s*$", re.IGNORECASE)),
    ("introduction", re.compile(r"^\s*(\d+\.?\s*)?introduction\s*$", re.IGNORECASE)),
    ("related_work", re.compile(r"^\s*(\d+\.?\s*)?(related work|background|prior work)\s*$", re.IGNORECASE)),
    ("methodology", re.compile(r"^\s*(\d+\.?\s*)?(method(ology)?|approach|proposed method|model)\s*$", re.IGNORECASE)),
    ("experiments", re.compile(r"^\s*(\d+\.?\s*)?(experiments?|experimental setup|evaluation)\s*$", re.IGNORECASE)),
    ("results", re.compile(r"^\s*(\d+\.?\s*)?results?\s*$", re.IGNORECASE)),
    ("discussion", re.compile(r"^\s*(\d+\.?\s*)?discussion\s*$", re.IGNORECASE)),
    ("limitations", re.compile(r"^\s*(\d+\.?\s*)?limitations?\s*$", re.IGNORECASE)),
    ("future_work", re.compile(r"^\s*(\d+\.?\s*)?future work\s*$", re.IGNORECASE)),
    ("conclusion", re.compile(r"^\s*(\d+\.?\s*)?conclusions?\s*$", re.IGNORECASE)),
    ("acknowledgments", re.compile(r"^\s*acknowledg(e)?ments?\s*$", re.IGNORECASE)),
    ("references", re.compile(r"^\s*(references|bibliography)\s*$", re.IGNORECASE)),
    ("appendix", re.compile(r"^\s*(\d+\.?\s*)?appendix\s*", re.IGNORECASE)),
]


class PDFExtractionError(RuntimeError):
    pass


@dataclass
class ExtractedSection:
    heading: str
    section_type: str
    order_index: int
    content: str
    page_start: int | None = None
    page_end: int | None = None


@dataclass
class ExtractedReference:
    raw_text: str
    order_index: int
    parsed_title: str | None = None
    parsed_year: int | None = None
    parsed_authors: str | None = None


@dataclass
class ExtractionResult:
    full_text: str
    num_pages: int
    sections: list[ExtractedSection] = field(default_factory=list)
    references: list[ExtractedReference] = field(default_factory=list)


def extract_pages_text(pdf_path: str) -> list[str]:
    """Extract raw text per page. Raises PDFExtractionError on unreadable
    files instead of returning empty/garbage text silently."""
    try:
        pages: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return pages
    except Exception as exc:  # pdfplumber raises various underlying errors
        raise PDFExtractionError(f"Failed to read PDF at {pdf_path}: {exc}") from exc


def _classify_line(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return None
    for section_type, pattern in SECTION_PATTERNS:
        if pattern.match(stripped):
            return section_type
    return None


def segment_into_sections(pages: list[str]) -> list[ExtractedSection]:
    """Heuristically split page text into sections by detecting heading-like
    lines (short lines matching known section-name patterns)."""
    sections: list[ExtractedSection] = []
    current_heading = "Preamble"
    current_type = "body"
    current_content: list[str] = []
    current_page_start = 0 if pages else None
    order = 0

    def flush(end_page: int) -> None:
        nonlocal order
        content = "\n".join(current_content).strip()
        if content:
            sections.append(
                ExtractedSection(
                    heading=current_heading,
                    section_type=current_type,
                    order_index=order,
                    content=content,
                    page_start=current_page_start,
                    page_end=end_page,
                )
            )
            order += 1

    for page_idx, page_text in enumerate(pages):
        for line in page_text.splitlines():
            section_type = _classify_line(line)
            if section_type is not None:
                flush(page_idx)
                current_heading = line.strip()
                current_type = section_type
                current_content = []
                current_page_start = page_idx
            else:
                current_content.append(line)

    flush(len(pages) - 1 if pages else 0)
    return sections


_REF_SPLIT_PATTERN = re.compile(r"(?:^|\n)\s*(?:\[\d+\]|\d{1,3}\.)\s+")
_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def extract_references(sections: list[ExtractedSection]) -> list[ExtractedReference]:
    """Find the References/Bibliography section and split it into individual
    entries using common numbering conventions ('[12] ...' or '12. ...')."""
    ref_section = next((s for s in sections if s.section_type == "references"), None)
    if ref_section is None:
        return []

    raw = ref_section.content
    parts = _REF_SPLIT_PATTERN.split(raw)
    parts = [p.strip() for p in parts if p.strip()]

    references: list[ExtractedReference] = []
    for idx, part in enumerate(parts):
        year_match = _YEAR_PATTERN.search(part)
        year = int(year_match.group(0)) if year_match else None
        # Heuristic: title is usually the text up to the first period after
        # the author list, but without an LLM pass we keep this best-effort
        # and conservative -- better to leave parsed_title as None than to
        # confidently extract garbage.
        references.append(
            ExtractedReference(
                raw_text=part,
                order_index=idx,
                parsed_year=year,
            )
        )
    return references


def extract_pdf(pdf_path: str) -> ExtractionResult:
    """Full Phase 1 extraction pipeline for a single PDF file on disk."""
    pages = extract_pages_text(pdf_path)
    full_text = "\n\n".join(pages)
    sections = segment_into_sections(pages)
    references = extract_references(sections)
    return ExtractionResult(
        full_text=full_text,
        num_pages=len(pages),
        sections=sections,
        references=references,
    )
