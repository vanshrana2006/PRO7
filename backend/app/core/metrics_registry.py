"""
A minimal in-process metrics registry rendering Prometheus text exposition
format. Pure logic (no Starlette/FastAPI types touched here), so counting
and formatting are fully testable offline; the HTTP-layer glue that calls
`record()` per request lives in observability.py's track_request().

For multi-instance deployments, /metrics as implemented here is
per-instance -- the standard approach (each instance is one Prometheus
scrape target) works fine with this; it's not something requiring a
Redis-backed shared counter, so there's no compromise here for horizontal
scaling.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class _Histogram:
    count: int = 0
    total_seconds: float = 0.0
    max_seconds: float = 0.0


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_counts: dict[tuple[str, str, int], int] = {}
        self._latency: dict[tuple[str, str], _Histogram] = {}

    def record(self, method: str, path: str, status: int, duration_seconds: float) -> None:
        with self._lock:
            count_key = (method, path, status)
            self._request_counts[count_key] = self._request_counts.get(count_key, 0) + 1

            latency_key = (method, path)
            hist = self._latency.setdefault(latency_key, _Histogram())
            hist.count += 1
            hist.total_seconds += duration_seconds
            hist.max_seconds = max(hist.max_seconds, duration_seconds)

    def render_prometheus(self) -> str:
        lines = [
            "# HELP researchos_http_requests_total Total HTTP requests processed",
            "# TYPE researchos_http_requests_total counter",
        ]
        with self._lock:
            for (method, path, status), count in sorted(self._request_counts.items()):
                lines.append(
                    f'researchos_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
                )

            lines.append("# HELP researchos_http_request_duration_seconds_sum Total time spent handling requests")
            lines.append("# TYPE researchos_http_request_duration_seconds_sum counter")
            for (method, path), hist in sorted(self._latency.items()):
                lines.append(
                    f'researchos_http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {hist.total_seconds:.6f}'
                )

            lines.append("# HELP researchos_http_request_duration_seconds_count Count of measured requests")
            lines.append("# TYPE researchos_http_request_duration_seconds_count counter")
            for (method, path), hist in sorted(self._latency.items()):
                lines.append(
                    f'researchos_http_request_duration_seconds_count{{method="{method}",path="{path}"}} {hist.count}'
                )

            lines.append("# HELP researchos_http_request_duration_seconds_max Max observed request duration")
            lines.append("# TYPE researchos_http_request_duration_seconds_max gauge")
            for (method, path), hist in sorted(self._latency.items()):
                lines.append(
                    f'researchos_http_request_duration_seconds_max{{method="{method}",path="{path}"}} {hist.max_seconds:.6f}'
                )

        return "\n".join(lines) + "\n"


registry = MetricsRegistry()
