# Architecture and Design Decisions

## 1. Purpose

OpsPilot AI standardises the first stage of incident triage. It accepts structured monitoring signals and human-written incident context, validates the data, produces a consistent analysis, stores the record, and exposes the result through an API and dashboard.

## 2. Component flow

1. **Client** sends JSON through Swagger, the dashboard, a script, or a future monitoring/ITSM integration.
2. **FastAPI** matches the method and path and coordinates the request-response cycle.
3. **Pydantic** validates required fields, types, ranges, and allowed values before endpoint logic runs.
4. **Analyzer** applies metric-specific or text-based transparent rules.
5. **Knowledge retrieval** returns matching sanitised runbooks.
6. **History retrieval** compares the incident with existing local records.
7. **Storage** converts the result into a SQLAlchemy model and commits it to SQLite.
8. **Response** returns a structured incident with analysis and approval state.

## 3. Why deterministic analysis is the default

The submission must run without secrets, internet access, paid services, or unpredictable model output. Transparent rules make the demo reproducible and allow every classification to be explained. The code is designed so an LLM adapter can be added later, but no external model is required for the final working release.

## 4. Monitoring-alert logic

- `HIGH_CPU`, `HIGH_MEMORY`, `DISK_FULL`, and `HTTP_5XX_SPIKE` are breached when `value >= threshold`.
- `SERVICE_DOWN` uses inverse logic because a low health value represents failure: `value <= threshold`.
- Severity is calculated from the threshold ratio and can be raised by a trusted reported severity.
- Severity maps to priority: critical → P1, high → P2, medium → P3, low → P4.

## 5. Human-incident logic

The system tokenises the title and description and scores explicit keyword groups such as VPN/network, access/authentication, messaging, database, infrastructure, and application support. Impact and urgency determine the initial priority, while affected-user count and workaround availability adjust it.

The approach is intentionally explainable. It is not represented as a trained machine-learning model.

## 6. Evidence retrieval

`app/knowledge.py` contains sanitised runbook summaries. Retrieval uses overlapping keywords and returns only safe first steps. It never includes confidential procedures or credentials.

## 7. Similar-incident retrieval

Stored incident titles and descriptions are tokenised. Candidate records receive extra weight when their category matches. The API returns the top records with a simple percentage score. This is a lightweight history feature suitable for the local prototype.

## 8. Persistence

SQLite stores the records in `data/opspilot.db`. SQLAlchemy isolates most database operations from the engine, making a later PostgreSQL migration possible. The database URL is configurable through `OPSPILOT_DATABASE_URL`.

## 9. Safety and approval

Every detected issue sets `approval_required=true`. The approval endpoint records who approved, when, and an optional note. It does **not** execute remediation. This demonstrates a safe human-in-the-loop boundary.

## 10. Trade-offs

- SQLite is ideal for a local hackathon demo but not for high-concurrency enterprise deployment.
- Keyword retrieval is reliable and explainable but less flexible than embeddings.
- Rule-based classification avoids hallucination but requires deliberate maintenance.
- No authentication is included because this is a local demo; production deployment would require identity, authorisation, audit logging, rate limiting, migrations, secrets management, and secure network controls.
