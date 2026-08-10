# Sprint 8 — Agentic Investigation, RCA, and RAG

## Objective

Turn OpsPilot AI from deterministic incident triage into an evidence-first investigation workflow that can later combine live observability data, historical knowledge, vector retrieval, and LLM reasoning without allowing the model to invent operational evidence.

## Sprint 8 target architecture

```text
Persisted OpsPilot incident
        ↓
LangGraph investigation workflow
        ↓
Collect real evidence
  ├─ Tempo traces
  ├─ Mimir metrics
  └─ Loki logs
        ↓
Retrieve relevant knowledge
  ├─ runbooks
  └─ historical incidents via vector RAG
        ↓
LiteLLM model gateway
        ↓
Selected LLM
        ↓
Grounded RCA + recommendation + confidence
        ↓
Validation / safety checks
```

## Increment 1 — implemented and verified

The first Sprint 8 increment establishes the orchestration contract before any external model is trusted with incident reasoning.

Implemented:

- `langgraph==1.2.10`
- New `app.agent` package
- Typed investigation state
- LangGraph workflow for incident context, deterministic hypothesis, and grounding validation
- New API endpoint: `POST /incidents/{incident_id}/investigate`
- Structured investigation response schema
- Tests for graph execution, persisted-incident investigation, and unknown incidents

Verification on the developer Mac:

```text
26 passed in 1.41s
```

## Increment 2 — implemented, awaiting local verification

The graph now has a dedicated `collect_observability_evidence` node and a read-only LGTM evidence client.

Implemented:

- Tempo TraceQL search through the Tempo HTTP API
- Mimir instant queries for demo-run P95 HTTP duration and observed 5xx count
- Loki LogQL range query for incident-relevant warning/error messages
- Per-backend isolation so one unavailable signal does not break the investigation
- Opt-in configuration via `OPSPILOT_OBSERVABILITY_ENABLED`
- Structured telemetry evidence returned by the investigation endpoint
- Mocked tests covering Tempo, Mimir, and Loki response parsing

The default remains disabled so normal unit/API tests do not depend on Docker services. To use real local telemetry evidence:

```bash
export OPSPILOT_OBSERVABILITY_ENABLED=true
export OPSPILOT_OBSERVABILITY_SERVICE_NAME=opspilot-synthetic-booking
```

Default local backend URLs match the Sprint 7 stack:

- Tempo: `http://localhost:3200`
- Mimir: `http://localhost:9009/prometheus`
- Loki: `http://localhost:3100`

## Current reasoning mode

The current response still explicitly returns:

```text
reasoning_mode = deterministic_foundation
```

This is intentional. Even when live telemetry evidence is collected, the graph does **not** yet ask an LLM to produce RCA. The deterministic probable cause and recommendation remain the fallback until vector retrieval, LiteLLM, model selection, structured model output, and grounding validation are implemented.

## Remaining Sprint 8 work

- Verify real Tempo, Mimir, and Loki collection against the running Sprint 7 stack
- Add Qdrant-backed vector retrieval for runbooks and historical incidents
- Add LiteLLM as the model gateway
- Evaluate candidate LLMs against controlled SRE scenarios before selecting the primary model
- Require structured model output
- Ground RCA statements in collected evidence and retrieved context
- Add hallucination / unsupported-claim checks
- Persist investigation results and model/evidence metadata
- Connect investigation output cleanly to the OpsPilot incident record
- Add end-to-end tests and demo evidence

## Safety and truthfulness

- No production or customer data is used.
- The synthetic inventory dependency remains simulated.
- LangGraph orchestration is real.
- Increment 2 performs read-only observability queries only.
- Current RCA generation is deterministic, not LLM-based.
- Qdrant vector RAG, LiteLLM, and model-backed RCA remain unimplemented until later Sprint 8 increments.
- Remediation execution remains Sprint 9 scope.
