from app.analyzer import analyze_alert


def test_high_cpu_above_threshold_is_detected():
    result = analyze_alert(
        alert_type="HIGH_CPU",
        value=95,
        threshold=80,
    )

    assert result["investigation_status"] == "issue_detected"
    assert result["confidence"] == 85

def test_high_cpu_below_threshold_is_normal():
    result = analyze_alert(
        alert_type="HIGH_CPU",
        value=70,
        threshold=80,
    )

    assert result["investigation_status"] == "normal"
    assert result["confidence"] == 40
    assert result["recommended_action"] == "Continue monitoring"    

def test_high_cpu_equal_to_threshold_is_normal():
    result = analyze_alert(
        alert_type="HIGH_CPU",
        value=80,
        threshold=80,
    )

    assert result["investigation_status"] == "normal"    