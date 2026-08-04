"""Persistence and incident-history operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.database import SessionLocal
from app.knowledge import tokenise
from app.models import Incident


def _json_loads(value: str | None) -> list:
    if not value:
        return []
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []
    except json.JSONDecodeError:
        return []


def incident_to_dict(incident: Incident) -> dict:
    monitoring_input = {
        "alert_type": incident.alert_type,
        "server": incident.server,
        "value": incident.metric_value,
        "threshold": incident.threshold,
        "severity": incident.reported_severity,
        "business_service": incident.business_service,
    }
    human_input = {
        "title": incident.title,
        "description": incident.description,
        "impact": incident.impact,
        "urgency": incident.urgency,
        "affected_users": incident.affected_users,
        "business_service": incident.business_service,
        "workaround_available": incident.workaround_available,
    }

    return {
        "incident_id": incident.incident_id,
        "source_type": incident.source_type,
        "status": incident.status,
        "created_at": incident.created_at,
        "input": monitoring_input if incident.source_type == "monitoring_alert" else human_input,
        "analysis": {
            "issue_detected": incident.issue_detected,
            "technical_severity": incident.technical_severity,
            "priority": incident.priority,
            "category": incident.category,
            "subcategory": incident.subcategory,
            "assignment_group": incident.assignment_group,
            "probable_cause": incident.probable_cause,
            "recommended_action": incident.recommended_action,
            "confidence": incident.confidence,
            "evidence": _json_loads(incident.evidence_json),
            "similar_incidents": _json_loads(incident.similar_incidents_json),
            "approval_required": incident.approval_required,
            "remediation_approved": incident.remediation_approved,
        },
        "approval": {
            "approved": incident.remediation_approved,
            "approved_by": incident.approved_by,
            "note": incident.approval_note,
            "approved_at": incident.approved_at,
            "execution_status": "not_executed",
        },
    }


def save_incident(payload: dict) -> dict:
    with SessionLocal() as session:
        incident = Incident(
            incident_id=payload["incident_id"],
            source_type=payload["source_type"],
            status=payload["status"],
            created_at=payload["created_at"],
            title=payload["title"],
            description=payload["description"],
            server=payload.get("server"),
            business_service=payload.get("business_service"),
            alert_type=payload.get("alert_type"),
            metric_value=payload.get("metric_value"),
            threshold=payload.get("threshold"),
            reported_severity=payload.get("reported_severity"),
            impact=payload.get("impact"),
            urgency=payload.get("urgency"),
            affected_users=payload.get("affected_users"),
            workaround_available=payload.get("workaround_available"),
            issue_detected=payload["analysis"]["issue_detected"],
            technical_severity=payload["analysis"]["technical_severity"],
            priority=payload["analysis"]["priority"],
            category=payload["analysis"]["category"],
            subcategory=payload["analysis"]["subcategory"],
            assignment_group=payload["analysis"]["assignment_group"],
            probable_cause=payload["analysis"]["probable_cause"],
            recommended_action=payload["analysis"]["recommended_action"],
            confidence=payload["analysis"]["confidence"],
            evidence_json=json.dumps(payload["analysis"].get("evidence", [])),
            similar_incidents_json=json.dumps(payload["analysis"].get("similar_incidents", [])),
            approval_required=payload["analysis"].get("approval_required", True),
            remediation_approved=False,
        )
        session.add(incident)
        session.commit()
        session.refresh(incident)
        return incident_to_dict(incident)


def list_incidents(
    source_type: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict]:
    with SessionLocal() as session:
        statement = select(Incident).order_by(Incident.created_at.desc()).limit(limit)
        if source_type:
            statement = statement.where(Incident.source_type == source_type)
        if priority:
            statement = statement.where(Incident.priority == priority)
        if status:
            statement = statement.where(Incident.status == status)
        incidents = session.scalars(statement).all()
        return [incident_to_dict(incident) for incident in incidents]


def get_incident(incident_id: str) -> dict | None:
    with SessionLocal() as session:
        incident = session.get(Incident, incident_id)
        return incident_to_dict(incident) if incident else None


def find_similar_incidents(text: str, category: str, limit: int = 3) -> list[dict]:
    target_tokens = tokenise(text)
    if not target_tokens:
        return []

    with SessionLocal() as session:
        incidents = session.scalars(
            select(Incident).order_by(Incident.created_at.desc()).limit(200)
        ).all()

    ranked: list[tuple[int, Incident]] = []
    for incident in incidents:
        candidate_tokens = tokenise(f"{incident.title} {incident.description}")
        overlap = len(target_tokens.intersection(candidate_tokens))
        if incident.category == category:
            overlap += 2
        if overlap > 0:
            ranked.append((overlap, incident))

    ranked.sort(key=lambda item: (-item[0], item[1].created_at), reverse=False)
    highest = ranked[0][0] if ranked else 1
    return [
        {
            "incident_id": incident.incident_id,
            "title": incident.title,
            "category": incident.category,
            "priority": incident.priority,
            "similarity_score": min(100, round((score / max(highest, 1)) * 100)),
        }
        for score, incident in ranked[:limit]
    ]


def approve_remediation(incident_id: str, approved_by: str, note: str | None) -> dict | None:
    with SessionLocal() as session:
        incident = session.get(Incident, incident_id)
        if incident is None:
            return None
        incident.remediation_approved = True
        incident.approved_by = approved_by
        incident.approval_note = note
        incident.approved_at = datetime.now(timezone.utc).isoformat()
        incident.status = "approved_for_manual_action"
        session.commit()
        session.refresh(incident)
        return incident_to_dict(incident)


def summary_metrics() -> dict:
    with SessionLocal() as session:
        total = session.scalar(select(func.count()).select_from(Incident)) or 0
        alerts = session.scalar(
            select(func.count()).select_from(Incident).where(Incident.source_type == "monitoring_alert")
        ) or 0
        human = session.scalar(
            select(func.count()).select_from(Incident).where(Incident.source_type == "human_incident")
        ) or 0
        critical = session.scalar(
            select(func.count()).select_from(Incident).where(Incident.priority == "P1")
        ) or 0
        approvals_pending = session.scalar(
            select(func.count()).select_from(Incident).where(
                Incident.approval_required.is_(True),
                Incident.remediation_approved.is_(False),
            )
        ) or 0
    return {
        "total_incidents": total,
        "monitoring_alerts": alerts,
        "human_incidents": human,
        "p1_incidents": critical,
        "approvals_pending": approvals_pending,
    }
