from __future__ import annotations

from pydantic import BaseModel


class ResearchRunRequest(BaseModel):
    query: str
    max_papers: int = 5


class AgentResultOut(BaseModel):
    agent: str
    success: bool
    summary: str


class KnowledgeSummaryOut(BaseModel):
    paper_id: str
    paper_title: str
    year: int | None = None
    entities_created: int
    relationships_created: int
    method_used: str
    methods: list[str]
    datasets: list[str]
    claims: list[str]


class ContradictionOut(BaseModel):
    dataset: str
    spread: float
    figures: list[dict]


class GapOut(BaseModel):
    kind: str
    subject: str
    detail: str


class NoveltyOut(BaseModel):
    method_name: str
    paper_title: str
    novelty_score: float
    similar_to: list[str]


class TimelinePointOut(BaseModel):
    paper_title: str
    year: int
    dataset: str
    value: float
    raw_claim: str


class BenchmarkTimelineOut(BaseModel):
    dataset: str
    points: list[TimelinePointOut]
    improved: bool


class PaperAnalysisOut(BaseModel):
    paper_id: str
    paper_title: str
    novelty_score: float | None  # avg novelty of this paper's own proposed methods; None if it proposes none
    impact_score: float  # 0-1: share of other papers in this run sharing a dataset/method with it
    evidence_density: float  # evidence-backed claims per extracted method+dataset
    key_contributions: list[str]
    summary: str


class MissingCitationOut(BaseModel):
    citing_paper_title: str
    concept: str
    concept_type: str
    likely_source_paper: str
    reason: str


class PaperRecommendationOut(BaseModel):
    paper_title: str
    recommended_paper_title: str
    shared_concepts: list[str]
    score: float


class ResearchRunResponse(BaseModel):
    query: str
    discovered_count: int
    ingested_count: int
    knowledge: list[KnowledgeSummaryOut]
    contradictions: list[ContradictionOut]
    gaps: list[GapOut]
    novelty: list[NoveltyOut]
    timelines: list[BenchmarkTimelineOut]
    analyses: list[PaperAnalysisOut]
    missing_citations: list[MissingCitationOut]
    recommendations: dict[str, list[PaperRecommendationOut]]
    survey_markdown: str
    agent_results: list[AgentResultOut]
    log: list[str]
