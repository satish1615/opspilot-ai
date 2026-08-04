"""Deterministic incident-triage engine with evidence-backed recommendations."""

from __future__ import annotations

from app.knowledge import retrieve_runbooks, tokenise

ALERT_RULES: dict[str, dict] = {
    "HIGH_CPU": {
        "title": "High CPU utilisation",
        "category": "Infrastructure",
        "subcategory": "Compute",
        "assignment_group": "Cloud and Server Operations",
        "cause": "A resource-intensive process, traffic increase, or recent deployment may be consuming CPU.",
        "action": "Inspect top processes, recent deployments, traffic changes, and application logs.",
        "keywords": "cpu process load latency slow",
    },
    "HIGH_MEMORY": {
        "title": "High memory utilisation",
        "category": "Infrastructure",
        "subcategory": "Memory",
        "assignment_group": "Cloud and Server Operations",
        "cause": "A memory leak, undersized limit, or unusually high workload may be consuming memory.",
        "action": "Inspect memory-consuming processes, out-of-memory events, limits, and recent changes.",
        "keywords": "memory ram leak oom swap",
    },
    "DISK_FULL": {
        "title": "High disk utilisation",
        "category": "Infrastructure",
        "subcategory": "Storage",
        "assignment_group": "Cloud and Server Operations",
        "cause": "Log growth, temporary files, backups, or application data may be consuming storage.",
        "action": "Identify high-usage directories, verify retention, and follow approved cleanup procedures.",
        "keywords": "disk storage filesystem logs space",
    },
    "SERVICE_DOWN": {
        "title": "Service unavailable",
        "category": "Application",
        "subcategory": "Availability",
        "assignment_group": "Application Support",
        "cause": "The service may have crashed or a dependency, configuration, or network path may be unavailable.",
        "action": "Confirm impact, review service and dependency logs, then use an approved recovery procedure.",
        "keywords": "service down unavailable crash timeout",
    },
    "HTTP_5XX_SPIKE": {
        "title": "HTTP 5xx error spike",
        "category": "Application",
        "subcategory": "Application Errors",
        "assignment_group": "Application Support",
        "cause": "A backend exception, failed dependency, capacity constraint, or deployment regression may be producing errors.",
        "action": "Inspect error logs, dependency health, deployment history, and request-volume changes.",
        "keywords": "500 5xx error service dependency timeout",
    },
}

HUMAN_RULES: list[dict] = [
    {
        "keywords": {"vpn", "network", "connectivity", "dns", "wifi", "latency"},
        "category": "Network",
        "subcategory": "Connectivity",
        "assignment_group": "Network Operations",
        "cause": "VPN gateway, DNS, endpoint connectivity, or network-path degradation may be affecting access.",
        "action": "Confirm scope, collect timestamps and error details, then check VPN, DNS, and network-health indicators.",
    },
    {
        "keywords": {"login", "password", "authentication", "mfa", "account", "locked", "entitlement"},
        "category": "Access Management",
        "subcategory": "Authentication",
        "assignment_group": "Identity and Access Management",
        "cause": "Account lock, password expiry, MFA, entitlement, or identity-provider health may be blocking access.",
        "action": "Verify identity, capture the exact error, and check account and identity-provider status without requesting a password.",
    },
    {
        "keywords": {"email", "outlook", "mail", "mailbox", "smtp", "message"},
        "category": "Messaging",
        "subcategory": "Email",
        "assignment_group": "Messaging Support",
        "cause": "Mailbox configuration, service degradation, connector health, or account-level restrictions may be affecting email.",
        "action": "Confirm send/receive scope, check service health, and review connector or queue health.",
    },
    {
        "keywords": {"database", "sql", "query", "oracle", "mysql", "postgres", "connection"},
        "category": "Database",
        "subcategory": "Database Availability",
        "assignment_group": "Database Operations",
        "cause": "Database availability, connection-pool exhaustion, locking, or query performance may be affecting the service.",
        "action": "Check database health, connection usage, locks, slow queries, and recent schema or deployment changes.",
    },
    {
        "keywords": {"server", "cpu", "memory", "disk", "storage", "filesystem"},
        "category": "Infrastructure",
        "subcategory": "Server",
        "assignment_group": "Cloud and Server Operations",
        "cause": "A server resource, operating-system, capacity, or configuration issue may be affecting availability or performance.",
        "action": "Review server health, resource trends, logs, and recent changes before taking recovery action.",
    },
    {
        "keywords": {"application", "app", "error", "failed", "crash", "timeout", "500", "page"},
        "category": "Application",
        "subcategory": "Application Support",
        "assignment_group": "Application Support",
        "cause": "An application defect, failed dependency, configuration issue, or deployment regression may be causing the incident.",
        "action": "Collect reproducible steps, review logs and dependency health, and compare with recent deployments.",
    },
]

SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}
PRIORITY_ORDER = {"P4": 1, "P3": 2, "P2": 3, "P1": 4}


def _maximum_severity(first: str, second: str | None) -> str:
    if second is None:
        return first
    return first if SEVERITY_ORDER[first] >= SEVERITY_ORDER[second] else second


def _priority_for_severity(severity: str) -> str:
    return {"critical": "P1", "high": "P2", "medium": "P3", "low": "P4"}[severity]


def _priority_from_impact_urgency(impact: str, urgency: str, affected_users: int, workaround_available: bool) -> str:
    matrix = {
        ("high", "high"): "P1",
        ("high", "medium"): "P2",
        ("medium", "high"): "P2",
        ("high", "low"): "P3",
        ("medium", "medium"): "P3",
        ("low", "high"): "P3",
        ("medium", "low"): "P4",
        ("low", "medium"): "P4",
        ("low", "low"): "P4",
    }
    priority = matrix[(impact, urgency)]

    if affected_users >= 500 and PRIORITY_ORDER[priority] < PRIORITY_ORDER["P2"]:
        priority = "P2"
    elif affected_users >= 100 and PRIORITY_ORDER[priority] < PRIORITY_ORDER["P3"]:
        priority = "P3"

    if workaround_available and priority == "P1":
        priority = "P2"
    return priority


def _severity_from_priority(priority: str) -> str:
    return {"P1": "critical", "P2": "high", "P3": "medium", "P4": "low"}[priority]


def analyze_monitoring_alert(
    alert_type: str,
    value: float,
    threshold: float,
    reported_severity: str | None = None,
) -> dict:
    """Analyse a machine-generated monitoring alert."""

    rule = ALERT_RULES[alert_type]
    issue_detected = value <= threshold if alert_type == "SERVICE_DOWN" else value >= threshold

    if not issue_detected:
        calculated_severity = "low"
    elif alert_type == "SERVICE_DOWN":
        calculated_severity = "critical"
    else:
        ratio = value / threshold
        if ratio >= 1.25:
            calculated_severity = "critical"
        elif ratio >= 1.10:
            calculated_severity = "high"
        else:
            calculated_severity = "medium"

    technical_severity = _maximum_severity(calculated_severity, reported_severity if issue_detected else None)
    priority = _priority_for_severity(technical_severity)

    evidence = retrieve_runbooks(f"{rule['keywords']} {rule['title']}") if issue_detected else []
    return {
        "issue_detected": issue_detected,
        "technical_severity": technical_severity,
        "priority": priority,
        "category": rule["category"],
        "subcategory": rule["subcategory"],
        "assignment_group": rule["assignment_group"],
        "probable_cause": rule["cause"] if issue_detected else "The current value does not breach the configured threshold.",
        "recommended_action": rule["action"] if issue_detected else "Continue monitoring and retain the alert for trend analysis.",
        "confidence": 90 if issue_detected else 75,
        "evidence": evidence,
        "approval_required": issue_detected,
        "remediation_approved": False,
        "title": rule["title"],
        "description": f"{alert_type} on the monitored server: value={value}, threshold={threshold}.",
    }


def analyze_human_incident(
    title: str,
    description: str,
    impact: str,
    urgency: str,
    affected_users: int,
    workaround_available: bool,
) -> dict:
    """Classify and prioritise a human-created incident using transparent rules."""

    text = f"{title} {description}"
    tokens = tokenise(text)
    ranked: list[tuple[int, dict]] = []
    for rule in HUMAN_RULES:
        ranked.append((len(tokens.intersection(rule["keywords"])), rule))
    ranked.sort(key=lambda item: -item[0])

    score, selected = ranked[0]
    if score == 0:
        selected = {
            "category": "Service Desk",
            "subcategory": "General Request",
            "assignment_group": "Service Desk",
            "cause": "The available description does not contain enough technical evidence for a more specific cause.",
            "action": "Collect the exact error, timestamps, affected scope, recent changes, and reproduction steps before reassignment.",
        }

    priority = _priority_from_impact_urgency(impact, urgency, affected_users, workaround_available)
    technical_severity = _severity_from_priority(priority)
    confidence = min(92, 62 + (score * 10)) if score else 55
    evidence = retrieve_runbooks(text)

    return {
        "issue_detected": True,
        "technical_severity": technical_severity,
        "priority": priority,
        "category": selected["category"],
        "subcategory": selected["subcategory"],
        "assignment_group": selected["assignment_group"],
        "probable_cause": selected["cause"],
        "recommended_action": selected["action"],
        "confidence": confidence,
        "evidence": evidence,
        "approval_required": True,
        "remediation_approved": False,
        "title": title,
        "description": description,
    }
