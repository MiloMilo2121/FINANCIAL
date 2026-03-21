"""OpenTelemetry tracing setup."""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def configure_tracing(service_name: str) -> None:
    """Configure OpenTelemetry tracing.

    When ENABLE_TRACING=true, exports spans to OTLP endpoint.
    Otherwise, exports to console (for local dev visibility).
    """
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    enable_tracing = os.environ.get("ENABLE_TRACING", "false").lower() == "true"
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")

    if enable_tracing and otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        # Console exporter for local development; no-op in test environments
        if os.environ.get("LOG_LEVEL", "INFO").upper() == "DEBUG":
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)
