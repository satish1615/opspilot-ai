# Sprint 8 — Agentic Investigation, RCA, and RAG

## Objective

Turn OpsPilot AI from deterministic incident triage into an evidence-first investigation workflow that can combine live observability data, historical operational knowledge, vector retrieval, and LLM reasoning without allowing the model to invent operational evidence.

## Implemented Sprint 8 architecture

```text
Persisted OpsPilot incident
        ↓
LangGraph investigation workflow
        ↓
Collect current evidence
  ├─ Tempo traces
  ├─ Mimir metrics
  └─ Loki logs
        ↓
Qdrant vector RAG
  ├─ approved runbooks
  ├─ historical incidents
  └─ previously persisted RCA results
        ↓
LiteLLM model gateway
        ↓
Configured LLM
        ↓
Structured probable RCA
  ├─ root cause
  ├─ recommended action
  ├─ prevention
  ├─ confidence
  └─ evidence IDs
        ↓
Grounding validation
        ↓
Persist investigation for audit + future RAG
```

## Increment 1 — LangGraph foundation

Implemented:

- `langgraph==1.2.10`
- Typed investigation state and graph orchestration
- `POST /incidents/{incident_id}/investigate`
- Deterministic fallback hypothesis
- Grounding-status classification

## Increment 2 — live observability evidence

Implemented and previously verified against the local LGTM stack:

- Tempo TraceQL search
- Mimir queries for demo-run P95 HTTP duration and observed 5xx count
- Loki LogQL range query for incident-relevant warning/error messages
- Per-backend fault isolation
- Opt-in configuration via `OPSPILOT_OBSERVABILITY_ENABLED`
- Structured telemetry evidence in the investigation response

Default local backend URLs:

- Tempo: `http://localhost:3200`
- Mimir: `http://localhost:9009/prometheus`
- Loki: `http://localhost:3100`

## Increment 3 — Qdrant vector RAG

Implemented:

- Local Qdrant service in `docker-compose.observability.yml`
- FastEmbed integration using `BAAI/bge-small-en-v1.5`
- Semantic retrieval across:
  - approved runbooks
  - previous incident summaries
  - previously persisted investigation/RCA results
- Current incident is excluded from its own retrieval query
- Retrieval is fault-isolated so Qdrant failure never breaks core incident triage

Enable local RAG:

```bash
export OPSPILOT_RAG_ENABLED=true
export OPSPILOT_QDRANT_URL=http://localhost:6333
```

The first local embedding run may download the FastEmbed model.

## Increment 4 — LiteLLM grounded RCA

Implemented:

- LiteLLM Python SDK as the provider-neutral model gateway
- Configurable model through `OPSPILOT_LLM_MODEL`
- Default demo model: `gemini/gemini-2.5-flash`
- Structured model contract:
  - probable root cause
  - recommended action
  - prevention action
  - confidence
  - evidence IDs
- Explicit evidence catalogue IDs:
  - `A*` current incident/alert context
  - `B*` approved runbook evidence already attached to the incident
  - `T*` live telemetry evidence
  - `K*` Qdrant-retrieved operational knowledge
- Model output with unknown evidence IDs is rejected
- When stronger evidence exists, the model must cite telemetry, retrieved knowledge, or approved runbook evidence rather than relying only on the raw alert
- Provider/model failures automatically fall back to deterministic analysis

Example enablement for the configured Gemini model:

```bash
export GEMINI_API_KEY="<set-locally-do-not-commit>"
export OPSPILOT_LLM_ENABLED=true
export OPSPILOT_LLM_MODEL=gemini/gemini-2.5-flash
```

No API key is stored in the repository.

## Increment 5 — persistence and learning loop

Implemented:

- New `investigations` table created alongside the existing incident table
- Stores:
  - workflow and reasoning mode
  - model metadata
  - root cause, action, prevention, confidence
  - evidence IDs
  - observability evidence
  - RAG retrieval metadata
  - retrieved knowledge
  - workflow steps
- `GET /incidents/{incident_id}/investigation` returns the latest persisted investigation
- Persisted investigation RCA text becomes eligible knowledge for later Qdrant retrieval

This creates the Sprint 8 learning loop:

```text
new incident → investigate → grounded RCA → persist → index as knowledge → help future incident
```

## Safe fallback behavior

All optional AI/observability components are fault-isolated.

If OpenTelemetry backends, Qdrant, the embedding model, LiteLLM, the provider, or an API key is unavailable, OpsPilot does not fail the incident request. It returns the deterministic baseline with an explicit `reasoning_mode=deterministic_fallback` and records why model generation was unavailable.

When the LLM path succeeds, the response uses `reasoning_mode=llm_grounded` and `status=grounded_rca`.

## Local full-flow configuration

```bash
# Infrastructure
docker compose -f docker-compose.observability.yml up -d

# Synthetic service telemetry
export OTEL_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=opspilot-synthetic-booking

# OpsPilot evidence collection
export OPSPILOT_OBSERVABILITY_ENABLED=true
export OPSPILOT_OBSERVABILITY_SERVICE_NAME=opspilot-synthetic-booking

# RAG
export OPSPILOT_RAG_ENABLED=true
export OPSPILOT_QDRANT_URL=http://localhost:6333

# LLM
export OPSPILOT_LLM_ENABLED=true
export OPSPILOT_LLM_MODEL=gemini/gemini-2.5-flash
export GEMINI_API_KEY="<local-secret>"
```

## Safety and truthfulness

- No production or customer data is used.
- The inventory dependency in the synthetic workload remains simulated.
- LangGraph orchestration is real.
- Tempo/Mimir/Loki evidence collection is read-only.
- Qdrant retrieval is read-only during investigation except for indexing the sanitised local knowledge collection.
- LLM output is treated as a probable RCA, not an unquestioned fact.
- Unsupported evidence citations are rejected.
- Safe deterministic fallback remains available.
- No infrastructure remediation is executed in Sprint 8.
- Remediation execution remains Sprint 9 scope.

## Verification status

The implementation and automated coverage are now in place. Full Sprint 8 validation should run after dependency installation and should include:

1. complete pytest suite;
2. Qdrant semantic retrieval against the local service;
3. live model call through LiteLLM with a locally supplied API key;
4. end-to-end incident → telemetry → RAG → model RCA → persistence check;
5. confirmation that no code or secret is written to `main` before review/approval.
