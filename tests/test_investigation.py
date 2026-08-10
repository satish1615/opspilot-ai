from fastapi.testclient import TestClient

from app.agent.investigation import run_investigation
from app.main import app


def _sample_incident() -> dict:
    return {
        "incident_id": "INC-SPRINT8-001",
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


def test_langgraph_investigation_runs_expected_steps():
    result = run_investigation(_sample_incident())

    assert result["incident_id"] == "INC-SPRINT8-001"
    assert result["workflow"] == "langgraph_incident_investigation_v1"
    assert result["reasoning_mode"] == "deterministic_foundation"
    assert result["status"] == "grounded_baseline"
    assert result["steps"] == [
        "collect_incident_context",
        "build_initial_hypothesis",
        "validate_grounding",
    ]
    assert result["evidence_count"] == 1
    assert result["hypothesis"]["confidence"] == 90


def test_investigation_endpoint_uses_persisted_incident():
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
    assert body["hypothesis"]["root_cause"]


def test_investigation_endpoint_returns_404_for_unknown_incident():
    with TestClient(app) as client:
        response = client.post("/incidents/does-not-exist/investigate")

    assert response.status_code == 404
    assert response.json()["detail"] == "Incident not found"
