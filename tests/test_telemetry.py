from demo_service.telemetry import (
    DEFAULT_ENVIRONMENT,
    DEFAULT_OTLP_ENDPOINT,
    DEFAULT_SERVICE_NAME,
    load_telemetry_config,
)


def test_telemetry_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    monkeypatch.delenv("OTEL_ENVIRONMENT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    config = load_telemetry_config()

    assert config.enabled is False
    assert config.service_name == DEFAULT_SERVICE_NAME
    assert config.environment == DEFAULT_ENVIRONMENT
    assert config.otlp_endpoint == DEFAULT_OTLP_ENDPOINT


def test_telemetry_configuration_can_be_overridden(monkeypatch):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "demo-booking")
    monkeypatch.setenv("OTEL_ENVIRONMENT", "integration-test")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318/")

    config = load_telemetry_config()

    assert config.enabled is True
    assert config.service_name == "demo-booking"
    assert config.environment == "integration-test"
    assert config.otlp_endpoint == "http://collector:4318"
