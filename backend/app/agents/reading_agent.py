from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import Agent, AgentContext, AgentResult
from app.models.paper import Paper
from app.services.ingest_service import IngestError, ingest_arxiv_paper


class ReadingAgent(Agent):
    """Ingests every paper found by DiscoveryAgent: downloads the PDF and
    runs structural extraction. One paper failing to download does not
    stop the others -- each is tried independently and failures are
    reported per-paper in the summary."""

    name = "reading_agent"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(self, context: AgentContext) -> AgentResult:
        discovered = context.data.get("discovered_papers", [])
        ingested: list[Paper] = []
        failures: list[str] = []

        for entry in discovered:
            try:
                paper = await ingest_arxiv_paper(self.db, entry.arxiv_id)
                if paper.extraction_status == "completed":
                    ingested.append(paper)
                else:
                    failures.append(f"{entry.arxiv_id}: {paper.extraction_error}")
            except IngestError as exc:
                failures.append(f"{entry.arxiv_id}: {exc}")

        context.data["ingested_papers"] = ingested
        summary = f"Ingested {len(ingested)}/{len(discovered)} papers"
        if failures:
            summary += f" ({len(failures)} failed: {'; '.join(failures[:3])})"

        return AgentResult(
            agent_name=self.name,
            success=len(ingested) > 0,
            summary=summary,
            output=ingested,
        )
