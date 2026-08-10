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

## Increment 1 — implemented

The first Sprint 8 increment establishes the orchestration contract before any external model is trusted with incident reasoning.

Implemented:

- `langgraph==1.2.10`
- New `app.agent` package
- Typed investigation state
- LangGraph workflow with three nodes:
  1. `collect_incident_context`
  2. `build_initial_hypothesis`
  3. `validate_grounding`
- New API endpoint: `POST /incidents/{incident_id}/investigate`
- Structured investigation response schema
- Tests for graph execution, persisted-incident investigation, and unknown incidents

## Current reasoning mode

The current response explicitly returns:

```text
reasoning_mode = deterministic_foundation
```

This is intentional. The graph currently reuses the incident's existing deterministic probable cause, recommendation, runbook evidence, and similar-incident context. It does **not** call an LLM yet and must not be presented as AI-generated RCA.

This baseline gives Sprint 8 a safe fallback path. When model-backed reasoning is added, OpsPilot can still return a transparent deterministic investigation if the model is disabled, unavailable, or fails validation.

## Remaining Sprint 8 work

- Query real Tempo, Mimir, and Loki evidence from the Sprint 7 observability stack
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
- LangGraph orchestration is real in Increment 1.
- Current RCA generation is deterministic, not LLM-based.
- Vector RAG, LiteLLM, live observability evidence collection, and model-backed RCA are Sprint 8 work still to be completed and verified.
- Remediation execution remains Sprint 9 scope.
