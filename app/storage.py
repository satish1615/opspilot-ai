INCIDENTS: dict[str, dict] = {}


def save_incident(incident: dict) -> None:
    INCIDENTS[incident["alert_id"]] = incident


def get_all_incidents() -> list[dict]:
    return list(INCIDENTS.values())


def get_incident(alert_id: str) -> dict | None:
    return INCIDENTS.get(alert_id)