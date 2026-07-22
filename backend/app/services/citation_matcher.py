"""
Pure logic for resolving a paper's extracted references against the corpus
of already-ingested papers, to build real `cites` edges in the knowledge
graph -- not just isolated per-paper reference text.

Matching is deliberately conservative (normalized exact-ish title match,
not fuzzy/embedding similarity) since a wrong citation edge is worse than
a missed one: the graph is used for evidence traversal, so precision
matters more than recall here. Fully testable offline -- no DB/network.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


def normalize_title(title: str) -> str:
    """Lowercases, strips punctuation, and collapses whitespace so titles
    that differ only in casing/punctuation ("GCNs:" vs "gcns") still match."""
    lowered = title.lower()
    stripped = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", stripped).strip()


@dataclass
class CorpusPaper:
    paper_id: str
    title: str


@dataclass
class CitationMatch:
    reference_id: str
    cited_paper_id: str
    cited_paper_title: str
    match_confidence: float


def match_references_to_corpus(
    references: list[tuple[str, str]],  # (reference_id, raw_text)
    corpus: list[CorpusPaper],
    min_title_length: int = 15,
) -> list[CitationMatch]:
    """For each reference, checks whether any corpus paper's normalized
    title appears as a substring of the reference's raw text. Skips very
    short titles (`min_title_length` normalized chars) since short titles
    produce false positives as substrings of unrelated reference text.
    """
    matches: list[CitationMatch] = []
    normalized_corpus = [
        (p, normalize_title(p.title)) for p in corpus if len(normalize_title(p.title)) >= min_title_length
    ]

    for ref_id, raw_text in references:
        normalized_ref = normalize_title(raw_text)
        for paper, normalized_title in normalized_corpus:
            if normalized_title in normalized_ref:
                # Confidence scales with how much of the reference text the
                # matched title accounts for -- a title that's most of the
                # reference is a much stronger signal than one that's a
                # small fragment of a long reference blob.
                confidence = min(1.0, len(normalized_title) / max(len(normalized_ref), 1) + 0.4)
                matches.append(
                    CitationMatch(
                        reference_id=ref_id,
                        cited_paper_id=paper.paper_id,
                        cited_paper_title=paper.title,
                        match_confidence=round(confidence, 2),
                    )
                )
    return matches
