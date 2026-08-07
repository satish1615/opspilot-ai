"""OpenTelemetry bootstrap for the synthetic booking service.

Telemetry export is opt-in so the normal test suite does not depend on a running
collector. Set OTEL_ENABLED=true when running the Sprint 7 observability stack.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


DEFAULT_SERVICE_NAME = "opspilot-synthetic-booking"
DEFAULT_OTLP_ENDPOINT = "http://localhost:4318"
DEFAULT_ENVIRONMENT = "hackathon-demo"
APP_LOGGER_NAME = "opspilot.synthetic_booking"

_application_logger = logging.getLogger(APP_LOGGER_NAME)
_application_logger.setLevel(logging.INFO)
_application_logger.propagate = False
if not _application_logger.handlers:
    _application_logger.addHandler(logging.NullHandler())

_logger_provider: LoggerProvider | None = None


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


def get_application_logger() -> logging.Logger:
    """Return the synthetic-service logger used for incident-relevant events."""

    return _application_logger


def configure_telemetry(app: FastAPI) -> TelemetryConfig:
    """Instrument FastAPI and export traces, metrics, and logs over OTLP HTTP.

    The collector is intentionally optional. Keeping telemetry disabled by default
    lets unit tests and the Sprint 6 demo run without external infrastructure.
    """

    global _logger_provider

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

    _logger_provider = LoggerProvider(resource=resource)
    _logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(
            OTLPLogExporter(endpoint=f"{config.otlp_endpoint}/v1/logs")
        )
    )
    if not any(isinstance(handler, LoggingHandler) for handler in _application_logger.handlers):
        _application_logger.addHandler(
            LoggingHandler(level=logging.INFO, logger_provider=_logger_provider)
        )

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        excluded_urls=r"/docs.*,/openapi.json,/health/live",
    )

    return config
