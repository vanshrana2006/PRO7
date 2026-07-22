"""
Offline tests for the pipeline orchestrator, using fake Agent
implementations -- exercises real orchestration logic (ordering, context
threading, stop_on_failure behavior) with zero DB/network dependency.

Run with:  python3 -m unittest tests.test_orchestrator -v
"""
import asyncio
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.agents.base import Agent, AgentContext, AgentResult  # noqa: E402
from app.agents.orchestrator import run_pipeline, run_pipeline_streaming  # noqa: E402


class WriteValueAgent(Agent):
    """Writes a fixed value into context.data under its own name."""

    def __init__(self, name: str, value, succeed: bool = True):
        self.name = name
        self.value = value
        self.succeed = succeed

    async def run(self, context: AgentContext) -> AgentResult:
        context.data[self.name] = self.value
        return AgentResult(agent_name=self.name, success=self.succeed, summary=f"wrote {self.value}", output=self.value)


class ReadPreviousAgent(Agent):
    """Reads a value written by an earlier agent, to verify context threading."""

    def __init__(self, name: str, reads_key: str):
        self.name = name
        self.reads_key = reads_key

    async def run(self, context: AgentContext) -> AgentResult:
        seen = context.data.get(self.reads_key)
        return AgentResult(agent_name=self.name, success=seen is not None, summary=f"saw {seen}", output=seen)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestPipelineOrchestrator(unittest.TestCase):
    def test_runs_agents_in_order(self):
        context = AgentContext(query="test query")
        order: list[str] = []

        class TrackingAgent(Agent):
            def __init__(self, name):
                self.name = name

            async def run(self, ctx):
                order.append(self.name)
                return AgentResult(agent_name=self.name, success=True, summary="ok")

        agents = [TrackingAgent("first"), TrackingAgent("second"), TrackingAgent("third")]
        run_async(run_pipeline(agents, context))
        self.assertEqual(order, ["first", "second", "third"])

    def test_context_data_threads_between_agents(self):
        context = AgentContext(query="graph neural networks")
        agents = [WriteValueAgent("discovery", value=["paper1", "paper2"]), ReadPreviousAgent("reader", reads_key="discovery")]
        results = run_async(run_pipeline(agents, context))
        self.assertTrue(results[1].success)
        self.assertEqual(results[1].output, ["paper1", "paper2"])

    def test_all_agents_run_by_default_even_after_failure(self):
        context = AgentContext(query="q")
        agents = [
            WriteValueAgent("a", value=1, succeed=False),
            WriteValueAgent("b", value=2, succeed=True),
        ]
        results = run_async(run_pipeline(agents, context))
        self.assertEqual(len(results), 2)
        self.assertFalse(results[0].success)
        self.assertTrue(results[1].success)

    def test_stop_on_failure_halts_pipeline(self):
        context = AgentContext(query="q")
        agents = [
            WriteValueAgent("a", value=1, succeed=False),
            WriteValueAgent("b", value=2, succeed=True),
        ]
        results = run_async(run_pipeline(agents, context, stop_on_failure=True))
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].success)

    def test_context_log_records_each_agent(self):
        context = AgentContext(query="q")
        agents = [WriteValueAgent("solo", value=42)]
        run_async(run_pipeline(agents, context))
        joined_log = " ".join(context.log)
        self.assertIn("Running agent: solo", joined_log)
        self.assertIn("Agent solo finished", joined_log)

    def test_empty_agent_list_returns_empty_results(self):
        context = AgentContext(query="q")
        results = run_async(run_pipeline([], context))
        self.assertEqual(results, [])


class TestPipelineStreaming(unittest.TestCase):
    """The streaming generator is the actual code path SSE progress
    (api/routes/research.py) depends on -- tested directly here rather
    than only indirectly through run_pipeline()'s list-draining wrapper."""

    def test_yields_each_result_incrementally(self):
        context = AgentContext(query="q")
        agents = [WriteValueAgent("a", value=1), WriteValueAgent("b", value=2)]

        async def collect():
            yielded = []
            async for result in run_pipeline_streaming(agents, context):
                yielded.append(result.agent_name)
            return yielded

        names = run_async(collect())
        self.assertEqual(names, ["a", "b"])

    def test_context_is_updated_between_yields(self):
        # Verifies later agents see earlier agents' writes even though
        # we're consuming results one at a time rather than all at once --
        # the exact behavior real streaming callers depend on.
        context = AgentContext(query="q")
        agents = [WriteValueAgent("discovery", value=["p1"]), ReadPreviousAgent("reader", reads_key="discovery")]

        async def collect():
            results = []
            async for result in run_pipeline_streaming(agents, context):
                results.append(result)
            return results

        results = run_async(collect())
        self.assertEqual(results[1].output, ["p1"])

    def test_stop_on_failure_stops_the_generator_early(self):
        context = AgentContext(query="q")
        agents = [
            WriteValueAgent("a", value=1, succeed=False),
            WriteValueAgent("b", value=2, succeed=True),
        ]

        async def collect():
            return [r async for r in run_pipeline_streaming(agents, context, stop_on_failure=True)]

        results = run_async(collect())
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].success)

    def test_run_pipeline_and_streaming_produce_identical_results(self):
        # run_pipeline() is now just run_pipeline_streaming() drained into
        # a list -- verify that refactor didn't change behavior.
        context_a = AgentContext(query="q")
        context_b = AgentContext(query="q")
        agents_a = [WriteValueAgent("x", value=1), WriteValueAgent("y", value=2)]
        agents_b = [WriteValueAgent("x", value=1), WriteValueAgent("y", value=2)]

        list_results = run_async(run_pipeline(agents_a, context_a))

        async def collect():
            return [r async for r in run_pipeline_streaming(agents_b, context_b)]

        streamed_results = run_async(collect())

        self.assertEqual(
            [(r.agent_name, r.success, r.output) for r in list_results],
            [(r.agent_name, r.success, r.output) for r in streamed_results],
        )

    def test_empty_agent_list_yields_nothing(self):
        context = AgentContext(query="q")

        async def collect():
            return [r async for r in run_pipeline_streaming([], context)]

        self.assertEqual(run_async(collect()), [])


if __name__ == "__main__":
    unittest.main()
