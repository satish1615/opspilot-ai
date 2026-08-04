# Demo and Screenshot Checklist

Use synthetic data only. Keep browser zoom around 90-100%, hide bookmarks and unrelated tabs, and do not display repository source code before evaluation unless the hackathon explicitly requires it.

## Required screenshots

1. **Dashboard overview** — `/dashboard` with the title, metric cards, both intake forms, and incident-history table visible.
2. **Monitoring-alert response** — Swagger `POST /alerts` showing a `201` response with priority, category, probable cause, recommendation, confidence, evidence, and approval state.
3. **Human-incident response** — Swagger `POST /human-incidents` using the VPN demo, showing P2 and Network Operations.
4. **Persistent history** — `GET /incidents` showing both records after restarting Uvicorn.
5. **Safety control** — approval endpoint response showing `approved=true` and `execution_status=not_executed`.
6. **Automated tests** — terminal output from `pytest -q` with all tests passing.
7. **API documentation** — top section of `/docs` showing the grouped final endpoints.
8. **Architecture** — render the architecture block from the README or create a clean slide from `docs/ARCHITECTURE.md`.

## Sanitised demo data

### Alert

- Server: `demo-app-01`
- Business service: `Demo Booking API`
- Type: `HIGH_CPU`
- Value: `95`
- Threshold: `80`
- Severity: `high`

### Human incident

- Title: `Multiple users cannot connect to VPN`
- Description: `Users receive a connection timeout while signing in to the corporate VPN.`
- Impact: `medium`
- Urgency: `high`
- Affected users: `35`
- Business service: `Remote Access`
- Workaround: `false`

## Final command checklist

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
uvicorn app.main:app --reload
```

Then verify `/health`, `/dashboard`, `/docs`, both POST endpoints, history, approval, and metrics.
