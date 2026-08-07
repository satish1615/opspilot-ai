"""OpenTelemetry bootstrap for the synthetic booking service.

Telemetry export is opt-in so the normal test suite does not depend on a running
collector. Set OTEL_ENABLED=true when running the Sprint 7 observability stack.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


DEFAULT_SERVICE_NAME = "opspilot-synthetic-booking"
DEFAULT_OTLP_ENDPOINT = "http://localhost:4318"
DEFAULT_ENVIRONMENT = "hackathon-demo"


@dataclass(frozen=True)
class TelemetryConfig:
    """Resolved telemetry settings exposed for diagnostics and documentation."""

    enabled: bool
    service_name: str
    environment: str
    otlp_endpoint: str


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_telemetry_config() -> TelemetryConfig:
    """Load OpenTelemetry settings from environment variables."""

    return TelemetryConfig(
        enabled=_env_flag("OTEL_ENABLED", default=False),
        service_name=os.getenv("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME),
        environment=os.getenv("OTEL_ENVIRONMENT", DEFAULT_ENVIRONMENT),
        otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTLP_ENDPOINT).rstrip("/"),
    )


def configure_telemetry(app: FastAPI) -> TelemetryConfig:
    """Instrument FastAPI and export traces/metrics to an OTLP HTTP collector.

    The collector is intentionally optional. Keeping telemetry disabled by default
    lets unit tests and the Sprint 6 demo run without external infrastructure.
    """

    config = load_telemetry_config()
    if not config.enabled:
        return config

    resource = Resource.create(
        {
            "service.name": config.service_name,
            "service.version": app.version,
            "deployment.environment.name": config.environment,
            "opspilot.component": "synthetic-workload",
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{config.otlp_endpoint}/v1/traces")
        )
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{config.otlp_endpoint}/v1/metrics"),
        export_interval_millis=5_000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        excluded_urls=r"/docs.*,/openapi.json,/health/live",
    )

    return config
