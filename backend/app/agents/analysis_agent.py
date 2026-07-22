from __future__ import annotations

from app.agents.base import Agent, AgentContext, AgentResult
from app.services.research_intelligence import compute_paper_analyses


class AnalysisAgent(Agent):
    """Computes per-paper novelty/impact/evidence-density scores and a
    grounded contribution summary -- see research_intelligence.py for
    exactly what each score means and how it's computed. Every number
    traces to a specific extracted-knowledge computation, not an
    arbitrary LLM-assigned rating."""

    name = "analysis_agent"

    async def run(self, context: AgentContext) -> AgentResult:
        knowledge = context.data.get("knowledge", [])
        analyses = compute_paper_analyses(knowledge)
        context.data["analyses"] = analyses
        return AgentResult(
            agent_name=self.name,
            success=len(analyses) > 0,
            summary=f"Computed analysis scores for {len(analyses)} paper(s)",
            output=analyses,
        )
