# Sprint 6 — Synthetic Incident Environment

## Objective

Create a controlled airline-style service that can reproduce user-impacting incidents without customer data, production access, or destructive actions. This service becomes the telemetry source for OpenTelemetry, LangGraph investigation, RAG, remediation, and validation work in later sprints.

## Why a separate synthetic service?

OpsPilot AI is the incident control plane. The synthetic booking service represents the workload being observed and repaired. Keeping them separate mirrors a real SRE architecture and lets the workload fail without taking down the incident platform itself.

## Implemented scenarios

| Mode | Shallow `/health` | Booking journey | Purpose |
|---|---:|---:|---|
| `healthy` | 200 | Fast, successful | Normal baseline |
| `high_latency` | 200 | Delayed, successful | Demonstrates user impact while a shallow health dashboard remains green |
| `dependency_failure` | 503 | 503 | Demonstrates an explicit downstream dependency outage |

All records and routes are synthetic.

## Run locally

Start the existing OpsPilot control plane in one terminal:

```bash
uvicorn app.main:app --reload --port 8000
```

Start the synthetic workload in another terminal:

```bash
uvicorn demo_service.main:app --reload --port 8001
```

Open the synthetic service Swagger UI:

```text
http://127.0.0.1:8001/docs
```

## Try the first incident scenario

1. Confirm that `GET /health` returns HTTP 200.
2. Call `POST /admin/failure-mode` with:

```json
{
  "mode": "high_latency",
  "latency_ms": 3000
}
```

3. Confirm that `GET /health` still returns HTTP 200.
4. Call `GET /bookings/DEMO-1001` and observe the delayed response.
5. Call `POST /admin/reset` to restore the healthy baseline.

This is the core outside-in monitoring scenario: a shallow health check stays green, but the customer journey is degraded.

## Safety boundaries

- No real passenger or customer records
- No production services
- No cloud credentials
- No destructive failure injection
- All modes are allowlisted and reversible
- Reset endpoint always restores the baseline

## Acceptance criteria

- Existing OpsPilot tests continue to pass.
- Synthetic service tests cover healthy, latency, dependency failure, reset, and invalid configuration.
- High-latency mode keeps shallow health green while delaying the booking journey.
- Dependency-failure mode returns HTTP 503.
- The service can be reset without restarting the process.

## Next sprint connection

OpenTelemetry instrumentation will measure booking latency, request counts, error rates, logs, and traces. An outside-in probe will call the booking journey rather than relying only on `/health`.
