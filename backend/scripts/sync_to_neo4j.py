#!/usr/bin/env python3
"""
Syncs the relational knowledge graph (kg_entities/kg_relationships in
SQLite/Postgres) into Neo4j, for graph-native traversal, Cypher queries,
and tools like Neo4j Bloom that expect a real graph database.

WRITTEN TO PRODUCTION STANDARD, NOT EXECUTED IN THIS SANDBOX: there's no
Neo4j instance or network access here to run this against. The Cypher
below follows standard, well-documented syntax (MERGE for idempotency,
so re-running this script is always safe and never creates duplicates).
Verify against a real Neo4j instance before relying on it -- see
"Verify" below.

Why a sync script rather than making Neo4j the primary store: the
relational graph (app/models/knowledge_graph.py) is the tested, working
system this whole platform runs on today. Swapping the *primary* datastore
to Neo4j is a bigger architectural change than this session can verify
without a live instance to test the swap against. A sync script gets you
real Neo4j-backed graph exploration today, on a schedule (cron this), with
zero risk to the tested primary path -- see docs/GAP_ANALYSIS.md.

Usage:
    pip install -r requirements-neo4j.txt   # the optional neo4j driver
    export NEO4J_URI=bolt://localhost:7687
    export NEO4J_USER=neo4j
    export NEO4J_PASSWORD=your-password
    python3 scripts/sync_to_neo4j.py

Verify (once you have a Neo4j instance):
    1. Run this script.
    2. In Neo4j Browser: MATCH (n) RETURN count(n);
       Should equal SELECT COUNT(*) FROM kg_entities in your relational DB.
    3. MATCH ()-[r]->() RETURN count(r);
       Should equal SELECT COUNT(*) FROM kg_relationships.
    4. Try a real traversal: MATCH (p:paper)-[:cites]->(cited:paper)
       RETURN p.name, cited.name LIMIT 25;
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.knowledge_graph import Entity, Relationship  # noqa: E402


def _sanitize_label(entity_type: str) -> str:
    """Neo4j node labels can't be parameterized in Cypher (they're part of
    the query structure, not data), so this whitelists against our known
    entity types rather than interpolating arbitrary strings into a query
    -- the one place in this script where raw string formatting into
    Cypher happens, and it's deliberately restricted to a fixed, safe set
    rather than trusting the DB value directly."""
    from app.models.knowledge_graph import ENTITY_TYPES

    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"Unrecognized entity_type '{entity_type}' -- refusing to build a dynamic Cypher label from it")
    return entity_type


async def sync_entities(neo4j_session, entities: list[Entity]) -> int:
    count = 0
    for entity in entities:
        label = _sanitize_label(entity.entity_type)
        # MERGE on (entity_type, id) is idempotent -- re-running this
        # script never creates duplicate nodes.
        await neo4j_session.run(
            f"""
            MERGE (n:{label} {{id: $id}})
            SET n.name = $name,
                n.normalized_name = $normalized_name,
                n.description = $description,
                n.confidence = $confidence,
                n.extraction_method = $extraction_method
            """,
            id=entity.id,
            name=entity.name,
            normalized_name=entity.normalized_name,
            description=entity.description,
            confidence=entity.confidence,
            extraction_method=entity.extraction_method,
        )
        count += 1
    return count


async def sync_relationships(neo4j_session, relationships: list[Relationship]) -> int:
    count = 0
    for rel in relationships:
        # Relationship TYPE also can't be parameterized in Cypher.
        # relationship_type is app-controlled (see RELATIONSHIP_TYPES in
        # models/knowledge_graph.py), not user input, but we still
        # whitelist it defensively rather than trust it blindly.
        from app.models.knowledge_graph import RELATIONSHIP_TYPES

        if rel.relationship_type not in RELATIONSHIP_TYPES:
            raise ValueError(f"Unrecognized relationship_type '{rel.relationship_type}'")

        await neo4j_session.run(
            f"""
            MATCH (source {{id: $source_id}})
            MATCH (target {{id: $target_id}})
            MERGE (source)-[r:{rel.relationship_type}]->(target)
            SET r.evidence = $evidence,
                r.confidence = $confidence
            """,
            source_id=rel.source_entity_id,
            target_id=rel.target_entity_id,
            evidence=rel.evidence,
            confidence=rel.confidence,
        )
        count += 1
    return count


async def main() -> None:
    try:
        from neo4j import AsyncGraphDatabase
    except ImportError:
        print("ERROR: the 'neo4j' package isn't installed. Run: pip install neo4j", file=sys.stderr)
        sys.exit(1)

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        print("ERROR: NEO4J_PASSWORD environment variable is required.", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        entities = (await db.execute(select(Entity))).scalars().all()
        relationships = (await db.execute(select(Relationship))).scalars().all()

    print(f"Read {len(entities)} entities and {len(relationships)} relationships from the relational DB.")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as neo4j_session:
            entity_count = await sync_entities(neo4j_session, entities)
            rel_count = await sync_relationships(neo4j_session, relationships)
    finally:
        await driver.close()

    print(f"Synced {entity_count} entities and {rel_count} relationships to Neo4j at {uri}.")


if __name__ == "__main__":
    asyncio.run(main())
