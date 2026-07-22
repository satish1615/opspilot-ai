CAUSES = {
    "HIGH_CPU": "A resource-intensive process or sudden traffic increase",
    "HIGH_MEMORY": "A possible memory leak or excessive application workload",
    "DISK_FULL": "Rapid log growth, temporary files, or unused data",
    "SERVICE_DOWN": "Application crash, dependency failure, or configuration issue",
    "HTTP_5XX_SPIKE": "Backend exception or unavailable dependency",
}

ACTIONS = {
    "HIGH_CPU": "Inspect running processes and recent deployments",
    "HIGH_MEMORY": "Check memory-consuming processes and application logs",
    "DISK_FULL": "Remove unnecessary files and rotate old logs",
    "SERVICE_DOWN": "Check service status, logs, and dependent services",
    "HTTP_5XX_SPIKE": "Inspect application errors and dependency health",
}


def analyze_alert(alert_type: str, value: float, threshold: float):
    is_breached = (
        value <= threshold
        if alert_type == "SERVICE_DOWN"
        else value >= threshold
    )

    return {
        "investigation_status": "issue_detected" if is_breached else "normal",
        "probable_cause": CAUSES[alert_type] if is_breached else "No issue detected",
        "recommended_action": (
            ACTIONS[alert_type]
            if is_breached
            else "Continue monitoring"
        ),
        "confidence": 85 if is_breached else 40,
    }