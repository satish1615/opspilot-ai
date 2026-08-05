from time import perf_counter

import pytest
from fastapi.testclient import TestClient

from demo_service.main import app, state


@pytest.fixture(autouse=True)
def reset_demo_state():
    state.reset()
    yield
    state.reset()


@pytest.fixture
def demo_client():
    with TestClient(app) as client:
        yield client


def test_synthetic_service_starts_healthy(demo_client):
    legacy_health = demo_client.get("/health")
    live = demo_client.get("/health/live")
    ready = demo_client.get("/health/ready")
    synthetic_check = demo_client.get("/synthetic/booking-check")
    booking = demo_client.get("/bookings/DEMO-1001")

    assert legacy_health.status_code == 200
    assert legacy_health.json()["status"] == "alive"
    assert live.status_code == 200
    assert live.json()["status"] == "alive"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert synthetic_check.status_code == 200
    assert synthetic_check.json()["status"] == "healthy"
    assert synthetic_check.json()["response_time_ms"] <= 500
    assert booking.status_code == 200
    assert booking.json()["booking_id"] == "DEMO-1001"
    assert booking.json()["passenger"] == "Synthetic Traveller"

    for public_response in (legacy_health, live, ready, synthetic_check):
        assert "mode" not in public_response.json()
        assert "latency_ms" not in public_response.json()


def test_high_latency_keeps_liveness_and_readiness_green_but_breaks_slo(demo_client):
    configured = demo_client.post(
        "/admin/failure-mode",
        json={"mode": "high_latency", "latency_ms": 25},
    )
    assert configured.status_code == 200

    live = demo_client.get("/health/live")
    ready = demo_client.get("/health/ready")

    started = perf_counter()
    booking = demo_client.get("/bookings/DEMO-2002")
    elapsed_ms = (perf_counter() - started) * 1000

    synthetic_check = demo_client.get("/synthetic/booking-check?slo_ms=20")

    assert live.status_code == 200
    assert live.json()["status"] == "alive"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert booking.status_code == 200
    assert booking.json()["service_mode"] == "high_latency"
    assert elapsed_ms >= 20
    assert synthetic_check.status_code == 503
    assert synthetic_check.json()["status"] == "degraded"
    assert synthetic_check.json()["reason"] == "slo_violation"
    assert synthetic_check.json()["response_time_ms"] >= 20


def test_dependency_failure_separates_liveness_from_readiness(demo_client):
    configured = demo_client.post(
        "/admin/failure-mode",
        json={"mode": "dependency_failure", "latency_ms": 1},
    )
    assert configured.status_code == 200

    live = demo_client.get("/health/live")
    ready = demo_client.get("/health/ready")
    synthetic_check = demo_client.get("/synthetic/booking-check")
    booking = demo_client.get("/bookings/DEMO-3003")

    assert live.status_code == 200
    assert live.json()["status"] == "alive"
    assert ready.status_code == 503
    assert ready.json()["status"] == "not_ready"
    assert ready.json()["dependency"] == "synthetic-inventory-service"
    assert synthetic_check.status_code == 503
    assert synthetic_check.json()["status"] == "failed"
    assert synthetic_check.json()["reason"] == "dependency_unavailable"
    assert booking.status_code == 503
    assert "dependency" in booking.json()["detail"].lower()


def test_reset_restores_ready_and_healthy_journey(demo_client):
    demo_client.post(
        "/admin/failure-mode",
        json={"mode": "dependency_failure", "latency_ms": 1},
    )

    reset = demo_client.post("/admin/reset")
    ready = demo_client.get("/health/ready")
    synthetic_check = demo_client.get("/synthetic/booking-check")

    assert reset.status_code == 200
    assert reset.json()["mode"] == "healthy"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert synthetic_check.status_code == 200
    assert synthetic_check.json()["status"] == "healthy"


def test_invalid_failure_configuration_is_rejected(demo_client):
    response = demo_client.post(
        "/admin/failure-mode",
        json={"mode": "high_latency", "latency_ms": 0},
    )

    assert response.status_code == 422


def test_invalid_synthetic_slo_is_rejected(demo_client):
    response = demo_client.get("/synthetic/booking-check?slo_ms=0")

    assert response.status_code == 422
