from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import Agent, AgentContext, AgentResult
from app.services.graph_service import extract_and_persist_for_paper


class ExtractionAgent(Agent):
    """Runs knowledge extraction (methods/datasets/metrics/claims) against
    every successfully-ingested paper and merges results into the shared
    knowledge graph."""

    name = "extraction_agent"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(self, context: AgentContext) -> AgentResult:
        papers = context.data.get("ingested_papers", [])
        knowledge_summaries = []

        for paper in papers:
            entities, relationships, method_used, cited_titles = await extract_and_persist_for_paper(self.db, paper)
            knowledge_summaries.append(
                {
                    "paper_id": paper.id,
                    "paper_title": paper.title,
                    "year": paper.published_at.year if paper.published_at else None,
                    "entities_created": len(entities),
                    "relationships_created": len(relationships),
                    "method_used": method_used,
                    "methods": [e.name for e in entities if e.entity_type == "method"],
                    "datasets": [e.name for e in entities if e.entity_type == "dataset"],
                    "claims": [e.description for e in entities if e.entity_type == "claim" and e.description],
                    "cites": cited_titles,
                }
            )

        context.data["knowledge"] = knowledge_summaries
        total_entities = sum(k["entities_created"] for k in knowledge_summaries)
        return AgentResult(
            agent_name=self.name,
            success=len(knowledge_summaries) > 0,
            summary=f"Extracted {total_entities} entities across {len(knowledge_summaries)} papers",
            output=knowledge_summaries,
        )
