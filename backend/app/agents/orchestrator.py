"""
Generic sequential pipeline runner -- the "Planning Agent" from the spec,
implemented as pure orchestration logic with no DB/network dependency of
its own, so it's fully unit-testable offline with fake Agent
implementations (see tests/test_orchestrator.py).

The concrete research pipeline (Discovery -> Reading -> Extraction ->
Survey, using real DB/network-backed agents) is assembled in
research_pipeline.py, which composes this runner with the concrete agents.
"""
from __future__ import annotations

from app.agents.base import Agent, AgentContext, AgentResult


class PipelineError(RuntimeError):
    pass


async def run_pipeline(
    agents: list[Agent], context: AgentContext, stop_on_failure: bool = False
) -> list[AgentResult]:
    """Runs each agent in order, threading the same AgentContext through so
    later agents can see earlier agents' output via context.data.

    If stop_on_failure is True, a failed agent halts the pipeline
    immediately (useful when a later stage genuinely can't proceed without
    the earlier one, e.g. extraction needs at least one ingested paper).
    Otherwise all agents run regardless, and callers inspect each
    AgentResult.success individually -- appropriate for fan-out stages
    where one paper failing shouldn't block the others.
    """
    results = [result async for result in run_pipeline_streaming(agents, context, stop_on_failure)]
    return results


async def run_pipeline_streaming(
    agents: list[Agent], context: AgentContext, stop_on_failure: bool = False
):
    """Same execution as run_pipeline, but an async generator yielding each
    AgentResult the moment that agent finishes, instead of collecting them
    all before returning anything. This is what makes real-time progress
    streaming possible (see api/routes/research.py's SSE endpoint) --
    a caller can show "Discovery Agent: done, found 5 papers" the instant
    it happens rather than waiting for the whole multi-minute pipeline to
    finish before the UI updates at all.

    run_pipeline() above is now just this generator drained into a list,
    so both entry points share one execution path -- no duplicated
    control flow to keep in sync.
    """
    for agent in agents:
        context.record(f"Running agent: {agent.name}")
        result = await agent.run(context)
        context.record(f"Agent {agent.name} finished: success={result.success} -- {result.summary}")
        yield result
        if not result.success and stop_on_failure:
            context.record(f"Pipeline halted after {agent.name} failure (stop_on_failure=True)")
            return
