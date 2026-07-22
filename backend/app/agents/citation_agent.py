from __future__ import annotations

from app.agents.base import Agent, AgentContext, AgentResult
from app.services.research_intelligence import detect_missing_citations


class CitationAgent(Agent):
    """Flags likely missing citations: a paper uses a dataset that only
    one other paper in this run evaluates on, but doesn't cite that paper
    -- see research_intelligence.detect_missing_citations for exactly how
    "cites" is determined (real reference-text matching, not a guess)."""

    name = "citation_agent"

    async def run(self, context: AgentContext) -> AgentResult:
        knowledge = context.data.get("knowledge", [])
        missing = detect_missing_citations(knowledge)
        context.data["missing_citations"] = missing
        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=f"Found {len(missing)} likely missing citation(s) across {len(knowledge)} papers",
            output=missing,
        )
