from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

import app.agent.investigation as investigation_module
from app.agent.investigation import run_investigation
from app.agent.observability import ObservabilityConfig, gather_observability_evidence
from app.agent.rag import retrieve_knowledge
from app.agent.reasoning import LLMConfig, generate_grounded_rca
from app.main import app


def _sample_incident() -> dict:
    return {
        "incident_id": "INC-SPRINT8-001",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "alert_type": "HIGH_CPU",
            "server": "booking-server-01",
            "value": 92,
            "threshold": 80,
            "severity": "high",
            "business_service": "Synthetic Booking",
        },
        "analysis": {
            "issue_detected": True,
            "category": "Compute",
            "subcategory": "CPU",
            "probable_cause": "CPU contention may be increasing request latency.",
            "recommended_action": "Inspect top CPU-consuming processes and recent changes.",
            "confidence": 90,
            "evidence": [
                {
                    "runbook_id": "RB-CPU-001",
                    "title": "High CPU investigation",
                    "matched_keywords": ["cpu"],
                    "safe_first_steps": ["Inspect top CPU-consuming processes."],
                }
            ],
            "similar_incidents": [],
        },
    }


def test_langgraph_investigation_runs_safe_fallback_when_ai_is_disabled(monkeypatch):
    monkeypatch.setenv("OPSPILOT_OBSERVABILITY_ENABLED", "false")
    monkeypatch.setenv("OPSPILOT_RAG_ENABLED", "false")
    monkeypatch.setenv("OPSPILOT_LLM_ENABLED", "false")

    result = run_investigation(_sample_incident())

    assert result["incident_id"] == "INC-SPRINT8-001"
    assert result["workflow"] == "langgraph_incident_investigation_v2"
    assert result["reasoning_mode"] == "deterministic_fallback"
    assert result["generation_status"] == "disabled"
    assert result["status"] == "grounded_fallback"
    assert result["steps"] == [
        "collect_incident_context",
        "collect_observability_evidence",
        "retrieve_historical_knowledge",
        "generate_grounded_hypothesis",
        "validate_grounding",
    ]
    assert result["evidence_count"] == 1
    assert result["telemetry_evidence_count"] == 0
    assert result["retrieved_knowledge_count"] == 0
    assert result["observability"]["status"] == "disabled"
    assert result["knowledge_retrieval"]["status"] == "disabled"
    assert result["hypothesis"]["confidence"] == 90
    assert result["hypothesis"]["prevention"]


def test_langgraph_uses_rag_and_grounded_llm_when_available(monkeypatch):
    monkeypatch.setenv("OPSPILOT_OBSERVABILITY_ENABLED", "false")

    def fake_retrieve(query: str, *, exclude_incident_id: str | None = None):
        assert "HIGH_CPU" in query
        assert exclude_incident_id == "INC-SPRINT8-001"
        return {
            "status": "available",
            "collection": "opspilot_knowledge",
            "embedding_model": "test-embedding",
            "documents_indexed": 8,
            "items": [
                {
                    "knowledge_id": "investigation:old-1",
                    "source_type": "historical_rca",
                    "title": "Previous booking latency RCA",
                    "text": "Database connection exhaustion caused retries and high latency.",
                    "score": 0.91,
                    "metadata": {"incident_id": "OLD-1"},
                }
            ],
        }

    def fake_generate(incident: dict, telemetry_evidence: list[dict], retrieved_knowledge: list[dict]):
        assert incident["incident_id"] == "INC-SPRINT8-001"
        assert retrieved_knowledge[0]["knowledge_id"] == "investigation:old-1"
        return {
            "status": "available",
            "model": "test/provider-model",
            "hypothesis": {
                "root_cause": "The current symptoms are consistent with database connection exhaustion causing retries.",
                "recommended_action": "Check database connectivity and connection-pool saturation before any restart.",
                "prevention": "Monitor connection-pool utilization and use bounded retry/backoff settings.",
                "confidence": 82,
                "evidence_ids": ["K1"],
            },
        }

    monkeypatch.setattr(investigation_module, "retrieve_rag_knowledge", fake_retrieve)
    monkeypatch.setattr(investigation_module, "generate_model_rca", fake_generate)

    result = run_investigation(_sample_incident())

    assert result["status"] == "grounded_rca"
    assert result["reasoning_mode"] == "llm_grounded"
    assert result["generation_status"] == "available"
    assert result["model"] == "test/provider-model"
    assert result["retrieved_knowledge_count"] == 1
    assert result["hypothesis"]["evidence_ids"] == ["K1"]
    assert "connection exhaustion" in result["hypothesis"]["root_cause"]


