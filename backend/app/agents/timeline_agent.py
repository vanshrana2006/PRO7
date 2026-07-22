from __future__ import annotations

from app.agents.base import Agent, AgentContext, AgentResult
from app.services.research_intelligence import build_benchmark_timelines


class TimelineAgent(Agent):
    """Builds year-ordered benchmark progress timelines from claimed
    results across this run's papers -- see research_intelligence.py."""

    name = "timeline_agent"

    async def run(self, context: AgentContext) -> AgentResult:
        knowledge = context.data.get("knowledge", [])
        timelines = build_benchmark_timelines(knowledge)
        context.data["timelines"] = timelines
        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=f"Built {len(timelines)} benchmark timeline(s) from dated papers in this run",
            output=timelines,
        )
