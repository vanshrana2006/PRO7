from __future__ import annotations

from app.agents.base import Agent, AgentContext, AgentResult
from app.services.arxiv_client import ArxivClient, ArxivClientError


class DiscoveryAgent(Agent):
    name = "discovery_agent"

    def __init__(self, max_results: int = 5):
        self.max_results = max_results

    async def run(self, context: AgentContext) -> AgentResult:
        client = ArxivClient()
        try:
            entries = await client.search(context.query, max_results=self.max_results)
        except ArxivClientError as exc:
            return AgentResult(
                agent_name=self.name, success=False, summary=f"arXiv search failed: {exc}", output=[]
            )

        context.data["discovered_papers"] = entries
        return AgentResult(
            agent_name=self.name,
            success=len(entries) > 0,
            summary=f"Discovered {len(entries)} candidate papers for '{context.query}'",
            output=entries,
        )
