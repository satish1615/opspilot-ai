# API Examples

Start the application with `uvicorn app.main:app --reload`.

## Monitoring alert

```bash
curl -X POST http://127.0.0.1:8000/alerts \
  -H 'Content-Type: application/json' \
  -d '{
    "alert_type": "HIGH_CPU",
    "server": "demo-app-01",
    "value": 95,
    "threshold": 80,
    "severity": "high",
    "business_service": "Demo Booking API"
  }'
```

Expected response fields include incident ID, P1-P4 priority, category, assignment group, probable cause, recommendation, confidence, evidence, and approval status.

## Service-down alert

`SERVICE_DOWN` intentionally uses inverse comparison.

```json
{
  "alert_type": "SERVICE_DOWN",
  "server": "demo-api-01",
  "value": 0,
  "threshold": 1
}
```

## Human-created incident

```bash
curl -X POST http://127.0.0.1:8000/human-incidents \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Multiple users cannot connect to VPN",
    "description": "Users receive a connection timeout while signing in to the corporate VPN.",
    "impact": "medium",
    "urgency": "high",
    "affected_users": 35,
    "business_service": "Remote Access",
    "workaround_available": false
  }'
```

## List incidents

```bash
curl 'http://127.0.0.1:8000/incidents?priority=P2&limit=20'
```

Supported filters: `source_type`, `priority`, `status`, and `limit`.

## Retrieve one incident

```bash
curl http://127.0.0.1:8000/incidents/INCIDENT_ID
```

## Record remediation approval

```bash
curl -X POST http://127.0.0.1:8000/incidents/INCIDENT_ID/approve-remediation \
  -H 'Content-Type: application/json' \
  -d '{
    "approved_by": "Hackathon Reviewer",
    "note": "Approved for manual recovery only."
  }'
```

Approval changes the record to `approved_for_manual_action`; it never executes an operational change.

## Summary metrics

```bash
curl http://127.0.0.1:8000/metrics/summary
```

## Validation example

A server name shorter than two characters or a non-positive metric threshold returns HTTP `422` with a structured validation error.
