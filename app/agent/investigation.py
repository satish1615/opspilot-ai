"""LangGraph orchestration for evidence-first incident investigation.

Sprint 8 combines persisted incident context, live observability evidence,
Qdrant-backed operational knowledge, LiteLLM model reasoning, grounding checks,
and a deterministic fallback that remains available when optional AI services
are disabled or unavailable.
"""

from __future__ import annotations

import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.observability import gather_observability_evidence
from app.agent.rag import retrieve_knowledge as retrieve_rag_knowledge
from app.agent.reasoning import generate_grounded_rca as generate_model_rca


WORKFLOW_NAME = "langgraph_incident_investigation_v2"


class InvestigationState(TypedDict, total=False):
    """State passed between LangGraph investigation nodes."""

    incident_id: str
    incident: dict
    evidence: list[dict]
    similar_incidents: list[dict]
    telemetry_evidence: list[dict]
    observability: dict
    knowledge_retrieval: dict
    retrieved_knowledge: list[dict]
    hypothesis: dict
    reasoning_mode: str
    generation_status: str
    model: str | None
    workflow_steps: list[str]
    status: str


def _append_step(state: InvestigationState, step: str) -> list[str]:
    return [*state.get("workflow_steps", []), step]


def collect_incident_context(state: InvestigationState) -> dict:
    """Collect approved runbook and historical evidence attached to the incident."""

    incident = state["incident"]
    analysis = incident.get("analysis", {})
    return {
        "evidence": list(analysis.get("evidence", [])),
        "similar_incidents": list(analysis.get("similar_incidents", [])),
        "workflow_steps": _append_step(state, "collect_incident_context"),
    }


def collect_observability_evidence(state: InvestigationState) -> dict:
    """Query Tempo, Mimir, and Loki for read-only operational evidence."""

    observability = gather_observability_evidence(state["incident"])
    return {
        "telemetry_evidence": list(observability.get("evidence", [])),
        "observability": {key: value for key, value in observability.items() if key != "evidence"},
        "workflow_steps": _append_step(state, "collect_observability_evidence"),
    }


def _build_rag_query(state: InvestigationState) -> str:
    incident = state["incident"]
    analysis = incident.get("analysis", {})
    telemetry = " ".join(
        item.get("summary", "") for item in state.get("telemetry_evidence", [])
    )
    return " ".join(
        part
        for part in [
            json.dumps(incident.get("input", {}), ensure_ascii=False, sort_keys=True),
            str(analysis.get("category", "")),
            str(analysis.get("subcategory", "")),
            telemetry,
        ]
        if part
    )


def retrieve_historical_knowledge(state: InvestigationState) -> dict:
    """Retrieve semantically similar runbooks and historical RCA knowledge."""

    retrieval = retrieve_rag_knowledge(
        _build_rag_query(state),
        exclude_incident_id=state["incident_id"],
    )
    items = list(retrieval.get("items", []))
    retrieval_summary = {key: value for key, value in retrieval.items() if key != "items"}
    return {
        "knowledge_retrieval": retrieval_summary,
        "retrieved_knowledge": items,
        "workflow_steps": _append_step(state, "retrieve_historical_knowledge"),
    }


def _fallback_hypothesis(state: InvestigationState) -> dict:
    analysis = state["incident"].get("analysis", {})
    issue_detected = bool(analysis.get("issue_detected"))

    if issue_detected:
        root_cause = analysis.get(
            "probable_cause",
            "The incident requires more evidence before a probable cause can be stated.",
        )
        recommended_action = analysis.get(
            "recommended_action",
            "Collect additional operational evidence before taking action.",
        )
        prevention = (
            "Retain the investigation evidence and add a validated prevention action after the incident is resolved."
        )
    else:
        root_cause = "No threshold breach or incident condition is currently detected."
        recommended_action = "Continue monitoring and retain the signal for trend analysis."
        prevention = "Continue baseline monitoring and review trends for early warning signals."

    return {
        "root_cause": root_cause,
        "recommended_action": recommended_action,
        "prevention": prevention,
        "confidence": int(analysis.get("confidence", 0)),
        "evidence_ids": [],
    }


