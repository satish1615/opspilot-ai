import os

os.environ["OPSPILOT_DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_home_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "OpsPilot AI"


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_create_and_read_monitoring_alert(client):
    response = client.post(
        "/alerts",
        json={
            "alert_type": "HIGH_CPU",
            "server": "demo-server-01",
            "value": 95,
            "threshold": 80,
            "severity": "high",
        },
    )
    assert response.status_code == 201
    incident = response.json()
    assert incident["analysis"]["issue_detected"] is True
    assert incident["analysis"]["approval_required"] is True

    lookup = client.get(f"/incidents/{incident['incident_id']}")
    assert lookup.status_code == 200
    assert lookup.json()["incident_id"] == incident["incident_id"]


def test_invalid_alert_returns_422(client):
    response = client.post(
        "/alerts",
        json={"alert_type": "HIGH_CPU", "server": "x", "value": 90, "threshold": 0},
    )
    assert response.status_code == 422


def test_create_human_incident_and_filter_history(client):
    response = client.post(
        "/human-incidents",
        json={
            "title": "Users cannot access email",
            "description": "Several users cannot send or receive email messages.",
            "impact": "medium",
            "urgency": "high",
            "affected_users": 25,
            "workaround_available": False,
        },
    )
    assert response.status_code == 201
    assert response.json()["analysis"]["category"] == "Messaging"

    history = client.get("/incidents?source_type=human_incident")
    assert history.status_code == 200
    assert history.json()["total"] == 1


def test_unknown_incident_returns_404(client):
    response = client.get("/incidents/does-not-exist")
    assert response.status_code == 404


def test_remediation_requires_explicit_approval(client):
    created = client.post(
        "/alerts",
        json={
            "alert_type": "SERVICE_DOWN",
            "server": "demo-api-01",
            "value": 0,
            "threshold": 1,
        },
    ).json()
    assert created["analysis"]["remediation_approved"] is False

    approval = client.post(
        f"/incidents/{created['incident_id']}/approve-remediation",
        json={"approved_by": "Hackathon Reviewer", "note": "Approved for manual recovery only."},
    )
    assert approval.status_code == 200
    assert approval.json()["analysis"]["remediation_approved"] is True
    assert approval.json()["approval"]["execution_status"] == "not_executed"


def test_summary_metrics(client):
    client.post(
        "/alerts",
        json={"alert_type": "HIGH_MEMORY", "server": "demo-01", "value": 91, "threshold": 80},
    )
    client.post(
        "/human-incidents",
        json={
            "title": "VPN access is failing",
            "description": "Multiple users see a timeout while connecting to VPN.",
            "impact": "medium",
            "urgency": "high",
            "affected_users": 10,
        },
    )
    metrics = client.get("/metrics/summary").json()
    assert metrics["total_incidents"] == 2
    assert metrics["monitoring_alerts"] == 1
    assert metrics["human_incidents"] == 1
