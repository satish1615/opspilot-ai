# OpsPilot AI

OpsPilot AI is a hackathon-ready incident-triage platform built with Python, FastAPI, Pydantic, SQLAlchemy, SQLite, and pytest. It accepts machine-generated monitoring alerts and human-created incidents, validates the input, applies transparent analysis rules, assigns P1-P4 priority, retrieves sanitised runbook evidence, stores incident history, and keeps remediation behind a human approval gate.

> **Safety boundary:** OpsPilot AI recommends and records approval. It does not execute infrastructure changes, restart services, delete files, or call confidential enterprise systems.

## What is implemented

- Monitoring alert intake through `POST /alerts`
- Human-created incident intake through `POST /human-incidents`
- Pydantic validation and automatic OpenAPI documentation
- Metric-specific threshold evaluation, including inverse logic for `SERVICE_DOWN`
- Technical severity and P1-P4 business priority
- Category, subcategory, assignment-group recommendation, probable cause, and recommended action
- Sanitised local runbook evidence and similar-incident retrieval
- SQLite persistence through SQLAlchemy
- Incident list, filters, detail lookup, runbook API, and summary metrics
- Explicit remediation approval endpoint with no autonomous execution
- Browser dashboard at `/dashboard`
- Automated test suite and GitHub Actions workflow
- Sprint notes, architecture, API examples, interview preparation, and submission guidance

## Architecture

```text
Monitoring tool / Swagger / Dashboard / Human operator
                         |
                         v
                  FastAPI endpoints
                         |
                         v
                Pydantic validation
                         |
                         v
       Deterministic triage and priority engine
             |                         |
             v                         v
  Sanitised runbook evidence     Similar incidents
             \                         /
              v                       v
                   SQLAlchemy ORM
                         |
                         v
                    SQLite database
                         |
                         v
       API response + dashboard + approval record
```

Detailed architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Project structure

```text
opspilot-ai/
├── app/
│   ├── analyzer.py
│   ├── database.py
│   ├── knowledge.py
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   └── storage.py
├── dashboard/index.html
├── data/.gitkeep
├── docs/
├── tests/
├── .github/workflows/tests.yml
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── requirements-dev.txt
```

## Run locally

Python 3.13 is recommended.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Open:

- Dashboard: `http://127.0.0.1:8000/dashboard`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

## Run tests

```bash
pytest -q
```

The tests cover threshold boundaries, inverse service-down logic, human incident classification, priority rules, API validation, persistence-backed history, 404 handling, approval controls, and summary metrics.

## Run with Docker

```bash
docker compose up --build
```

The local `data/` directory is mounted so incident history survives container restarts.

## Demo payloads

### Monitoring alert

```json
{
  "alert_type": "HIGH_CPU",
  "server": "demo-app-01",
  "value": 95,
  "threshold": 80,
  "severity": "high",
  "business_service": "Demo Booking API"
}
```

### Human-created incident

```json
{
  "title": "Multiple users cannot connect to VPN",
  "description": "Users receive a connection timeout while signing in to the corporate VPN.",
  "impact": "medium",
  "urgency": "high",
  "affected_users": 35,
  "business_service": "Remote Access",
  "workaround_available": false
}
```

More examples: [`docs/API_EXAMPLES.md`](docs/API_EXAMPLES.md)

## API summary

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Application information |
| `GET` | `/health` | API and database health |
| `POST` | `/alerts` | Analyse a monitoring alert |
| `POST` | `/human-incidents` | Analyse a human-created incident |
| `GET` | `/incidents` | List and filter incident history |
| `GET` | `/incidents/{incident_id}` | Retrieve one incident |
| `POST` | `/incidents/{incident_id}/approve-remediation` | Record human approval |
| `GET` | `/metrics/summary` | Dashboard metrics |
| `GET` | `/runbooks` | View sanitised runbook summaries |
| `GET` | `/dashboard` | Open the demo UI |

## Implemented versus future work

Implemented functionality is deterministic, explainable, locally runnable, and fully testable without an external API key. A future production phase may add a securely configured LLM provider and vector retrieval, but those capabilities are not claimed as part of this release. The current evidence layer uses transparent keyword retrieval over sanitised runbooks, and every remediation remains human-controlled.

## Documentation

- [Sprint-by-sprint notes](docs/SPRINT_NOTES.md)
- [Architecture and design decisions](docs/ARCHITECTURE.md)
- [API requests and responses](docs/API_EXAMPLES.md)
- [Hackathon submission guide](docs/HACKATHON_SUBMISSION.md)
- [Demo and screenshot checklist](docs/DEMO_AND_SCREENSHOTS.md)
- [Interview questions and answers](docs/INTERVIEW_GUIDE.md)

## Data and confidentiality

All repository examples are synthetic. Do not add client names, production hostnames, ticket numbers, internal URLs, credentials, logs, or confidential incident details. `.env`, virtual environments, caches, and local database files are excluded from Git.

## Author

**Satish Singh** — independent builder and Coforge hackathon participant.
