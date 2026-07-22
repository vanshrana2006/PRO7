from __future__ import annotations

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    type: str
    name: str
    confidence: float


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    evidence: str | None = None


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ExtractResponse(BaseModel):
    paper_id: str
    method_used: str  # 'heuristic' or 'llm'
    entities_created: int
    relationships_created: int
