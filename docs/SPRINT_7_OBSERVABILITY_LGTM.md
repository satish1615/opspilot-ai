# Sprint 7 — OpenTelemetry + LGTM Observability

## Objective

Make the synthetic booking workload observable through vendor-neutral telemetry and a local LGTM stack so later agentic investigation can use real metrics, traces, and logs as evidence.

## Implemented architecture

```text
Synthetic FastAPI booking service
        |
        | OpenTelemetry SDK + FastAPI instrumentation
        | OTLP HTTP
        v
OpenTelemetry Collector
   |          |          |
   v          v          v
 Tempo      Mimir       Loki
 traces     metrics      logs
      \        |        /
             Grafana
```

The Collector is the telemetry routing layer. The application exports to the Collector rather than directly coupling itself to Grafana backends.

## Implemented telemetry

### Traces

- FastAPI requests are auto-instrumented.
- The service resource name defaults to `opspilot-synthetic-booking`.
- Traces are exported over OTLP HTTP to the Collector and routed to Tempo.
- Swagger/OpenAPI and liveness URLs are excluded from tracing to reduce noise.

### Metrics

FastAPI instrumentation emits HTTP server metrics including request duration, active requests, request size, and response size. The Collector converts them to Prometheus remote write and sends them to Mimir.

Verified Mimir metric names include:

- `http_server_active_requests`
- `http_server_duration_milliseconds_bucket`
- `http_server_duration_milliseconds_count`
- `http_server_duration_milliseconds_sum`
- `http_server_request_size_bytes_*`
- `http_server_response_size_bytes_*`
- `target_info`

### Logs

The synthetic service uses an application logger for incident-relevant events. OpenTelemetry logging sends these records over OTLP HTTP to the Collector and then to Loki.

Events include:

- synthetic service reset
- failure-mode changes
- healthy synthetic booking checks
- booking SLO violations
- synthetic dependency failures

## Local LGTM stack

`docker-compose.observability.yml` starts:

- OpenTelemetry Collector Contrib
- Tempo
- Mimir
- Loki
- Grafana

This stack is intentionally local and hackathon-scoped. Tempo, Mimir, and Loki use single-node/filesystem-oriented demo configurations rather than production HA storage.

Grafana is provisioned with:

- `OpsPilot Mimir`
- `OpsPilot Tempo`
- `OpsPilot Loki`
- `OpsPilot AI - Synthetic Booking Observability` dashboard

Local Grafana credentials are `admin` / `admin` and are only for this demo environment.

## Run the observability stack

```bash
docker compose -f docker-compose.observability.yml up -d
```

Check status:

```bash
docker compose -f docker-compose.observability.yml ps
```

Backend readiness endpoints:

```bash
curl -s http://localhost:3200/ready
curl -s http://localhost:9009/ready
curl -s http://localhost:3100/ready
curl -s http://localhost:3000/api/health
```

## Start the synthetic service with telemetry

```bash
OTEL_ENABLED=true \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
OTEL_SERVICE_NAME=opspilot-synthetic-booking \
python -m uvicorn demo_service.main:app --host 127.0.0.1 --port 8001
```

Telemetry is disabled by default so unit tests and the synthetic service can run without an external Collector.

## Run the repeatable incident demo

```bash
bash scripts/run_observability_demo.sh
```

The script exercises:

| Scenario | Expected synthetic result |
|---|---|
| Healthy | `status=healthy`, fast response |
| High latency | approximately 1500 ms, `status=degraded`, `reason=slo_violation` |
| Dependency failure | `status=failed`, `reason=dependency_unavailable` |
| Reset | returns workload to healthy state |

## Verified evidence

Manual verification on 7 Aug 2026 confirmed:

- Collector received OTLP HTTP from the Python service.
- Collector received traces, metrics, and logs from `opspilot-synthetic-booking`.
- A demo run produced 23 spans and four HTTP metric families before application logging was added.
- A later logging-enabled run showed Collector `traces`, `metrics`, and `logs` signals together.
- Healthy synthetic check returned approximately 0.01 ms in the measured local run.
- High-latency mode produced approximately 1500–1501 ms and breached the 500 ms SLO.
- Dependency-failure mode returned `dependency_unavailable`.
- Tempo became ready and traces were visible in Grafana for `opspilot-synthetic-booking`.
- Mimir returned the OpenTelemetry HTTP metric names through its Prometheus API.
- Loki returned `service_name` as a label and `opspilot-synthetic-booking` as a stored label value.
- Existing 21 automated tests passed after OpenTelemetry logging was introduced.

Two telemetry-configuration unit tests were added after that verification and require the final regression run before Sprint 7 is merged.

## Grafana investigation

Open Grafana at:

```text
http://localhost:3000
```

The provisioned dashboard provides a compact metrics/log view. For trace investigation, use **Explore → OpsPilot Tempo** with TraceQL:

```text
{ resource.service.name = "opspilot-synthetic-booking" }
```

Tempo is a trace store, not the OpsPilot incident database. An `INC` identifier is not expected in this Sprint 7 trace view unless a later OpsPilot incident workflow explicitly correlates one with the trace.

## Safety and truthfulness boundaries

- No customer or production data is used.
- No production cloud credentials are used.
- Failure modes are synthetic, allowlisted, and reversible.
- The downstream inventory outage is simulated inside the synthetic service; it is not yet a separate distributed dependency.
- The local LGTM stack is not presented as production-ready.
- Sprint 7 provides telemetry evidence only. LangGraph investigation, LLM reasoning, RAG, incident-to-trace correlation, and autonomous remediation are not Sprint 7 capabilities.

## Current limitations

- Tempo/Mimir/Loki are local single-node demo services.
- Application failure state remains in memory.
- The inventory dependency is simulated rather than a separate service, so the demo does not yet produce a true multi-service distributed trace.
- Grafana's Tempo Search UI showed an intermittent front-end error during manual testing; direct TraceQL returned trace results and should be used for the demo until the UI issue is revisited during final hardening.
- No production authentication, TLS, retention policy, external object storage, HA, or scaling configuration is included.

## Acceptance criteria

Sprint 7 is ready for integration when:

- all automated tests pass on the sprint branch;
- Collector, Tempo, Mimir, Loki, and Grafana start successfully;
- traces reach Tempo and can be queried;
- metrics reach Mimir and can be queried;
- logs reach Loki and can be queried;
- healthy, high-latency, and dependency-failure scenarios produce distinguishable telemetry;
- the provisioned Grafana dashboard loads without configuration errors;
- documentation matches verified implementation;
- the sprint is reviewed before merge into `develop/usecase-115`.

## Next sprint connection

Sprint 8 will consume this evidence layer for agentic investigation. The planned direction is to connect OpsPilot incident context to metrics, traces, logs, historical incident knowledge, LangGraph orchestration, RAG, and an LLM through LiteLLM. Those capabilities must be implemented and verified before being claimed.
