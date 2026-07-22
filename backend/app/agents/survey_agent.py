from __future__ import annotations

from app.agents.base import Agent, AgentContext, AgentResult
from app.services.llm_client import LLMError, complete_json, is_available as llm_is_available
from app.services.survey_templates import generate_template_survey

SURVEY_SYSTEM_PROMPT = """You are a research scientist writing a concise literature review. \
Given structured knowledge extracted from a set of papers, write a well-organized review in \
Markdown. Return ONLY a JSON object of the shape {"review_markdown": "..."} -- no other text.

Base the review strictly on the provided facts. Do not invent findings, numbers, or papers not \
listed. Organize by theme (methods, datasets, key results) and note any complementary or \
conflicting findings across papers where evidence supports it."""


class SurveyAgent(Agent):
    """Synthesizes a literature review from the knowledge ExtractionAgent
    produced. Uses the LLM for genuine synthesis/prose when available;
    otherwise produces a structured, fact-grounded template summary so the
    pipeline still delivers a real, useful artifact with zero API keys."""

    name = "survey_agent"

    async def run(self, context: AgentContext) -> AgentResult:
        knowledge = context.data.get("knowledge", [])

        if llm_is_available():
            try:
                user_prompt = f"Query: {context.query}\n\nExtracted knowledge:\n{knowledge}"
                parsed = await complete_json(SURVEY_SYSTEM_PROMPT, user_prompt, max_tokens=3000)
                review = parsed.get("review_markdown") if isinstance(parsed, dict) else None
                if review:
                    context.data["survey"] = review
                    return AgentResult(
                        agent_name=self.name,
                        success=True,
                        summary="Generated LLM-synthesized literature review",
                        output=review,
                    )
            except LLMError:
                pass  # fall through to template below

        review = generate_template_survey(context.query, knowledge)
        context.data["survey"] = review
        return AgentResult(
            agent_name=self.name,
            success=bool(knowledge),
            summary="Generated template-based literature review (no LLM key configured)",
            output=review,
        )