def generate_grounded_hypothesis(state: InvestigationState) -> dict:
    """Ask the configured LLM for grounded RCA, otherwise retain safe fallback."""

    analysis = state["incident"].get("analysis", {})
    if not bool(analysis.get("issue_detected")):
        return {
            "hypothesis": _fallback_hypothesis(state),
            "reasoning_mode": "deterministic_fallback",
            "generation_status": "not_needed",
            "model": None,
            "workflow_steps": _append_step(state, "generate_grounded_hypothesis"),
        }

    generation = generate_model_rca(
        state["incident"],
        state.get("telemetry_evidence", []),
        state.get("retrieved_knowledge", []),
    )

    if generation.get("status") == "available":
        return {
            "hypothesis": generation["hypothesis"],
            "reasoning_mode": "llm_grounded",
            "generation_status": "available",
            "model": generation.get("model"),
            "workflow_steps": _append_step(state, "generate_grounded_hypothesis"),
        }

    return {
        "hypothesis": _fallback_hypothesis(state),
        "reasoning_mode": "deterministic_fallback",
        "generation_status": str(generation.get("status", "unavailable")),
        "model": None,
        "workflow_steps": _append_step(state, "generate_grounded_hypothesis"),
    }


def validate_grounding(state: InvestigationState) -> dict:
    """Classify whether the final hypothesis is LLM-grounded or a safe fallback."""

    analysis = state["incident"].get("analysis", {})
    issue_detected = bool(analysis.get("issue_detected"))
    has_context = bool(
        state.get("evidence")
        or state.get("similar_incidents")
        or state.get("telemetry_evidence")
        or state.get("retrieved_knowledge")
    )

    if not issue_detected:
        status = "no_issue_detected"
    elif state.get("reasoning_mode") == "llm_grounded" and state.get("generation_status") == "available":
        status = "grounded_rca"
    elif has_context:
        status = "grounded_fallback"
    else:
        status = "needs_more_evidence"

    return {
        "status": status,
        "workflow_steps": _append_step(state, "validate_grounding"),
    }


def build_investigation_graph():
    """Compile the Sprint 8 evidence -> RAG -> LLM investigation graph."""

    workflow = StateGraph(InvestigationState)
    workflow.add_node("collect_incident_context", collect_incident_context)
    workflow.add_node("collect_observability_evidence", collect_observability_evidence)
    workflow.add_node("retrieve_historical_knowledge", retrieve_historical_knowledge)
    workflow.add_node("generate_grounded_hypothesis", generate_grounded_hypothesis)
    workflow.add_node("validate_grounding", validate_grounding)

    workflow.add_edge(START, "collect_incident_context")
    workflow.add_edge("collect_incident_context", "collect_observability_evidence")
    workflow.add_edge("collect_observability_evidence", "retrieve_historical_knowledge")
    workflow.add_edge("retrieve_historical_knowledge", "generate_grounded_hypothesis")
    workflow.add_edge("generate_grounded_hypothesis", "validate_grounding")
    workflow.add_edge("validate_grounding", END)
    return workflow.compile()


_investigation_graph = build_investigation_graph()


def run_investigation(incident: dict) -> dict:
    """Run the LangGraph workflow for one persisted OpsPilot incident."""

    final_state = _investigation_graph.invoke(
        {
            "incident_id": incident["incident_id"],
            "incident": incident,
            "workflow_steps": [],
        }
    )

    return {
        "incident_id": incident["incident_id"],
        "status": final_state["status"],
        "workflow": WORKFLOW_NAME,
        "reasoning_mode": final_state.get("reasoning_mode", "deterministic_fallback"),
        "generation_status": final_state.get("generation_status", "unknown"),
        "model": final_state.get("model"),
        "steps": final_state["workflow_steps"],
        "evidence_count": len(final_state.get("evidence", [])),
        "similar_incident_count": len(final_state.get("similar_incidents", [])),
        "telemetry_evidence_count": len(final_state.get("telemetry_evidence", [])),
        "retrieved_knowledge_count": len(final_state.get("retrieved_knowledge", [])),
        "observability": final_state.get("observability", {}),
        "telemetry_evidence": final_state.get("telemetry_evidence", []),
        "knowledge_retrieval": final_state.get("knowledge_retrieval", {}),
        "retrieved_knowledge": final_state.get("retrieved_knowledge", []),
        "hypothesis": final_state["hypothesis"],
    }
