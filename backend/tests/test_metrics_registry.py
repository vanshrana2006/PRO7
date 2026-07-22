"""
Offline tests for MetricsRegistry.

Run with:  python3 -m unittest tests.test_metrics_registry -v
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.core.metrics_registry import MetricsRegistry  # noqa: E402


class TestMetricsRegistry(unittest.TestCase):
    def test_records_request_count(self):
        reg = MetricsRegistry()
        reg.record("GET", "/api/health", 200, 0.01)
        output = reg.render_prometheus()
        self.assertIn('researchos_http_requests_total{method="GET",path="/api/health",status="200"} 1', output)

    def test_increments_count_for_repeated_requests(self):
        reg = MetricsRegistry()
        reg.record("GET", "/api/health", 200, 0.01)
        reg.record("GET", "/api/health", 200, 0.02)
        output = reg.render_prometheus()
        self.assertIn('researchos_http_requests_total{method="GET",path="/api/health",status="200"} 2', output)

    def test_separate_status_codes_tracked_independently(self):
        reg = MetricsRegistry()
        reg.record("POST", "/api/papers/ingest", 200, 0.5)
        reg.record("POST", "/api/papers/ingest", 502, 0.3)
        output = reg.render_prometheus()
        self.assertIn('status="200"} 1', output)
        self.assertIn('status="502"} 1', output)

    def test_latency_sum_accumulates(self):
        reg = MetricsRegistry()
        reg.record("GET", "/x", 200, 1.0)
        reg.record("GET", "/x", 200, 2.0)
        output = reg.render_prometheus()
        self.assertIn("researchos_http_request_duration_seconds_sum", output)
        self.assertIn('{method="GET",path="/x"} 3.000000', output)

    def test_latency_max_tracks_maximum(self):
        reg = MetricsRegistry()
        reg.record("GET", "/x", 200, 1.0)
        reg.record("GET", "/x", 200, 5.0)
        reg.record("GET", "/x", 200, 2.0)
        output = reg.render_prometheus()
        self.assertIn('researchos_http_request_duration_seconds_max{method="GET",path="/x"} 5.000000', output)

    def test_output_contains_help_and_type_lines(self):
        reg = MetricsRegistry()
        output = reg.render_prometheus()
        self.assertIn("# HELP researchos_http_requests_total", output)
        self.assertIn("# TYPE researchos_http_requests_total counter", output)

    def test_empty_registry_still_renders_valid_output(self):
        reg = MetricsRegistry()
        output = reg.render_prometheus()
        self.assertIsInstance(output, str)
        self.assertTrue(output.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
