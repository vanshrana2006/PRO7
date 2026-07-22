"""
Offline tests for app.core.tracing -- specifically that it's a true no-op
when tracing is disabled (the default), which is the one thing about this
module that's actually testable without the opentelemetry packages
installed (this module only imports them inside setup_tracing()'s try
block, never at module level).

Run with:  python3 -m unittest tests.test_tracing -v
"""
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.core.tracing import setup_tracing, span  # noqa: E402


class TestSpanNoOp(unittest.TestCase):
    def test_span_context_manager_yields_without_error(self):
        with span("test_operation"):
            result = 1 + 1
        self.assertEqual(result, 2)

    def test_span_accepts_attributes_without_error_when_disabled(self):
        with span("test_operation", paper_id="abc123", count=5):
            pass  # should not raise even though no tracer is configured

    def test_exception_inside_span_propagates_normally(self):
        with self.assertRaises(ValueError):
            with span("test_operation"):
                raise ValueError("something went wrong")

    def test_nested_spans_work_when_disabled(self):
        with span("outer"):
            with span("inner"):
                pass


class TestSetupTracingNoOp(unittest.TestCase):
    def test_setup_tracing_is_a_safe_no_op_without_otlp_endpoint(self):
        os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
        # Should not raise even with a dummy "app" object, since it returns
        # immediately when the env var isn't set.
        setup_tracing(app=object(), service_name="test-service")


if __name__ == "__main__":
    unittest.main()
