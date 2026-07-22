from __future__ import annotations

from app.agents.base import Agent, AgentContext, AgentResult
from app.services.research_intelligence import detect_contradictions


class ContradictionAgent(Agent):
    """Flags datasets where different papers in this run report results
    diverging beyond a threshold -- see research_intelligence.py for the
    exact (real, inspectable) heuristic."""

    name = "contradiction_agent"

    async def run(self, context: AgentContext) -> AgentResult:
        knowledge = context.data.get("knowledge", [])
        contradictions = detect_contradictions(knowledge)
        context.data["contradictions"] = contradictions
        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=f"Found {len(contradictions)} potential contradiction(s) across {len(knowledge)} papers",
            output=contradictions,
        )
