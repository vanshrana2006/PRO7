"""
Base classes for the multi-agent research system.

Deliberately hand-rolled rather than pulling in LangGraph: the orchestration
this platform needs -- a fixed pipeline of discover -> read -> extract ->
synthesize, with per-paper fan-out -- doesn't need a graph-execution engine
to be correct or extensible, and a plain async pipeline is something I can
actually unit-test in this offline sandbox with fake agents. If your use
case grows into genuinely dynamic agent routing later, this Agent interface
is the natural seam to swap in LangGraph without touching call sites.

Every agent:
  * declares a `name` for logging/tracing
  * implements `async def run(self, context: AgentContext) -> AgentResult`
  * NEVER raises past its own boundary for expected failure modes (a search
    returning zero results, an ingest failing) -- it returns an AgentResult
    with success=False and a reason, so the orchestrator can decide whether
    to continue the pipeline for other papers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    """Shared state threaded through the pipeline. Agents read what they
    need and write their output into `data` under their own namespaced key
    -- keeps agents decoupled from each other's internal shapes."""

    query: str
    data: dict[str, Any] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)

    def record(self, message: str) -> None:
        self.log.append(message)


@dataclass
class AgentResult:
    agent_name: str
    success: bool
    summary: str
    output: Any = None


class Agent:
    name: str = "base_agent"

    async def run(self, context: AgentContext) -> AgentResult:  # pragma: no cover - interface
        raise NotImplementedError
