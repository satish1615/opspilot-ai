from app.analyzer import analyze_human_incident, analyze_monitoring_alert


def test_high_cpu_above_threshold_is_detected():
    result = analyze_monitoring_alert("HIGH_CPU", value=95, threshold=80)
    assert result["issue_detected"] is True
    assert result["priority"] in {"P1", "P2", "P3"}
    assert result["category"] == "Infrastructure"


def test_high_cpu_below_threshold_is_normal():
    result = analyze_monitoring_alert("HIGH_CPU", value=60, threshold=80)
    assert result["issue_detected"] is False
    assert result["technical_severity"] == "low"
    assert result["priority"] == "P4"


def test_high_cpu_equal_to_threshold_is_detected():
    result = analyze_monitoring_alert("HIGH_CPU", value=80, threshold=80)
    assert result["issue_detected"] is True


def test_service_down_uses_inverse_threshold():
    result = analyze_monitoring_alert("SERVICE_DOWN", value=0, threshold=1)
    assert result["issue_detected"] is True
    assert result["priority"] == "P1"


def test_human_incident_classifies_vpn_issue():
    result = analyze_human_incident(
        title="Users cannot connect to VPN",
        description="The VPN connection times out for multiple users.",
        impact="medium",
        urgency="high",
        affected_users=20,
        workaround_available=False,
    )
    assert result["category"] == "Network"
    assert result["assignment_group"] == "Network Operations"
    assert result["priority"] == "P2"


def test_human_incident_priority_is_reduced_when_workaround_exists():
    result = analyze_human_incident(
        title="Critical application unavailable",
        description="All users receive an application error during login.",
        impact="high",
        urgency="high",
        affected_users=1000,
        workaround_available=True,
    )
    assert result["priority"] == "P2"
