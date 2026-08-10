"""Read-only evidence collection from the local Sprint 7 LGTM stack.

This module deliberately performs queries only. It does not mutate telemetry
backends or execute remediation. Evidence collection is opt-in so tests and the
core API remain usable when the local observability stack is not running.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx


DEFAULT_SERVICE_NAME = "opspilot-synthetic-booking"
DEFAULT_TEMPO_URL = "http://localhost:3200"
DEFAULT_MIMIR_URL = "http://localhost:9009/prometheus"
DEFAULT_LOKI_URL = "http://localhost:3100"


@dataclass(frozen=True)
class ObservabilityConfig:
    enabled: bool
    service_name: str
    tempo_url: str
    mimir_url: str
    loki_url: str
    lookback_minutes: int
    timeout_seconds: float


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_observability_config() -> ObservabilityConfig:
    """Resolve safe local evidence-source settings from environment variables."""

    return ObservabilityConfig(
        enabled=_env_flag("OPSPILOT_OBSERVABILITY_ENABLED", default=False),
        service_name=os.getenv("OPSPILOT_OBSERVABILITY_SERVICE_NAME", DEFAULT_SERVICE_NAME),
        tempo_url=os.getenv("OPSPILOT_TEMPO_URL", DEFAULT_TEMPO_URL).rstrip("/"),
        mimir_url=os.getenv("OPSPILOT_MIMIR_URL", DEFAULT_MIMIR_URL).rstrip("/"),
        loki_url=os.getenv("OPSPILOT_LOKI_URL", DEFAULT_LOKI_URL).rstrip("/"),
        lookback_minutes=max(1, int(os.getenv("OPSPILOT_EVIDENCE_LOOKBACK_MINUTES", "15"))),
        timeout_seconds=max(0.2, float(os.getenv("OPSPILOT_EVIDENCE_TIMEOUT_SECONDS", "2.0"))),
    )


def _incident_time(incident: dict) -> datetime:
    raw = incident.get("created_at")
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _window(incident: dict, lookback_minutes: int) -> tuple[datetime, datetime]:
    incident_time = _incident_time(incident)
    now = datetime.now(timezone.utc)
    end = min(now, incident_time + timedelta(minutes=5))
    start = incident_time - timedelta(minutes=lookback_minutes)
    if end <= start:
        end = now
        start = now - timedelta(minutes=lookback_minutes)
    return start, end


def _query_tempo(
    client: httpx.Client,
    config: ObservabilityConfig,
    start: datetime,
    end: datetime,
) -> list[dict]:
    traceql = f'{{ resource.service.name = "{config.service_name}" }}'
    response = client.get(
        f"{config.tempo_url}/api/search",
        params={
            "q": traceql,
            "limit": 5,
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
        },
    )
    response.raise_for_status()
    traces = response.json().get("traces", [])

    evidence: list[dict] = []
    for trace in traces[:3]:
        trace_id = trace.get("traceID") or trace.get("traceId")
        name = trace.get("rootTraceName") or trace.get("rootServiceName") or "request trace"
        duration_ms = trace.get("durationMs")
        evidence.append(
            {
                "source": "tempo",
                "kind": "trace",
                "summary": f"Observed trace {name}",
                "details": {
                    "trace_id": trace_id,
                    "name": name,
                    "duration_ms": duration_ms,
                },
            }
        )
    return evidence


def _prometheus_scalar(payload: dict) -> float | None:
    results = payload.get("data", {}).get("result", [])
    if not results:
        return None
    value = results[0].get("value")
    if not isinstance(value, list) or len(value) < 2:
        return None
    try:
        return float(value[1])
    except (TypeError, ValueError):
        return None


def _query_mimir(client: httpx.Client, config: ObservabilityConfig) -> list[dict]:
    service_matcher = f'service_name="{config.service_name}"'
    queries = {
        "p95_http_duration_ms": (
            "histogram_quantile(0.95, sum by (le) "
            f"(http_server_duration_milliseconds_bucket{{{service_matcher}}}))"
        ),
        "http_5xx_observation_count": (
            "sum(http_server_duration_milliseconds_count{"
            f'{service_matcher},http_response_status_code=~"5.."' + "})"
        ),
    }

    evidence: list[dict] = []
    for metric_name, query in queries.items():
        response = client.get(f"{config.mimir_url}/api/v1/query", params={"query": query})
        response.raise_for_status()
        value = _prometheus_scalar(response.json())
        if value is None:
            continue
        evidence.append(
            {
                "source": "mimir",
                "kind": "metric",
                "summary": f"{metric_name}={round(value, 2)}",
                "details": {"metric": metric_name, "value": round(value, 4)},
            }
        )
    return evidence


def _query_loki(
    client: httpx.Client,
    config: ObservabilityConfig,
    start: datetime,
    end: datetime,
) -> list[dict]:
    query = (
        f'{{service_name="{config.service_name}"}} '
        '|~ "WARN|ERROR|breached|failed|unavailable"'
    )
    response = client.get(
        f"{config.loki_url}/loki/api/v1/query_range",
        params={
            "query": query,
            "start": str(int(start.timestamp() * 1_000_000_000)),
            "end": str(int(end.timestamp() * 1_000_000_000)),
            "limit": 20,
            "direction": "backward",
        },
    )
    response.raise_for_status()
    streams = response.json().get("data", {}).get("result", [])

    evidence: list[dict] = []
    for stream in streams:
        labels = stream.get("stream", {})
        for value in stream.get("values", []):
            if not isinstance(value, list) or len(value) < 2:
                continue
            evidence.append(
                {
                    "source": "loki",
                    "kind": "log",
                    "summary": str(value[1])[:500],
                    "details": {
                        "timestamp_ns": value[0],
                        "level": labels.get("severity_text") or labels.get("level"),
                    },
                }
            )
            if len(evidence) >= 5:
                return evidence
    return evidence


def gather_observability_evidence(
    incident: dict,
    *,
    config: ObservabilityConfig | None = None,
    client: httpx.Client | None = None,
) -> dict:
    """Collect read-only trace, metric, and log evidence for one incident.

    Each backend is isolated so one unavailable signal does not prevent the graph
    from investigating with whatever evidence remains available.
    """

    resolved = config or load_observability_config()
    if not resolved.enabled:
        return {
            "status": "disabled",
            "service_name": resolved.service_name,
            "sources": {"tempo": "disabled", "mimir": "disabled", "loki": "disabled"},
            "evidence": [],
        }

    start, end = _window(incident, resolved.lookback_minutes)
    owns_client = client is None
    http_client = client or httpx.Client(timeout=resolved.timeout_seconds)
    evidence: list[dict] = []
    source_status: dict[str, str] = {}

    collectors = {
        "tempo": lambda: _query_tempo(http_client, resolved, start, end),
        "mimir": lambda: _query_mimir(http_client, resolved),
        "loki": lambda: _query_loki(http_client, resolved, start, end),
    }

    try:
        for source, collector in collectors.items():
            try:
                source_evidence = collector()
                evidence.extend(source_evidence)
                source_status[source] = "available" if source_evidence else "no_data"
            except (httpx.HTTPError, ValueError, KeyError):
                source_status[source] = "unavailable"
    finally:
        if owns_client:
            http_client.close()

    available_sources = sum(status == "available" for status in source_status.values())
    if available_sources == 3:
        status = "available"
    elif available_sources > 0:
        status = "partial"
    else:
        status = "unavailable"

    return {
        "status": status,
        "service_name": resolved.service_name,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "sources": source_status,
        "evidence": evidence,
    }
