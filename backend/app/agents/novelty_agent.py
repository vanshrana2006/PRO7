from __future__ import annotations

from app.agents.base import Agent, AgentContext, AgentResult
from app.services.research_intelligence import assess_novelty


class NoveltyAgent(Agent):
    """Scores each proposed method's apparent novelty against other methods
    seen in this run, by name-overlap -- see research_intelligence.py."""

    name = "novelty_agent"

    async def run(self, context: AgentContext) -> AgentResult:
        knowledge = context.data.get("knowledge", [])
        assessments = assess_novelty(knowledge)
        context.data["novelty"] = assessments
        low_novelty = [a for a in assessments if a.novelty_score < 1.0]
        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=f"Assessed {len(assessments)} method(s); {len(low_novelty)} overlap with prior work in this run",
            output=assessments,
        )
