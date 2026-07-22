# Observability

Prometheus + Grafana configs for AI ResearchOS, plus how to enable
OpenTelemetry tracing. **Written to production standard, not run against
a live Prometheus/Grafana/collector in this environment** -- verify the
steps below once you have them running.

## Metrics (Prometheus + Grafana)

The backend always exposes `/metrics` in Prometheus text format (see
`app/core/metrics_registry.py`) -- no configuration needed for that part;
verify it right now with `curl http://localhost:8000/metrics`.

To visualize it:

```bash
docker run -d --name prometheus -p 9090:9090 \
  -v $(pwd)/observability/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

docker run -d --name grafana -p 3001:3000 grafana/grafana
```

Then in Grafana (http://localhost:3001, default admin/admin):
1. Add a Prometheus data source pointing at `http://prometheus:9090` (or
   `http://host.docker.internal:9090` depending on your Docker network).
2. Import `observability/grafana/dashboard.json`.

Update `observability/prometheus.yml`'s target (`backend:8000`) to match
your actual backend hostname/port if it differs from the docker-compose
service name.

## Distributed tracing (OpenTelemetry)

Off by default -- the backend runs with zero tracing overhead until you
set:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://your-collector:4318/v1/traces
```

Once set, every HTTP request is auto-instrumented (via
`FastAPIInstrumentor`), plus explicit spans around PDF download and
extraction (see `app/core/tracing.py` and its call sites in
`app/services/ingest_service.py`). Point `OTEL_EXPORTER_OTLP_ENDPOINT` at
Jaeger, Grafana Tempo, or any OTLP-compatible collector.

To add a span around any other operation:

```python
from app.core.tracing import span

with span("my_operation", some_attribute=value):
    do_the_work()
```

This is a true no-op when tracing is disabled (tested -- see
`backend/tests/test_tracing.py`), so it's safe to sprinkle throughout the
codebase regardless of whether a collector is configured.
