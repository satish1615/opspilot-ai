from datetime import datetime, timezone

import httpx
from fastapi.testclient import TestClient

from app.agent.investigation import run_investigation
from app.agent.observability import ObservabilityConfig, gather_observability_evidence
from app.main import app


def _sample_incident() -> dict:
    return {
        "incident_id": "INC-SPRINT8-001",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "analysis": {
            "issue_detected": True,
            "probable_cause": "CPU contention may be increasing request latency.",
            "recommended_action": "Inspect top CPU-consuming processes and recent changes.",
            "confidence": 90,
            "evidence": [
                {
                    "runbook_id": "RB-CPU-001",
                    "title": "High CPU investigation",
                    "matched_keywords": ["cpu"],
                    "safe_first_steps": ["Inspect top CPU-consuming processes."],
                }
            ],
            "similar_incidents": [],
        },
    }


def test_langgraph_investigation_runs_expected_steps(monkeypatch):
    monkeypatch.setenv("OPSPILOT_OBSERVABILITY_ENABLED", "false")
    result = run_investigation(_sample_incident())

    assert result["incident_id"] == "INC-SPRINT8-001"
    assert result["workflow"] == "langgraph_incident_investigation_v1"
    assert result["reasoning_mode"] == "deterministic_foundation"
    assert result["status"] == "grounded_baseline"
    assert result["steps"] == [
        "collect_incident_context",
        "collect_observability_evidence",
        "build_initial_hypothesis",
        "validate_grounding",
    ]
    assert result["evidence_count"] == 1
    assert result["telemetry_evidence_count"] == 0
    assert result["observability"]["status"] == "disabled"
    assert result["hypothesis"]["confidence"] == 90


def test_observability_collector_parses_tempo_mimir_and_loki():
    config = ObservabilityConfig(
        enabled=True,
        service_name="opspilot-synthetic-booking",
        tempo_url="http://tempo",
        mimir_url="http://mimir/prometheus",
        loki_url="http://loki",
        lookback_minutes=15,
        timeout_seconds=1.0,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/search":
            return httpx.Response(
                200,
                json={
                    "traces": [
                        {
                            "traceID": "trace-123",
                            "rootTraceName": "GET /synthetic/booking-check",
                            "durationMs": 1501.14,
                        }
                    ]
                },
            )
        if request.url.path == "/prometheus/api/v1/query":
            query = request.url.params.get("query", "")
            value = "2" if "http_response_status_code" in query else "1500.5"
            return httpx.Response(
                200,
                json={"status": "success", "data": {"result": [{"value": [0, value]}]}},
            )
        if request.url.path == "/loki/api/v1/query_range":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "result": [
                            {
                                "stream": {"severity_text": "WARN"},
                                "values": [
                                    ["1", "Synthetic booking check breached the configured SLO"]
                                ],
                            }
                        ]
                    },
                },
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = gather_observability_evidence(_sample_incident(), config=config, client=client)

    assert result["status"] == "available"
    assert result["sources"] == {
        "tempo": "available",
        "mimir": "available",
        "loki": "available",
    }
    assert {item["source"] for item in result["evidence"]} == {"tempo", "mimir", "loki"}
    assert any(
        item["details"].get("duration_ms") == 1501.14 for item in result["evidence"]
    )
    assert any(
        item["details"].get("metric") == "p95_http_duration_ms" for item in result["evidence"]
    )


def test_observability_collector_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OPSPILOT_OBSERVABILITY_ENABLED", raising=False)
    result = gather_observability_evidence(_sample_incident())

    assert result["status"] == "disabled"
    assert result["evidence"] == []
    assert result["sources"]["tempo"] == "disabled"


def test_investigation_endpoint_uses_persisted_incident(monkeypatch):
    monkeypatch.setenv("OPSPILOT_OBSERVABILITY_ENABLED", "false")
    with TestClient(app) as client:
        created = client.post(
            "/alerts",
            json={
                "alert_type": "HIGH_CPU",
                "server": "sprint8-demo-server",
                "business_service": "Synthetic Booking",
                "value": 92,
                "threshold": 80,
                "severity": "high",
            },
        )
        assert created.status_code == 201

        incident_id = created.json()["incident_id"]
        investigated = client.post(f"/incidents/{incident_id}/investigate")

    assert investigated.status_code == 200
    body = investigated.json()
    assert body["incident_id"] == incident_id
    assert body["workflow"] == "langgraph_incident_investigation_v1"
    assert body["reasoning_mode"] == "deterministic_foundation"
    assert body["status"] == "grounded_baseline"
    assert body["evidence_count"] >= 1
    assert body["telemetry_evidence_count"] == 0
    assert body["observability"]["status"] == "disabled"
    assert body["hypothesis"]["root_cause"]


def test_investigation_endpoint_returns_404_for_unknown_incident(monkeypatch):
    monkeypatch.setenv("OPSPILOT_OBSERVABILITY_ENABLED", "false")
    with TestClient(app) as client:
        response = client.post("/incidents/does-not-exist/investigate")

    assert response.status_code == 404
    assert response.json()["detail"] == "Incident not found"
