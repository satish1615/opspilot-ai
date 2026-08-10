"""LangGraph orchestration for evidence-first incident investigation.

Sprint 8 begins with a deterministic fallback and then enriches that state with
read-only observability evidence. LLM reasoning is added only after the evidence
contract is proven so generated RCA can be grounded instead of invented.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.observability import gather_observability_evidence


WORKFLOW_NAME = "langgraph_incident_investigation_v1"
REASONING_MODE = "deterministic_foundation"


class InvestigationState(TypedDict, total=False):
    """State passed between LangGraph investigation nodes."""

    incident_id: str
    incident: dict
    evidence: list[dict]
    similar_incidents: list[dict]
    telemetry_evidence: list[dict]
    observability: dict
    hypothesis: dict
    workflow_steps: list[str]
    status: str


def _append_step(state: InvestigationState, step: str) -> list[str]:
    return [*state.get("workflow_steps", []), step]


def collect_incident_context(state: InvestigationState) -> dict:
    """Collect runbook and historical evidence already attached to the incident."""

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


def build_initial_hypothesis(state: InvestigationState) -> dict:
    """Build a transparent baseline hypothesis from deterministic analysis.

    This node deliberately does not call an LLM. Its purpose is to remain a safe
    fallback while Sprint 8 adds vector retrieval and model-backed reasoning.
    """

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
    else:
        root_cause = "No threshold breach or incident condition is currently detected."
        recommended_action = "Continue monitoring and retain the signal for trend analysis."

    return {
        "hypothesis": {
            "root_cause": root_cause,
            "recommended_action": recommended_action,
            "confidence": int(analysis.get("confidence", 0)),
        },
        "workflow_steps": _append_step(state, "build_initial_hypothesis"),
    }


def validate_grounding(state: InvestigationState) -> dict:
    """Mark whether the hypothesis has project or live telemetry evidence."""

    analysis = state["incident"].get("analysis", {})
    issue_detected = bool(analysis.get("issue_detected"))
    has_context = bool(
        state.get("evidence")
        or state.get("similar_incidents")
        or state.get("telemetry_evidence")
    )

    if not issue_detected:
        status = "no_issue_detected"
    elif has_context:
        status = "grounded_baseline"
    else:
        status = "needs_more_evidence"

    return {
        "status": status,
        "workflow_steps": _append_step(state, "validate_grounding"),
    }


def build_investigation_graph():
    """Compile the Sprint 8 incident-investigation graph."""

    workflow = StateGraph(InvestigationState)
    workflow.add_node("collect_incident_context", collect_incident_context)
    workflow.add_node("collect_observability_evidence", collect_observability_evidence)
    workflow.add_node("build_initial_hypothesis", build_initial_hypothesis)
    workflow.add_node("validate_grounding", validate_grounding)

    workflow.add_edge(START, "collect_incident_context")
    workflow.add_edge("collect_incident_context", "collect_observability_evidence")
    workflow.add_edge("collect_observability_evidence", "build_initial_hypothesis")
    workflow.add_edge("build_initial_hypothesis", "validate_grounding")
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
        "reasoning_mode": REASONING_MODE,
        "steps": final_state["workflow_steps"],
        "evidence_count": len(final_state.get("evidence", [])),
        "similar_incident_count": len(final_state.get("similar_incidents", [])),
        "telemetry_evidence_count": len(final_state.get("telemetry_evidence", [])),
        "observability": final_state.get("observability", {}),
        "telemetry_evidence": final_state.get("telemetry_evidence", []),
        "hypothesis": final_state["hypothesis"],
    }
