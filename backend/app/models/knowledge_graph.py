"""
Knowledge graph schema, Phase 2.

Uses a generic Entity/Relationship pair rather than one table per entity
type (Method, Dataset, Task, Claim, ...). This is a deliberate architecture
choice for this phase:

  * It lets the extraction pipeline (heuristic today, LLM-refined once you
    add a key) emit new entity/relationship types without a migration.
  * It maps directly onto a property graph, so swapping the storage layer
    to Neo4j later (mentioned in the original spec) is a data-migration
    exercise, not a schema redesign -- entity_type/relationship_type become
    node labels/edge labels as-is.
  * It scales fine on Postgres/SQLite up to the hundreds-of-thousands of
    nodes range this project will realistically hit; a dedicated graph DB
    is a Phase-5-and-beyond concern, not something to fake now.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, Float, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# Canonical entity types (informational -- not DB-enforced, so the
# extraction pipeline can introduce new ones without a migration):
#   paper | author | method | dataset | task | metric | benchmark | claim | concept
ENTITY_TYPES = [
    "paper", "author", "method", "dataset", "task",
    "metric", "benchmark", "claim", "concept",
]

# Canonical relationship types:
#   cites | proposes | uses_dataset | evaluated_on | improves_on |
#   contradicts | compares_to | authored_by | mentions
RELATIONSHIP_TYPES = [
    "cites", "proposes", "uses_dataset", "evaluated_on", "improves_on",
    "contradicts", "compares_to", "authored_by", "mentions",
]


class Entity(Base):
    __tablename__ = "kg_entities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    entity_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional link back to the paper this entity was extracted from
    # (a Method/Dataset/Claim entity is usually scoped to one source paper).
    source_paper_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("papers.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # How this entity was produced: 'heuristic' or 'llm'. Lets the UI show
    # confidence and lets us re-run only the heuristic-extracted entities
    # once an API key is added, without touching LLM-verified ones.
    extraction_method: Mapped[str] = mapped_column(String, default="heuristic")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    __table_args__ = (
        Index("ix_kg_entities_type_norm", "entity_type", "normalized_name"),
    )


class Relationship(Base):
    __tablename__ = "kg_relationships"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    source_entity_id: Mapped[str] = mapped_column(
        String, ForeignKey("kg_entities.id", ondelete="CASCADE"), index=True
    )
    target_entity_id: Mapped[str] = mapped_column(
        String, ForeignKey("kg_entities.id", ondelete="CASCADE"), index=True
    )
    relationship_type: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # The paper text span (or heuristic rule) that justified this edge --
    # keeps every graph edge traceable to real evidence rather than an
    # unexplained LLM assertion.
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    source_entity: Mapped[Entity] = relationship("Entity", foreign_keys=[source_entity_id])
    target_entity: Mapped[Entity] = relationship("Entity", foreign_keys=[target_entity_id])

    __table_args__ = (
        Index("ix_kg_rel_source_type", "source_entity_id", "relationship_type"),
    )
