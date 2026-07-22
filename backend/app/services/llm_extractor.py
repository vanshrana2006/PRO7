"""
LLM-refined knowledge extraction. Produces the exact same ExtractionOutput
shape as app/services/knowledge_extraction.py so callers can swap between
the two paths without any downstream changes.

Requires ANTHROPIC_API_KEY (checked via llm_client.is_available()). This
module makes real network calls, so it isn't executed in this offline
sandbox -- verify it live once you've added a key (see README "Phase 2").
"""
from __future__ import annotations

from app.services.knowledge_extraction import ExtractedEntity, ExtractedRelationship, ExtractionOutput
from app.services.llm_client import LLMError, complete_json

SYSTEM_PROMPT = """You are a scientific knowledge extraction system. Given the text of a \
research paper's sections, extract structured knowledge as JSON.

Return ONLY a JSON object (no markdown fences, no prose) with this exact shape:
{
  "methods": [{"name": "...", "description": "..."}],
  "datasets": [{"name": "..."}],
  "metrics": [{"name": "..."}],
  "claims": [{"description": "...", "evidence": "the exact sentence supporting this claim"}]
}

Rules:
- Only extract things explicitly stated in the text -- never infer or invent.
- "methods" are novel techniques/models/algorithms the paper proposes, not techniques it merely cites.
- "claims" are specific, evidence-backed results (numbers, comparisons), not vague statements.
- If a category has nothing to extract, return an empty list for it.
"""


async def extract_from_sections_llm(sections: dict[str, str], paper_title: str) -> ExtractionOutput:
    if not sections:
        return ExtractionOutput()

    combined = "\n\n".join(f"## {k}\n{v}" for k, v in sections.items() if v.strip())
    user_prompt = f"Paper title: {paper_title}\n\n{combined[:12000]}"

    try:
        parsed = await complete_json(SYSTEM_PROMPT, user_prompt)
    except LLMError:
        # Callers are expected to catch this and fall back to the heuristic
        # path -- see app/api/routes/knowledge.py. Re-raise rather than
        # silently returning empty, so the fallback is a deliberate choice
        # made by the caller, not a hidden default.
        raise

    if not isinstance(parsed, dict):
        raise LLMError("Expected a JSON object from the model")

    output = ExtractionOutput()

    for m in parsed.get("methods", []):
        name = m.get("name")
        if not name:
            continue
        output.entities.append(
            ExtractedEntity(
                entity_type="method",
                name=name,
                description=m.get("description"),
                extraction_method="llm",
                confidence=0.85,
            )
        )
        output.relationships.append(
            ExtractedRelationship(
                source_name=paper_title,
                target_name=name,
                relationship_type="proposes",
                evidence=m.get("description"),
                confidence=0.85,
            )
        )

    for d in parsed.get("datasets", []):
        name = d.get("name")
        if not name:
            continue
        output.entities.append(
            ExtractedEntity(entity_type="dataset", name=name, extraction_method="llm", confidence=0.85)
        )
        output.relationships.append(
            ExtractedRelationship(
                source_name=paper_title,
                target_name=name,
                relationship_type="evaluated_on",
                confidence=0.85,
            )
        )

    for met in parsed.get("metrics", []):
        name = met.get("name")
        if not name:
            continue
        output.entities.append(
            ExtractedEntity(entity_type="metric", name=name, extraction_method="llm", confidence=0.85)
        )
        output.relationships.append(
            ExtractedRelationship(
                source_name=paper_title,
                target_name=name,
                relationship_type="mentions",
                confidence=0.85,
            )
        )

    for i, c in enumerate(parsed.get("claims", [])):
        desc = c.get("description")
        if not desc:
            continue
        claim_name = f"{paper_title} — claim {i + 1}"
        output.entities.append(
            ExtractedEntity(
                entity_type="claim",
                name=claim_name,
                description=desc,
                extraction_method="llm",
                confidence=0.85,
            )
        )
        output.relationships.append(
            ExtractedRelationship(
                source_name=paper_title,
                target_name=claim_name,
                relationship_type="mentions",
                evidence=c.get("evidence", desc),
                confidence=0.85,
            )
        )

    return output
