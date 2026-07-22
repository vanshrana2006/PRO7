"""
Composes the concrete Discovery -> Reading -> Extraction -> Intelligence ->
Survey pipeline using the real DB/network-backed agents, on top of the
generic (and offline-tested) orchestrator runner.

This is the "Research Graph Neural Networks" one-command workflow from the
project spec: a single call that searches, ingests, extracts knowledge,
runs contradiction/gap/novelty/timeline/analysis/citation/recommendation
analysis, and writes a review -- with no manual steps in between.

Two entry points, sharing one agent list and one result-shaping function
so they can never drift apart:
  * run_research_pipeline()           -- awaits the whole thing, returns
    the complete result dict. Used by POST /api/research/run.
  * run_research_pipeline_streaming() -- async generator yielding a
    progress event per agent as it finishes, then the final result. Used
    by GET /api/research/run/stream (Server-Sent Events).
"""
from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.analysis_agent import AnalysisAgent
from app.agents.base import AgentContext
from app.agents.citation_agent import CitationAgent
from app.agents.contradiction_agent import ContradictionAgent
from app.agents.discovery_agent import DiscoveryAgent
from app.agents.extraction_agent import ExtractionAgent
from app.agents.gap_agent import GapAgent
from app.agents.novelty_agent import NoveltyAgent
from app.agents.orchestrator import run_pipeline, run_pipeline_streaming
from app.agents.reading_agent import ReadingAgent
from app.agents.recommendation_agent import RecommendationAgent
from app.agents.survey_agent import SurveyAgent
from app.agents.timeline_agent import TimelineAgent


def _build_agents(db: AsyncSession, max_papers: int) -> list:
    return [
        DiscoveryAgent(max_results=max_papers),
        ReadingAgent(db=db),
        ExtractionAgent(db=db),
        ContradictionAgent(),
        GapAgent(),
        NoveltyAgent(),
        TimelineAgent(),
        AnalysisAgent(),
        CitationAgent(),
        RecommendationAgent(),
        SurveyAgent(),
    ]


def _build_final_result(query: str, context: AgentContext, agent_results: list[dict]) -> dict:
    recommendations = context.data.get("recommendations", {})
    return {
        "query": query,
        "discovered_count": len(context.data.get("discovered_papers", [])),
        "ingested_count": len(context.data.get("ingested_papers", [])),
        "knowledge": context.data.get("knowledge", []),
        "contradictions": [asdict(c) for c in context.data.get("contradictions", [])],
        "gaps": [asdict(g) for g in context.data.get("gaps", [])],
        "novelty": [asdict(n) for n in context.data.get("novelty", [])],
        "timelines": [asdict(t) for t in context.data.get("timelines", [])],
        "analyses": [asdict(a) for a in context.data.get("analyses", [])],
        "missing_citations": [asdict(m) for m in context.data.get("missing_citations", [])],
        "recommendations": {
            title: [asdict(r) for r in recs] for title, recs in recommendations.items()
        },
        "survey_markdown": context.data.get("survey", ""),
        "agent_results": agent_results,
        "log": context.log,
    }


async def run_research_pipeline(db: AsyncSession, query: str, max_papers: int = 5) -> dict:
    context = AgentContext(query=query)
    agents = _build_agents(db, max_papers)

    results = await run_pipeline(agents, context, stop_on_failure=False)
    agent_results = [{"agent": r.agent_name, "success": r.success, "summary": r.summary} for r in results]

    return _build_final_result(query, context, agent_results)


async def run_research_pipeline_streaming(db: AsyncSession, query: str, max_papers: int = 5):
    """Async generator version of run_research_pipeline: yields a small
    progress event the instant each agent finishes, then one final event
    carrying the complete result (identical shape to run_research_pipeline's
    return value). Powers the SSE endpoint in api/routes/research.py.

    Each yielded item is a dict with a "type" discriminator so the
    consumer (SSE formatter, or a test) can tell progress events apart
    from the final result without inspecting shape:
        {"type": "progress", "agent": ..., "success": ..., "summary": ...}
        {"type": "result", **run_research_pipeline's normal return dict}
    """
    context = AgentContext(query=query)
    agents = _build_agents(db, max_papers)
    agent_results: list[dict] = []

    async for result in run_pipeline_streaming(agents, context, stop_on_failure=False):
        agent_results.append({"agent": result.agent_name, "success": result.success, "summary": result.summary})
        yield {
            "type": "progress",
            "agent": result.agent_name,
            "success": result.success,
            "summary": result.summary,
        }

    yield {"type": "result", **_build_final_result(query, context, agent_results)}
