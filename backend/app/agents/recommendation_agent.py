from __future__ import annotations

from app.agents.base import Agent, AgentContext, AgentResult
from app.services.research_intelligence import recommend_related_papers


class RecommendationAgent(Agent):
    """Recommends related papers within this run, ranked by shared
    datasets/methods -- see research_intelligence.recommend_related_papers.
    Grounded in extracted overlap, not embedding similarity (dense
    retrieval isn't wired up yet -- see docs/GAP_ANALYSIS.md)."""

    name = "recommendation_agent"

    async def run(self, context: AgentContext) -> AgentResult:
        knowledge = context.data.get("knowledge", [])
        recommendations = recommend_related_papers(knowledge)
        context.data["recommendations"] = recommendations
        total = sum(len(v) for v in recommendations.values())
        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=f"Generated {total} paper recommendation(s) across {len(knowledge)} papers",
            output=recommendations,
        )
