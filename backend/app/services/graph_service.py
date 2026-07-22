"""
Persists ExtractionOutput (from knowledge_extraction.py, and later
llm_extractor.py) into the kg_entities / kg_relationships tables, and
provides read queries for the graph API.

Entity resolution: a new entity is only created if no existing entity of
the same type + normalized name exists yet -- so "Cora" mentioned in ten
papers becomes one graph node with ten "evaluated_on" edges, not ten
duplicate nodes. This is what makes the graph actually useful for
cross-paper queries ("which papers use Cora?") instead of being ten
disconnected islands.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_graph import Entity, Relationship
from app.models.paper import Paper
from app.services.citation_matcher import CorpusPaper, match_references_to_corpus
from app.services.knowledge_extraction import ExtractionOutput, extract_from_sections
from app.services.llm_client import LLMError, is_available as llm_is_available
from app.services.llm_extractor import extract_from_sections_llm


async def _get_or_create_entity(
    db: AsyncSession,
    entity_type: str,
    name: str,
    source_paper_id: str | None,
    description: str | None,
    extraction_method: str,
    confidence: float,
) -> Entity:
    normalized = name.strip().lower()
    result = await db.execute(
        select(Entity).where(Entity.entity_type == entity_type, Entity.normalized_name == normalized)
    )
    entity = result.scalar_one_or_none()
    if entity is None:
        entity = Entity(
            entity_type=entity_type,
            name=name.strip(),
            normalized_name=normalized,
            description=description,
            source_paper_id=source_paper_id,
            extraction_method=extraction_method,
            confidence=confidence,
        )
        db.add(entity)
        await db.flush()
    return entity


async def persist_extraction(
    db: AsyncSession, paper: Paper, output: ExtractionOutput
) -> tuple[list[Entity], list[Relationship]]:
    # Paper itself is always a node so relationships have somewhere to point.
    paper_entity = await _get_or_create_entity(
        db,
        entity_type="paper",
        name=paper.title,
        source_paper_id=paper.id,
        description=paper.abstract,
        extraction_method="direct",
        confidence=1.0,
    )

    name_to_entity: dict[str, Entity] = {paper.title.strip().lower(): paper_entity}
    created_entities: list[Entity] = []

    for ent in output.entities:
        entity = await _get_or_create_entity(
            db,
            entity_type=ent.entity_type,
            name=ent.name,
            source_paper_id=paper.id if ent.entity_type == "claim" else None,
            description=ent.description,
            extraction_method=ent.extraction_method,
            confidence=ent.confidence,
        )
        name_to_entity[ent.name.strip().lower()] = entity
        created_entities.append(entity)

    created_relationships: list[Relationship] = []
    for rel in output.relationships:
        source = name_to_entity.get(rel.source_name.strip().lower())
        target = name_to_entity.get(rel.target_name.strip().lower())
        if source is None or target is None:
            continue  # defensive: never create a dangling-reference edge

        relationship = Relationship(
            source_entity_id=source.id,
            target_entity_id=target.id,
            relationship_type=rel.relationship_type,
            evidence=rel.evidence,
            confidence=rel.confidence,
        )
        db.add(relationship)
        created_relationships.append(relationship)

    await db.commit()
    return created_entities, created_relationships


async def build_citation_edges(db: AsyncSession, paper: Paper) -> tuple[list[Relationship], list[str]]:
    """Resolves this paper's extracted references against every other
    ingested paper in the corpus and creates real `cites` edges in the
    graph -- turning isolated per-paper reference lists into an actual
    citation graph. Conservative matching (see citation_matcher.py):
    correctness over coverage, since these edges drive evidence traversal.

    Returns (relationships_created, cited_paper_titles) -- the titles are
    surfaced so callers (ExtractionAgent) can compare "what this paper
    actually cites" against "what it should probably cite" for missing-
    citation detection (see research_intelligence.detect_missing_citations),
    without a second DB round-trip.
    """
    corpus_result = await db.execute(select(Paper.id, Paper.title).where(Paper.id != paper.id))
    corpus = [CorpusPaper(paper_id=pid, title=title) for pid, title in corpus_result.all()]
    if not corpus:
        return [], []

    references = [(ref.id, ref.raw_text) for ref in paper.references]
    if not references:
        return [], []

    matches = match_references_to_corpus(references, corpus)
    if not matches:
        return [], []

    # Ensure a paper-type entity exists for the citing paper.
    source_entity = await _get_or_create_entity(
        db, entity_type="paper", name=paper.title, source_paper_id=paper.id,
        description=paper.abstract, extraction_method="direct", confidence=1.0,
    )

    created: list[Relationship] = []
    cited_titles: list[str] = []
    for match in matches:
        cited_paper_result = await db.execute(select(Paper).where(Paper.id == match.cited_paper_id))
        cited_paper = cited_paper_result.scalar_one_or_none()
        if cited_paper is None:
            continue
        target_entity = await _get_or_create_entity(
            db, entity_type="paper", name=cited_paper.title, source_paper_id=cited_paper.id,
            description=cited_paper.abstract, extraction_method="direct", confidence=1.0,
        )
        relationship = Relationship(
            source_entity_id=source_entity.id,
            target_entity_id=target_entity.id,
            relationship_type="cites",
            evidence=match.cited_paper_title,
            confidence=match.match_confidence,
        )
        db.add(relationship)
        created.append(relationship)
        cited_titles.append(cited_paper.title)

    await db.commit()
    return created, cited_titles


async def extract_and_persist_for_paper(
    db: AsyncSession, paper: Paper
) -> tuple[list[Entity], list[Relationship], str, list[str]]:
    """Runs extraction against a paper's already-extracted sections and
    persists the result to the graph. Uses the LLM path when an API key is
    configured, and transparently falls back to the heuristic path if the
    LLM call fails for any reason (rate limit, bad JSON, network) -- so a
    flaky LLM call never means "no extraction happened" for the user.
    Returns (entities, relationships, method_used, cited_paper_titles) so
    callers/UI can show which path actually ran and what this paper's
    references actually resolved to in the corpus.
    """
    sections_by_type: dict[str, str] = {}
    for section in paper.sections:
        sections_by_type.setdefault(section.section_type, "")
        sections_by_type[section.section_type] += "\n" + section.content

    method_used = "heuristic"
    output: ExtractionOutput | None = None

    if llm_is_available():
        try:
            output = await extract_from_sections_llm(sections_by_type, paper_title=paper.title)
            method_used = "llm"
        except LLMError:
            output = None  # fall through to heuristic below

    if output is None:
        output = extract_from_sections(sections_by_type, paper_title=paper.title)
        method_used = "heuristic"

    entities, relationships = await persist_extraction(db, paper, output)
    citation_edges, cited_titles = await build_citation_edges(db, paper)
    return entities, relationships + citation_edges, method_used, cited_titles


async def get_graph_for_paper(db: AsyncSession, paper_id: str) -> dict:
    """Returns the subgraph directly connected to a paper: the paper node
    plus every entity/relationship extracted from it."""
    result = await db.execute(select(Entity).where(Entity.source_paper_id == paper_id))
    entities = result.scalars().all()
    entity_ids = {e.id for e in entities}

    paper_result = await db.execute(select(Paper.title).where(Paper.id == paper_id))
    title = paper_result.scalar_one_or_none()
    if title:
        paper_entity_result = await db.execute(
            select(Entity).where(Entity.entity_type == "paper", Entity.normalized_name == title.strip().lower())
        )
        paper_entity = paper_entity_result.scalar_one_or_none()
        if paper_entity:
            entity_ids.add(paper_entity.id)
            entities = list(entities) + [paper_entity]

    rel_result = await db.execute(
        select(Relationship).where(
            Relationship.source_entity_id.in_(entity_ids) | Relationship.target_entity_id.in_(entity_ids)
        )
    )
    relationships = rel_result.scalars().all()

    return {
        "nodes": [
            {"id": e.id, "type": e.entity_type, "name": e.name, "confidence": e.confidence}
            for e in entities
        ],
        "edges": [
            {
                "source": r.source_entity_id,
                "target": r.target_entity_id,
                "type": r.relationship_type,
                "evidence": r.evidence,
            }
            for r in relationships
        ],
    }
