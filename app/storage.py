from sqlalchemy import select

from app.database import SessionLocal
from app.models import Incident


def incident_to_dict(incident: Incident) -> dict:
    return {
        "alert_id": incident.alert_id,
        "status": incident.status,
        "received_at": incident.received_at,
        "alert": {
            "alert_type": incident.alert_type,
            "server": incident.server,
            "value": incident.value,
            "threshold": incident.threshold,
            "severity": incident.severity,
        },
        "analysis": {
            "investigation_status": incident.investigation_status,
            "probable_cause": incident.probable_cause,
            "recommended_action": incident.recommended_action,
            "confidence": incident.confidence,
        },
    }


def save_incident(incident: dict) -> None:
    session = SessionLocal()

    try:
        db_incident = Incident(
            alert_id=incident["alert_id"],
            status=incident["status"],
            received_at=incident["received_at"],
            alert_type=incident["alert"]["alert_type"],
            server=incident["alert"]["server"],
            value=incident["alert"]["value"],
            threshold=incident["alert"]["threshold"],
            severity=incident["alert"]["severity"],
            investigation_status=incident["analysis"]["investigation_status"],
            probable_cause=incident["analysis"]["probable_cause"],
            recommended_action=incident["analysis"]["recommended_action"],
            confidence=incident["analysis"]["confidence"],
        )

        session.add(db_incident)
        session.commit()

    finally:
        session.close()


def get_all_incidents() -> list[dict]:
    session = SessionLocal()

    try:
        incidents = session.scalars(select(Incident)).all()
        return [incident_to_dict(incident) for incident in incidents]

    finally:
        session.close()


def get_incident(alert_id: str) -> dict | None:
    session = SessionLocal()

    try:
        incident = session.get(Incident, alert_id)

        if incident is None:
            return None

        return incident_to_dict(incident)

    finally:
        session.close()