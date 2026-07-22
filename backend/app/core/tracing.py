"""
OpenTelemetry tracing setup.

WRITTEN TO PRODUCTION STANDARD, NOT EXECUTED IN THIS SANDBOX: the
`opentelemetry-*` packages aren't installable here (no network/pip). The
API usage below follows the standard OTel Python SDK (TracerProvider,
BatchSpanProcessor, OTLP HTTP exporter) exactly as documented -- verify
with a real collector (Jaeger, Tempo, or your APM vendor's OTLP endpoint)
per the "Verify" steps in docs/ARCHITECTURE.md's Observability section.

Design: tracing is entirely optional and off by default (no
OTEL_EXPORTER_OTLP_ENDPOINT configured => a no-op tracer is used), same
"never require infrastructure that isn't there" principle as the
LLM-optional and auth-optional patterns elsewhere in this codebase.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

_tracer = None


def setup_tracing(app, service_name: str = "ai-researchos-backend") -> None:
    """Call once from main.py's lifespan. No-ops cleanly if
    OTEL_EXPORTER_OTLP_ENDPOINT isn't set, or if the opentelemetry
    packages aren't installed -- tracing is additive, never required."""
    global _tracer

    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not otlp_endpoint:
        return  # tracing disabled; _tracer stays None, span() below no-ops

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        # opentelemetry-* not installed -- degrade to no tracing rather
        # than crash the whole app over an observability dependency.
        return

    resource = Resource(attributes={SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)  # auto-spans every HTTP request

    _tracer = trace.get_tracer(service_name)


@contextmanager
def span(name: str, **attributes):
    """Wraps a block of code in a span if tracing is enabled, otherwise a
    true no-op context manager -- call sites (ingest_service.py,
    graph_service.py, agents/*.py) use this unconditionally without
    checking whether tracing is on.

    Usage:
        with span("pdf_extraction", paper_id=paper.id):
            result = extract_pdf(path)
    """
    if _tracer is None:
        yield
        return

    with _tracer.start_as_current_span(name) as current_span:
        for key, value in attributes.items():
            current_span.set_attribute(key, value)
        yield
