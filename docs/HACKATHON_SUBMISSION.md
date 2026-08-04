# Hackathon Submission Guide

## Project title

**OpsPilot AI — Safe Incident Triage and Human-Approved Remediation**

Use the official hackathon workbook's exact industry, sub-industry, use-case title, and submission labels when completing the portal. Do not invent or paraphrase official labels without checking the current workbook.

## One-line description

OpsPilot AI standardises monitoring alerts and human-created incidents into explainable P1-P4 triage, evidence-backed recommendations, persistent history, and human-controlled remediation approval.

## Problem

Operational triage often starts with inconsistent alert formats, incomplete incident descriptions, repeated manual checks, and unclear assignment. This delays routing and makes the initial response dependent on individual experience.

## Solution

The platform provides one validated workflow that:

1. receives monitoring or human incident input;
2. applies explicit technical and business rules;
3. recommends severity, priority, category, assignment group, probable cause, and safe next action;
4. retrieves sanitised runbook evidence and similar local incidents;
5. stores the analysis for history and metrics;
6. blocks remediation execution until human approval is recorded.

## Demonstrable features

- Two incident-intake paths
- Validated input and clear errors
- Metric-specific threshold logic
- P1-P4 priority classification
- Routing and investigation recommendations
- Runbook evidence and similar incidents
- Persistent SQLite history
- Human approval audit fields
- Dashboard, Swagger, Docker, automated tests, and CI

## Two-minute pitch

“OpsPilot AI addresses the repetitive first stage of IT incident triage. A monitoring tool or operator sends structured information to FastAPI. Pydantic validates it before any business logic runs. The triage engine then applies metric-specific or impact-and-urgency rules, recommends P1-P4 priority, category, assignment group, probable cause, and a safe next action. The response also includes matching sanitised runbooks and similar incidents from local history. SQLAlchemy stores every result in SQLite, so the record survives application restarts. Finally, remediation remains human-controlled: approval can be recorded, but the prototype never executes an infrastructure action. The result is a transparent, testable, and safe foundation that can later integrate with enterprise monitoring, ITSM, and securely configured LLM services.”

## Demo sequence

1. Open `/dashboard` and `/docs`.
2. Show `/health` returning API and database health.
3. Submit a high-CPU alert and explain validation, threshold breach, severity, priority, category, cause, recommendation, and evidence.
4. Submit a VPN incident and explain the impact/urgency priority matrix and assignment group.
5. Open `/incidents` and show both records persisted.
6. Open one incident and show runbook evidence and approval state.
7. Call the approval endpoint and explain that execution still remains `not_executed`.
8. Show `/metrics/summary` and the test result.

## Implemented versus roadmap

### Implemented now

FastAPI, Pydantic, deterministic triage, human incident classification, P1-P4 priority, SQLAlchemy/SQLite, runbook retrieval, similar incidents, dashboard, tests, Docker, CI, and human approval recording.

### Future production roadmap

Authentication and role-based access, Alembic migrations, PostgreSQL, production observability, ITSM integration, vector retrieval, securely configured LLM assistance with strict schema validation, and policy-controlled automation.

Never present roadmap items as live features.

## Submission hygiene

- Use only synthetic demo servers, users, services, and incidents.
- Do not show confidential employer or client data.
- Do not upload `.env`, database files, credentials, production logs, or internal URLs.
- Keep screenshots focused on the working model and test evidence.
