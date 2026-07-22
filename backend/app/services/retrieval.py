"""
BM25 sparse retrieval over ingested papers' full text.

A real, standard implementation (Robertson/Sparck-Jones BM25, k1=1.5,
b=0.75 defaults) -- not a placeholder or a fake "AI search" wrapper around
substring matching. Pure Python/stdlib (tokenization via regex, no numpy
needed at this corpus scale), so it's fully unit-testable offline.

This is the "Sparse Retrieval" piece of the retrieval stack. It's useful
standalone (keyword search over your ingested corpus) and is designed to
combine with dense/embedding retrieval later via Reciprocal Rank Fusion
(see `reciprocal_rank_fusion` below) once an embeddings provider is wired
up (API-key-gated, same optional-upgrade pattern as the LLM extraction
path) -- the fusion function doesn't care where either ranked list came
from, so hybrid retrieval is an additive change, not a rewrite.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

# Small, standard English stopword list -- filtering these out is what
# makes BM25 rank on meaningful terms instead of "the"/"of"/"and".
_STOPWORDS = frozenset(
    """
    a an the and or but if of to in on for with as by is are was were be
    been being this that these those it its from at into over under
    between we our their they he she his her them you your i not no
    can could will would should may might do does did have has had
    """.split()
)


def tokenize(text: str) -> list[str]:
    tokens = _TOKEN_PATTERN.findall(text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


@dataclass
class ScoredDocument:
    doc_id: str
    score: float


class BM25Index:
    """In-memory BM25 index. Rebuilt from the current corpus on each
    `build()` call rather than incrementally maintained -- appropriate for
    this platform's scale (hundreds to low thousands of papers); for a
    truly large, continuously-growing corpus, a dedicated search engine
    (OpenSearch/Elasticsearch) would replace this, using the same
    tokenize() function for consistency.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._doc_term_freqs: dict[str, Counter] = {}
        self._doc_lengths: dict[str, int] = {}
        self._avg_doc_length: float = 0.0
        self._doc_freq: Counter = Counter()  # in how many docs does term t appear
        self._n_docs: int = 0

    def build(self, documents: dict[str, str]) -> None:
        """documents: doc_id -> raw text."""
        self._doc_term_freqs = {}
        self._doc_lengths = {}
        self._doc_freq = Counter()

        for doc_id, text in documents.items():
            tokens = tokenize(text)
            term_freqs = Counter(tokens)
            self._doc_term_freqs[doc_id] = term_freqs
            self._doc_lengths[doc_id] = len(tokens)
            for term in term_freqs:
                self._doc_freq[term] += 1

        self._n_docs = len(documents)
        self._avg_doc_length = (
            sum(self._doc_lengths.values()) / self._n_docs if self._n_docs else 0.0
        )

    def _idf(self, term: str) -> float:
        df = self._doc_freq.get(term, 0)
        # Standard BM25 IDF with a +1 smoothing floor so a term that
        # appears in every document still gets a small positive weight
        # instead of going negative.
        return math.log((self._n_docs - df + 0.5) / (df + 0.5) + 1.0)

    def search(self, query: str, top_k: int = 10) -> list[ScoredDocument]:
        if self._n_docs == 0:
            return []

        query_terms = tokenize(query)
        if not query_terms:
            return []

        scores: dict[str, float] = {}
        for doc_id, term_freqs in self._doc_term_freqs.items():
            doc_length = self._doc_lengths[doc_id]
            score = 0.0
            for term in query_terms:
                if term not in term_freqs:
                    continue
                freq = term_freqs[term]
                idf = self._idf(term)
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (
                    1 - self.b + self.b * doc_length / max(self._avg_doc_length, 1e-9)
                )
                score += idf * (numerator / denominator)
            if score > 0:
                scores[doc_id] = score

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [ScoredDocument(doc_id=doc_id, score=round(score, 4)) for doc_id, score in ranked[:top_k]]


def reciprocal_rank_fusion(
    ranked_lists: list[list[ScoredDocument]], k: int = 60
) -> list[ScoredDocument]:
    """Combines multiple ranked result lists (e.g. BM25 + a future dense
    retriever) into one fused ranking via Reciprocal Rank Fusion: each
    document's fused score is the sum of 1/(k + rank) across every list it
    appears in. RRF is used specifically because it needs no score
    normalization between retrieval methods with different score scales
    (BM25 scores and cosine similarities aren't comparable directly) --
    only rank position, which is why this is the standard hybrid-retrieval
    fusion technique rather than a naive weighted score average.
    """
    fused: dict[str, float] = {}
    for ranked_list in ranked_lists:
        for rank, doc in enumerate(ranked_list, start=1):
            fused[doc.doc_id] = fused.get(doc.doc_id, 0.0) + 1.0 / (k + rank)

    ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
    return [ScoredDocument(doc_id=doc_id, score=round(score, 6)) for doc_id, score in ranked]
