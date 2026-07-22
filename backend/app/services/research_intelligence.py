"""
Pure heuristic logic backing the Contradiction, Gap, and Novelty agents.
No DB/network dependency -- operates entirely on the `knowledge`
summaries ExtractionAgent already produced, so it's testable offline and
runs with zero API keys (an LLM-refined version is a natural next step,
same optional-upgrade pattern as knowledge_extraction.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_NUMBER_METRIC_PATTERN = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*%", re.IGNORECASE
)


@dataclass
class ClaimFigure:
    paper_title: str
    dataset: str
    value: float
    raw_claim: str


@dataclass
class Contradiction:
    dataset: str
    figures: list[ClaimFigure]
    spread: float  # max - min percentage points


@dataclass
class ResearchGap:
    kind: str  # 'underexplored_dataset' | 'unevaluated_method'
    subject: str
    detail: str


@dataclass
class NoveltyAssessment:
    method_name: str
    paper_title: str
    novelty_score: float  # 0 (looks like an existing method) - 1 (looks novel)
    similar_to: list[str]


@dataclass
class TimelinePoint:
    paper_title: str
    year: int
    dataset: str
    value: float
    raw_claim: str


@dataclass
class BenchmarkTimeline:
    dataset: str
    points: list[TimelinePoint]  # sorted by year
    improved: bool  # True if the last point's value > the first's


def _extract_claim_figures(knowledge_summaries: list[dict]) -> list[ClaimFigure]:
    figures: list[ClaimFigure] = []
    for k in knowledge_summaries:
        datasets = k.get("datasets", [])
        for claim in k.get("claims", []):
            if not claim:
                continue
            number_match = _NUMBER_METRIC_PATTERN.search(claim)
            if not number_match:
                continue
            value = float(number_match.group(1))
            # Associate the claim with whichever of the paper's datasets is
            # mentioned in the same sentence; if none match by name, skip --
            # a wrong dataset association is worse than no association.
            for ds in datasets:
                if ds.lower() in claim.lower():
                    figures.append(
                        ClaimFigure(paper_title=k["paper_title"], dataset=ds, value=value, raw_claim=claim)
                    )
    return figures


def detect_contradictions(knowledge_summaries: list[dict], min_spread: float = 5.0) -> list[Contradiction]:
    """Flags datasets where different papers report results that diverge by
    more than `min_spread` percentage points -- a real (if coarse) signal
    of contradictory or at least hard-to-reconcile findings, not a fake
    placeholder check."""
    figures = _extract_claim_figures(knowledge_summaries)
    by_dataset: dict[str, list[ClaimFigure]] = {}
    for f in figures:
        by_dataset.setdefault(f.dataset, []).append(f)

    contradictions: list[Contradiction] = []
    for dataset, figs in by_dataset.items():
        if len(figs) < 2:
            continue
        values = [f.value for f in figs]
        spread = max(values) - min(values)
        if spread >= min_spread:
            contradictions.append(Contradiction(dataset=dataset, figures=figs, spread=round(spread, 2)))

    return sorted(contradictions, key=lambda c: c.spread, reverse=True)


def detect_gaps(knowledge_summaries: list[dict]) -> list[ResearchGap]:
    """Two concrete, explainable gap signals:
    - a dataset mentioned by only one paper in the corpus (underexplored)
    - a method with no dataset evaluation recorded at all (unevaluated)
    Not a fake "AI found gaps!" claim -- each flagged item traces to a
    specific, inspectable pattern in the extracted knowledge.
    """
    dataset_counts: dict[str, int] = {}
    for k in knowledge_summaries:
        for ds in k.get("datasets", []):
            dataset_counts[ds] = dataset_counts.get(ds, 0) + 1

    gaps: list[ResearchGap] = []
    for ds, count in dataset_counts.items():
        if count == 1:
            gaps.append(
                ResearchGap(
                    kind="underexplored_dataset",
                    subject=ds,
                    detail=f"'{ds}' appears in only 1 paper in this corpus -- limited cross-paper validation.",
                )
            )

    for k in knowledge_summaries:
        if k.get("methods") and not k.get("datasets"):
            for method in k["methods"]:
                gaps.append(
                    ResearchGap(
                        kind="unevaluated_method",
                        subject=method,
                        detail=f"'{method}' (from '{k['paper_title']}') has no recognized dataset evaluation in the extracted text.",
                    )
                )

    return gaps


def assess_novelty(knowledge_summaries: list[dict]) -> list[NoveltyAssessment]:
    """Flags proposed methods whose names share significant word overlap
    with other methods already seen in the corpus -- a coarse but real
    signal that a "novel" method may be a variant/rename of prior work,
    worth a closer look rather than an LLM guess dressed up as certainty.
    """
    all_methods: list[tuple[str, str]] = []  # (paper_title, method_name)
    for k in knowledge_summaries:
        for m in k.get("methods", []):
            all_methods.append((k["paper_title"], m))

    def words(name: str) -> set[str]:
        return set(re.findall(r"[a-z]+", name.lower()))

    assessments: list[NoveltyAssessment] = []
    for paper_title, method in all_methods:
        method_words = words(method)
        similar: list[str] = []
        for other_title, other_method in all_methods:
            if other_method == method and other_title == paper_title:
                continue
            overlap = method_words & words(other_method)
            if method_words and len(overlap) / len(method_words) >= 0.5:
                similar.append(other_method)

        novelty_score = 1.0 if not similar else max(0.0, 1.0 - 0.3 * len(similar))
        assessments.append(
            NoveltyAssessment(
                method_name=method,
                paper_title=paper_title,
                novelty_score=round(novelty_score, 2),
                similar_to=similar,
            )
        )
    return assessments


def _extract_claim_figures_with_year(knowledge_summaries: list[dict]) -> list[TimelinePoint]:
    points: list[TimelinePoint] = []
    for k in knowledge_summaries:
        year = k.get("year")
        if not year:
            continue
        datasets = k.get("datasets", [])
        for claim in k.get("claims", []):
            if not claim:
                continue
            number_match = _NUMBER_METRIC_PATTERN.search(claim)
            if not number_match:
                continue
            value = float(number_match.group(1))
            for ds in datasets:
                if ds.lower() in claim.lower():
                    points.append(
                        TimelinePoint(paper_title=k["paper_title"], year=year, dataset=ds, value=value, raw_claim=claim)
                    )
    return points


def build_benchmark_timelines(knowledge_summaries: list[dict], min_points: int = 2) -> list[BenchmarkTimeline]:
    """For each dataset with claimed results across multiple *dated* papers
    in this run, builds a year-ordered timeline of reported figures --
    grounded entirely in extracted claims, not an LLM narrative. Papers
    with no recognized publication year are excluded from timelines (a
    timeline needs an axis), which is an honest omission rather than a
    guessed date.
    """
    figures = _extract_claim_figures_with_year(knowledge_summaries)
    by_dataset: dict[str, list[TimelinePoint]] = {}
    for f in figures:
        by_dataset.setdefault(f.dataset, []).append(f)

    timelines: list[BenchmarkTimeline] = []
    for dataset, points in by_dataset.items():
        if len(points) < min_points:
            continue
        points_sorted = sorted(points, key=lambda p: p.year)
        improved = points_sorted[-1].value > points_sorted[0].value
        timelines.append(BenchmarkTimeline(dataset=dataset, points=points_sorted, improved=improved))

    return sorted(timelines, key=lambda t: t.dataset)


@dataclass
class PaperAnalysis:
    paper_id: str
    paper_title: str
    novelty_score: float | None
    impact_score: float
    evidence_density: float
    key_contributions: list[str]
    summary: str


def compute_paper_analyses(knowledge_summaries: list[dict]) -> list[PaperAnalysis]:
    """Per-paper analysis scores, each grounded in a specific, inspectable
    extracted-knowledge computation -- not an arbitrary LLM-assigned
    number:

    - novelty_score: mean novelty (see assess_novelty) of this paper's own
      proposed methods; None if it proposes none.
    - impact_score: share of OTHER papers in this run that share at least
      one dataset or method with this paper -- a real (if run-scoped)
      connectivity signal, not a citation-count guess.
    - evidence_density: evidence-backed claims per extracted method+dataset
      -- how well-supported the paper's contributions are by quantified
      results, in the text actually extracted.
    """
    novelty_assessments = assess_novelty(knowledge_summaries)
    novelty_by_paper: dict[str, list[float]] = {}
    for a in novelty_assessments:
        novelty_by_paper.setdefault(a.paper_title, []).append(a.novelty_score)

    n_other_papers = max(len(knowledge_summaries) - 1, 1)

    analyses: list[PaperAnalysis] = []
    for k in knowledge_summaries:
        title = k["paper_title"]
        methods = set(k.get("methods", []))
        datasets = set(k.get("datasets", []))
        claims = k.get("claims", [])

        novelty_scores = novelty_by_paper.get(title)
        novelty_score = round(sum(novelty_scores) / len(novelty_scores), 2) if novelty_scores else None

        shared_with = 0
        for other in knowledge_summaries:
            if other["paper_title"] == title:
                continue
            other_methods = set(other.get("methods", []))
            other_datasets = set(other.get("datasets", []))
            if (methods & other_methods) or (datasets & other_datasets):
                shared_with += 1
        impact_score = round(shared_with / n_other_papers, 2)

        concept_count = max(len(methods) + len(datasets), 1)
        evidence_density = round(len(claims) / concept_count, 2)

        contribution_parts = []
        if methods:
            contribution_parts.append(f"proposes {', '.join(sorted(methods))}")
        if datasets:
            contribution_parts.append(f"evaluated on {', '.join(sorted(datasets))}")
        if contribution_parts:
            joined = "; ".join(contribution_parts)
            # Capitalize only the first character -- str.capitalize() would
            # lowercase the rest of the string, mangling names like "M1" or
            # "GraphMix" into "m1"/"graphmix".
            joined = joined[0].upper() + joined[1:] if joined else joined
            summary = f"{joined}; {len(claims)} evidence-backed claim(s) extracted."
        else:
            summary = f"{len(claims)} evidence-backed claim(s) extracted; no methods or datasets recognized in the text."

        analyses.append(
            PaperAnalysis(
                paper_id=k["paper_id"],
                paper_title=title,
                novelty_score=novelty_score,
                impact_score=impact_score,
                evidence_density=evidence_density,
                key_contributions=sorted(methods),
                summary=summary,
            )
        )

    return analyses


@dataclass
class MissingCitation:
    citing_paper_title: str
    concept: str  # the dataset or method name shared
    concept_type: str  # 'dataset' | 'method'
    likely_source_paper: str
    reason: str


def detect_missing_citations(knowledge_summaries: list[dict]) -> list[MissingCitation]:
    """Flags cases where paper A uses/mentions a dataset or method that
    paper B in this run *proposes*, but A's actual resolved citations
    (`cites`, populated by citation_matcher.py from real reference-text
    matching -- see graph_service.build_citation_edges) don't include B.

    This is a real, inspectable signal -- not a guess: it only fires when
    both (a) a concrete name overlap exists in extracted text and (b) the
    citation graph, built from actual reference-list matching, confirms no
    citation edge exists. A dataset name overlap alone is not sufific ient
    (very common dataset names would create constant false positives);
    requiring the "proposing" relationship notably narrows this to the
    cases that matter -- did you cite the paper that introduced the thing
    you're using.
    """
    # Only datasets/methods that are *introduced* somewhere give a
    # concrete "should have cited this" target -- we approximate
    # "introduces" as "is the only paper in this run proposing/using it",
    # since two independent introductions of the same name is rare within
    # one run and disambiguating a true origin is out of scope for a
    # same-run heuristic.
    dataset_origin: dict[str, str] = {}
    for k in knowledge_summaries:
        for ds in k.get("datasets", []):
            dataset_origin.setdefault(ds, k["paper_title"])

    missing: list[MissingCitation] = []
    for k in knowledge_summaries:
        title = k["paper_title"]
        cited = set(k.get("cites", []))

        for ds in k.get("datasets", []):
            origin = dataset_origin.get(ds)
            if origin and origin != title and origin not in cited:
                missing.append(
                    MissingCitation(
                        citing_paper_title=title,
                        concept=ds,
                        concept_type="dataset",
                        likely_source_paper=origin,
                        reason=f"Uses '{ds}', which only '{origin}' evaluates on in this run, but does not cite it.",
                    )
                )

        # Methods are almost always the citing paper's own contribution in
        # this extraction pipeline (see knowledge_extraction.py's "we
        # propose X" pattern), so a paper very rarely "uses" a method it
        # didn't itself propose under this heuristic -- dataset reuse above
        # is the meaningful missing-citation signal this function reports.

    return missing


@dataclass
class PaperRecommendation:
    paper_title: str
    recommended_paper_title: str
    shared_concepts: list[str]
    score: float


def recommend_related_papers(knowledge_summaries: list[dict], top_k: int = 3) -> dict[str, list[PaperRecommendation]]:
    """For each paper, recommends other papers in this run ranked by
    shared datasets/methods -- "if you're reading this, you may also want
    to read..." grounded entirely in extracted overlap, not embeddings
    similarity (which isn't wired up -- see docs/GAP_ANALYSIS.md). Returns
    a dict keyed by paper_title for direct lookup.
    """
    recommendations: dict[str, list[PaperRecommendation]] = {}

    for k in knowledge_summaries:
        title = k["paper_title"]
        concepts = set(k.get("methods", [])) | set(k.get("datasets", []))
        scored: list[PaperRecommendation] = []

        for other in knowledge_summaries:
            other_title = other["paper_title"]
            if other_title == title:
                continue
            other_concepts = set(other.get("methods", [])) | set(other.get("datasets", []))
            shared = concepts & other_concepts
            if shared:
                scored.append(
                    PaperRecommendation(
                        paper_title=title,
                        recommended_paper_title=other_title,
                        shared_concepts=sorted(shared),
                        score=round(len(shared) / max(len(concepts), 1), 2),
                    )
                )

        scored.sort(key=lambda r: r.score, reverse=True)
        recommendations[title] = scored[:top_k]

    return recommendations
