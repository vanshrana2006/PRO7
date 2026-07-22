from __future__ import annotations

from app.agents.base import Agent, AgentContext, AgentResult
from app.services.research_intelligence import detect_gaps


class GapAgent(Agent):
    """Surfaces underexplored datasets and unevaluated methods across this
    run's papers -- see research_intelligence.py for the exact heuristic."""

    name = "gap_agent"

    async def run(self, context: AgentContext) -> AgentResult:
        knowledge = context.data.get("knowledge", [])
        gaps = detect_gaps(knowledge)
        context.data["gaps"] = gaps
        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=f"Identified {len(gaps)} candidate research gap(s)",
            output=gaps,
        )
