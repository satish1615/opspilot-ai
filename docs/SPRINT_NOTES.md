# Sprint-by-Sprint Notes

This file records what was built, the main code used, the learning outcome, and the verification for every sprint. Earlier PDF notes were consolidated into this final Markdown reference.

## Sprint 0 — Backend foundation

**Goal:** Create a runnable FastAPI service.

**Implemented:** project folders, virtual environment workflow, `GET /`, `GET /health`, Uvicorn startup, Swagger UI.

**Key code:** `app = FastAPI(...)`, route decorators such as `@app.get("/health")`, and `uvicorn app.main:app --reload`.

**Learning:** FastAPI is the backend framework; Uvicorn is the ASGI server; Swagger is automatically generated from endpoint and Pydantic definitions.

## Sprint 1 — Validated monitoring alert intake

**Goal:** Receive a standard monitoring payload.

**Implemented:** `POST /alerts`, allowed alert types, server validation, numeric values, optional reported severity, UUID incident identifier, UTC timestamp, `201 Created`.

**Key code:** `MonitoringAlertCreate(BaseModel)` and `Field(...)` constraints.

**Verification:** valid input returns `201`; invalid server or threshold returns `422` before analysis executes.

## Sprint 2 — Metric-specific incident analysis

**Goal:** Decide whether an alert represents an issue and recommend the first investigation action.

**Implemented:** explicit rules for CPU, memory, disk usage, service availability, and HTTP 5xx spikes; probable cause; recommended action; confidence.

**Key code:** `analyze_monitoring_alert()` and the `ALERT_RULES` mapping.

**Verification:** threshold boundaries and inverse `SERVICE_DOWN` behaviour are covered by unit tests.

## Sprint 3 — Incident-history APIs

**Goal:** Retrieve analysis records.

**Implemented:** `GET /incidents`, `GET /incidents/{incident_id}`, filtering, ordering, limits, and `404 Incident not found`.

**Key code:** SQLAlchemy `select(...)` and FastAPI `HTTPException`.

## Sprint 4 — SQLAlchemy and SQLite persistence

**Goal:** Keep incidents after the backend restarts.

**Implemented:** SQLAlchemy engine, session factory, `Incident` model, save/read functions, configurable database URL, and database health query.

**Key code:** `create_engine`, `sessionmaker`, `DeclarativeBase`, `mapped_column`, `session.commit()`.

**Verification:** API tests create records and retrieve them through database-backed endpoints. The `data/*.db` files are ignored by Git.

## Sprint 5 — Quality baseline

**Goal:** Make behaviour repeatable and protect completed features.

**Implemented:** analyzer unit tests, API integration tests, isolated in-memory SQLite during tests, development requirements, and GitHub Actions.

**Key code:** pytest fixtures, `TestClient`, table reset before each test, and `.github/workflows/tests.yml`.

**Verification:** the final suite covers analysis, validation, history, missing incidents, approval, and metrics.

## Sprint 6 — Human-created incident intake

**Goal:** Handle incidents entered by people, not only monitoring tools.

**Implemented:** `POST /human-incidents` with title, description, impact, urgency, affected users, business service, and workaround availability.

**Key code:** `HumanIncidentCreate` and `analyze_human_incident()`.

**Verification:** VPN and email examples are classified into the expected category and assignment group.

## Sprint 7 — P1-P4 priority and routing

**Goal:** Convert technical and business context into consistent triage fields.

**Implemented:** technical severity, P1-P4 priority matrix, category, subcategory, assignment-group recommendation, affected-user adjustment, and workaround adjustment.

**Key code:** `_priority_from_impact_urgency()`, `_severity_from_priority()`, and explicit routing rules.

**Verification:** a high-impact/high-urgency incident is P1 unless a viable workaround reduces immediate urgency; large user counts raise lower priorities.

## Sprint 8 — Evidence and similar incidents

**Goal:** Ground recommendations in approved knowledge and history.

**Implemented:** sanitised local runbooks, transparent keyword retrieval, similar-incident scoring, `/runbooks`, and evidence inside each incident response.

**Key code:** `retrieve_runbooks()`, `tokenise()`, and `find_similar_incidents()`.

**Truthfulness:** this is lightweight deterministic retrieval, not a vector database or an LLM. Those remain future options.

## Sprint 9 — Safety controls, dashboard, and submission packaging

**Goal:** Deliver a complete demonstrable hackathon model.

**Implemented:** remediation approval recording, no autonomous execution, metrics endpoint, browser dashboard, Docker support, clean README, architecture, API examples, screenshot plan, submission guide, and interview preparation.

**Key code:** `/incidents/{incident_id}/approve-remediation`, `/metrics/summary`, and `dashboard/index.html`.

**Final product state:** locally runnable, persistent, tested, documented, safe, and suitable for a live demo with synthetic data.
