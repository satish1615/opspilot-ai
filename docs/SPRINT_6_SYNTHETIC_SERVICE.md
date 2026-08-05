# Sprint 6 — Synthetic Incident Environment

## Objective

Create a controlled airline-style service that can reproduce user-impacting incidents without customer data, production access, or destructive actions. This service becomes the telemetry source for OpenTelemetry, LangGraph investigation, RAG, remediation, and validation work in later sprints.

## Why a separate synthetic service?

OpsPilot AI is the incident control plane. The synthetic booking service represents the workload being observed and repaired. Keeping them separate mirrors a real SRE architecture and lets the workload fail without taking down the incident platform itself.

## Implemented scenarios

| Mode | Liveness | Readiness | Synthetic booking check | Booking journey | Purpose |
|---|---:|---:|---:|---:|---|
| `healthy` | 200 | 200 | 200 | Fast, successful | Normal baseline |
| `high_latency` | 200 | 200 | 503 when the SLO is exceeded | Delayed, successful | Demonstrates user impact while infrastructure checks remain green |
| `dependency_failure` | 200 | 503 | 503 | 503 | Demonstrates an explicit downstream dependency outage |

All records and routes are synthetic.

## Health and journey endpoints

- `GET /health/live` — confirms that the application process is running.
- `GET /health/ready` — confirms that required dependencies are available and the instance can receive traffic.
- `GET /synthetic/booking-check` — executes an outside-in booking journey and compares its response time with an SLO.

The synthetic service intentionally does not expose a generic `GET /health` route. This avoids ambiguity and makes integrations choose the correct operational signal.

Public health responses intentionally do not expose the active failure mode or configured latency. Detailed demo controls remain available through `GET /admin/state`.

The synthetic check accepts an optional `slo_ms` query parameter. Its default value is 500 milliseconds.

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

## Try the high-latency incident scenario

1. Confirm that `GET /health/live` and `GET /health/ready` return HTTP 200.
2. Call `POST /admin/failure-mode` with:

```json
{
  "mode": "high_latency",
  "latency_ms": 1500
}
```

3. Confirm that liveness and readiness still return HTTP 200.
4. Call `GET /bookings/DEMO-1001` and observe the delayed but successful response.
5. Call `GET /synthetic/booking-check?slo_ms=500` and confirm that it returns HTTP 503 with `status: degraded` and `reason: slo_violation`.
6. Call `POST /admin/reset` to restore the healthy baseline.

This is the core outside-in monitoring scenario: process and dependency checks remain green while the customer journey violates its response-time objective.

## Try the dependency-failure scenario

1. Call `POST /admin/failure-mode` with:

```json
{
  "mode": "dependency_failure",
  "latency_ms": 1
}
```

2. Confirm that `GET /health/live` remains HTTP 200.
3. Confirm that `GET /health/ready` returns HTTP 503.
4. Confirm that both the synthetic booking check and booking endpoint return HTTP 503.
5. Call `POST /admin/reset` and confirm recovery.

## Safety boundaries

- No real passenger or customer records
- No production services
- No cloud credentials
- No destructive failure injection
- All modes are allowlisted and reversible
- Reset endpoint always restores the baseline
- Public health endpoints do not reveal internal failure-injection state

## Acceptance criteria

- Existing OpsPilot tests continue to pass.
- Synthetic service tests cover healthy, latency, dependency failure, reset, invalid configuration, and invalid SLO input.
- The removed generic `/health` route returns HTTP 404.
- Liveness stays available when a simulated dependency fails.
- Readiness rejects traffic when a required dependency is unavailable.
- High-latency mode keeps liveness and readiness green while the outside-in journey violates its SLO.
- Failure mode and latency details are restricted to administrative responses.
- The service can be reset without restarting the process.

## Current limitations

- Failure state is stored in memory and is not shared across multiple service instances.
- The downstream inventory dependency is simulated inside the demo service.
- OpenTelemetry metrics, logs, and traces are not included in Sprint 6.
- Administrative endpoints do not yet have authentication because the service is local and synthetic only.

## Next sprint connection

Sprint 7 will add OpenTelemetry instrumentation so the booking latency, request counts, error rates, logs, and traces can be collected and visualized through the observability stack. The new liveness, readiness, and synthetic endpoints provide clear signals for that instrumentation.
