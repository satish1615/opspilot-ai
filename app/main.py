"""FastAPI application for OpsPilot AI."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from app.agent import run_investigation
from app.analyzer import analyze_human_incident, analyze_monitoring_alert
from app.database import database_is_healthy, initialise_database
from app.knowledge import RUNBOOKS
from app.schemas import (
    HumanIncidentCreate,
    IncidentListResponse,
    IncidentResponse,
    InvestigationResponse,
    MonitoringAlertCreate,
    RemediationApprovalRequest,
)
from app.storage import (
    approve_remediation,
    find_similar_incidents,
    get_incident,
    list_incidents,
    save_incident,
    summary_metrics,
)

APP_VERSION = "1.1.0"
DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "dashboard" / "index.html"


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialise_database()
    yield


app = FastAPI(
    title="OpsPilot AI",
    description=(
        "A safe incident-triage platform for monitoring alerts and human-created incidents. "
        "It combines deterministic analysis, priority classification, sanitised runbook evidence, "
        "incident history, human approval controls, and an evidence-first LangGraph investigation workflow."
    ),
    version=APP_VERSION,
    lifespan=lifespan,
)


@app.get("/")
def home() -> dict:
    return {
        "name": "OpsPilot AI",
        "version": APP_VERSION,
        "status": "running",
        "documentation": "/docs",
        "dashboard": "/dashboard",
    }


@app.get("/health")
def health_check() -> dict:
    healthy = database_is_healthy()
    if not healthy:
        raise HTTPException(status_code=503, detail="Database health check failed")
    return {"status": "healthy", "database": "connected", "version": APP_VERSION}


@app.post("/alerts", response_model=IncidentResponse, status_code=201)
def receive_alert(alert: MonitoringAlertCreate) -> dict:
    analysis = analyze_monitoring_alert(
        alert_type=alert.alert_type,
        value=alert.value,
        threshold=alert.threshold,
        reported_severity=alert.severity,
    )
    analysis["similar_incidents"] = find_similar_incidents(
        text=f"{analysis['title']} {analysis['description']}",
        category=analysis["category"],
    )

    payload = {
        "incident_id": str(uuid4()),
        "source_type": "monitoring_alert",
        "status": "analysed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": analysis.pop("title"),
        "description": analysis.pop("description"),
        "server": alert.server,
        "business_service": alert.business_service,
        "alert_type": alert.alert_type,
        "metric_value": alert.value,
        "threshold": alert.threshold,
        "reported_severity": alert.severity,
        "analysis": analysis,
    }
    return save_incident(payload)


@app.post("/human-incidents", response_model=IncidentResponse, status_code=201)
def receive_human_incident(incident: HumanIncidentCreate) -> dict:
    analysis = analyze_human_incident(
        title=incident.title,
        description=incident.description,
        impact=incident.impact,
        urgency=incident.urgency,
        affected_users=incident.affected_users,
        workaround_available=incident.workaround_available,
    )
    analysis["similar_incidents"] = find_similar_incidents(
        text=f"{incident.title} {incident.description}",
        category=analysis["category"],
    )

    payload = {
        "incident_id": str(uuid4()),
        "source_type": "human_incident",
        "status": "analysed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": analysis.pop("title"),
        "description": analysis.pop("description"),
        "business_service": incident.business_service,
        "impact": incident.impact,
        "urgency": incident.urgency,
        "affected_users": incident.affected_users,
        "workaround_available": incident.workaround_available,
        "analysis": analysis,
    }
    return save_incident(payload)


@app.get("/incidents", response_model=IncidentListResponse)
def read_incidents(
    source_type: Literal["monitoring_alert", "human_incident"] | None = None,
    priority: Literal["P1", "P2", "P3", "P4"] | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    incidents = list_incidents(source_type=source_type, priority=priority, status=status, limit=limit)
    return {"total": len(incidents), "incidents": incidents}


@app.get("/incidents/{incident_id}", response_model=IncidentResponse)
def read_incident(incident_id: str) -> dict:
    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.post("/incidents/{incident_id}/investigate", response_model=InvestigationResponse)
def investigate_incident(incident_id: str) -> dict:
    """Run the evidence-first LangGraph workflow for a persisted incident."""

    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return run_investigation(incident)


@app.post("/incidents/{incident_id}/approve-remediation", response_model=IncidentResponse)
def approve_incident_remediation(incident_id: str, approval: RemediationApprovalRequest) -> dict:
    incident = approve_remediation(incident_id, approval.approved_by, approval.note)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.get("/metrics/summary")
def metrics_summary() -> dict:
    return summary_metrics()


@app.get("/runbooks")
def list_runbooks() -> dict:
    public_runbooks = [
        {
            "runbook_id": item["runbook_id"],
            "title": item["title"],
            "safe_first_steps": item["safe_first_steps"],
        }
        for item in RUNBOOKS
    ]
    return {"total": len(public_runbooks), "runbooks": public_runbooks}


@app.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    if not DASHBOARD_PATH.exists():
        raise HTTPException(status_code=404, detail="Dashboard file not found")
    return FileResponse(DASHBOARD_PATH)