def test_observability_collector_parses_tempo_mimir_and_loki():
    config = ObservabilityConfig(
        enabled=True,
        service_name="opspilot-synthetic-booking",
        tempo_url="http://tempo",
        mimir_url="http://mimir/prometheus",
        loki_url="http://loki",
        lookback_minutes=15,
        timeout_seconds=1.0,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/search":
            return httpx.Response(
                200,
                json={
                    "traces": [
                        {
                            "traceID": "trace-123",
                            "rootTraceName": "GET /synthetic/booking-check",
                            "durationMs": 1501.14,
                        }
                    ]
                },
            )
        if request.url.path == "/prometheus/api/v1/query":
            query = request.url.params.get("query", "")
            value = "2" if "http_response_status_code" in query else "1500.5"
            return httpx.Response(
                200,
                json={"status": "success", "data": {"result": [{"value": [0, value]}]},
            )
        if request.url.path == "/loki/api/v1/query_range":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "result": [
                            {
                                "stream": {"severity_text": "WARN"},
                                "values": [
                                    ["1", "Synthetic booking check breached the configured SLO"]
                                ],
                            }
                        ]
                    },
                },
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = gather_observability_evidence(_sample_incident(), config=config, client=client)

    assert result["status"] == "available"
    assert result["sources"] == {
        "tempo": "available",
        "mimir": "available",
        "loki": "available",
    }
    assert {item["source"] for item in result["evidence"]} == {"tempo", "mimir", "loki"}
    assert any(
        item["details"].get("duration_ms") == 1501.14 for item in result["evidence"]
    )
    assert any(
        item["details"].get("metric") == "p95_http_duration_ms" for item in result["evidence"]
    )


def test_observability_collector_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OPSPILOT_OBSERVABILITY_ENABLED", raising=False)
    result = gather_observability_evidence(_sample_incident())

    assert result["status"] == "disabled"
    assert result["evidence"] == []
    assert result["sources"]["tempo"] == "disabled"


def test_rag_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OPSPILOT_RAG_ENABLED", raising=False)
    result = retrieve_knowledge("booking latency")

    assert result["status"] == "disabled"
    assert result["items"] == []


def test_litellm_reasoning_accepts_only_grounded_citations():
    config = LLMConfig(
        enabled=True,
        model="test/model",
        timeout_seconds=1.0,
        temperature=0.0,
    )

    def fake_completion(**kwargs):
        assert kwargs["model"] == "test/model"
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"root_cause":"Observed warning evidence indicates dependency failure is driving retries.",'
                            '"recommended_action":"Inspect the failing dependency and connectivity before restarting anything.",'
                            '"prevention":"Add dependency health monitoring and bounded retry/backoff controls.",'
                            '"confidence":84,"evidence_ids":["T1"]}'
                        )
                    )
                )
            ]
        )

    result = generate_grounded_rca(
        _sample_incident(),
        [
            {
                "source": "loki",
                "kind": "log",
                "summary": "ERROR dependency unavailable",
                "details": {"level": "ERROR"},
            }
        ],
        [],
        config=config,
        completion_fn=fake_completion,
    )

    assert result["status"] == "available"
    assert result["hypothesis"]["confidence"] == 84
    assert result["hypothesis"]["evidence_ids"] == ["T1"]


def test_litellm_reasoning_rejects_unknown_evidence_ids():
    config = LLMConfig(
        enabled=True,
        model="test/model",
        timeout_seconds=1.0,
        temperature=0.0,
    )

    def fake_completion(**kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"root_cause":"This statement is long enough but cites evidence that does not exist.",'
                            '"recommended_action":"Collect evidence and inspect the dependency before taking action.",'
                            '"prevention":"Add stronger monitoring and retain validated incident knowledge.",'
                            '"confidence":50,"evidence_ids":["T99"]}'
                        )
                    )
                )
            ]
        )

    result = generate_grounded_rca(
        _sample_incident(),
        [
            {
                "source": "loki",
                "kind": "log",
                "summary": "ERROR dependency unavailable",
                "details": {},
            }
        ],
        [],
        config=config,
        completion_fn=fake_completion,
    )

    assert result["status"] == "rejected_unsupported_citations"


def test_investigation_endpoint_persists_result(monkeypatch):
    monkeypatch.setenv("OPSPILOT_OBSERVABILITY_ENABLED", "false")
    monkeypatch.setenv("OPSPILOT_RAG_ENABLED", "false")
    monkeypatch.setenv("OPSPILOT_LLM_ENABLED", "false")

    with TestClient(app) as client:
        created = client.post(
            "/alerts",
            json={
                "alert_type": "HIGH_CPU",
                "server": "sprint8-demo-server",
                "business_service": "Synthetic Booking",
                "value": 92,
                "threshold": 80,
                "severity": "high",
            },
        )
        assert created.status_code == 201

        incident_id = created.json()["incident_id"]
        investigated = client.post(f"/incidents/{incident_id}/investigate")
        persisted = client.get(f"/incidents/{incident_id}/investigation")

    assert investigated.status_code == 200
    body = investigated.json()
    assert body["incident_id"] == incident_id
    assert body["workflow"] == "langgraph_incident_investigation_v2"
    assert body["reasoning_mode"] == "deterministic_fallback"
    assert body["status"] == "grounded_fallback"
    assert body["persistence"]["status"] == "saved"

    assert persisted.status_code == 200
    saved = persisted.json()
    assert saved["incident_id"] == incident_id
    assert saved["investigation_id"] == body["persistence"]["investigation_id"]
    assert saved["hypothesis"]["root_cause"] == body["hypothesis"]["root_cause"]


def test_investigation_endpoint_returns_404_for_unknown_incident(monkeypatch):
    monkeypatch.setenv("OPSPILOT_OBSERVABILITY_ENABLED", "false")
    monkeypatch.setenv("OPSPILOT_RAG_ENABLED", "false")
    monkeypatch.setenv("OPSPILOT_LLM_ENABLED", "false")
    with TestClient(app) as client:
        response = client.post("/incidents/does-not-exist/investigate")

    assert response.status_code == 404
    assert response.json()["detail"] == "Incident not found"
