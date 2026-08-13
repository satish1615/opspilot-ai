"""LiteLLM-backed grounded RCA generation for OpsPilot AI.

The model is allowed to reason only over an explicit evidence catalogue. Model
output must cite catalogue IDs; unsupported or malformed output is rejected so
the LangGraph workflow can fall back safely to deterministic analysis.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

DEFAULT_LLM_MODEL = "gemini/gemini-2.5-flash"


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool
    model: str
    timeout_seconds: float
    temperature: float


class GroundedRCA(BaseModel):
    root_cause: str = Field(min_length=10, max_length=2000)
    recommended_action: str = Field(min_length=10, max_length=2000)
    prevention: str = Field(min_length=10, max_length=2000)
    confidence: int = Field(ge=0, le=100)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_llm_config() -> LLMConfig:
    """Resolve the model gateway configuration.

    The default model is a low-latency Gemini Flash model, but the LiteLLM model
    string is environment-configurable so the workflow remains provider-neutral.
    """

    return LLMConfig(
        enabled=_env_flag("OPSPILOT_LLM_ENABLED", default=False),
        model=os.getenv("OPSPILOT_LLM_MODEL", DEFAULT_LLM_MODEL),
        timeout_seconds=max(1.0, float(os.getenv("OPSPILOT_LLM_TIMEOUT_SECONDS", "20"))),
        temperature=max(0.0, min(1.0, float(os.getenv("OPSPILOT_LLM_TEMPERATURE", "0.1")))),
    )


def build_evidence_catalog(
    incident: dict,
    telemetry_evidence: list[dict],
    retrieved_knowledge: list[dict],
) -> list[dict]:
    """Create compact evidence records with IDs the LLM must cite."""

    catalog: list[dict] = []

    raw_input = incident.get("input", {})
    catalog.append(
        {
            "id": "A1",
            "source": "incident",
            "text": json.dumps(raw_input, ensure_ascii=False, sort_keys=True),
        }
    )

    for index, evidence in enumerate(incident.get("analysis", {}).get("evidence", []), start=1):
        catalog.append(
            {
                "id": f"B{index}",
                "source": "approved_runbook",
                "text": (
                    f"{evidence.get('title', 'Runbook')}: "
                    f"{' '.join(evidence.get('safe_first_steps', []))}"
                ),
            }
        )

    for index, item in enumerate(telemetry_evidence, start=1):
        catalog.append(
            {
                "id": f"T{index}",
                "source": item.get("source", "telemetry"),
                "text": f"{item.get('summary', '')} | {json.dumps(item.get('details', {}), sort_keys=True)}",
            }
        )

    for index, item in enumerate(retrieved_knowledge, start=1):
        catalog.append(
            {
                "id": f"K{index}",
                "source": item.get("source_type", "knowledge"),
                "text": f"{item.get('title', 'Knowledge')}: {item.get('text', '')}",
            }
        )

    return catalog


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    if stripped.lower().startswith("json\n"):
        stripped = stripped[5:].strip()
    return stripped


def _validate_citations(rca: GroundedRCA, catalog: list[dict]) -> tuple[bool, list[str]]:
    valid_ids = {item["id"] for item in catalog}
    cited_ids = list(dict.fromkeys(rca.evidence_ids))
    if any(item not in valid_ids for item in cited_ids):
        return False, cited_ids

    stronger_evidence = {
        item["id"]
        for item in catalog
        if item["id"].startswith(("T", "K", "B"))
    }
    if stronger_evidence and not stronger_evidence.intersection(cited_ids):
        return False, cited_ids
    return bool(cited_ids), cited_ids


def generate_grounded_rca(
    incident: dict,
    telemetry_evidence: list[dict],
    retrieved_knowledge: list[dict],
    *,
    config: LLMConfig | None = None,
    completion_fn=None,
) -> dict:
    """Generate and validate one evidence-grounded RCA through LiteLLM."""

    resolved = config or load_llm_config()
    catalog = build_evidence_catalog(incident, telemetry_evidence, retrieved_knowledge)

    if not resolved.enabled:
        return {
            "status": "disabled",
            "model": resolved.model,
            "evidence_catalog": catalog,
        }

    try:
        if completion_fn is None:
            from litellm import completion

            completion_fn = completion

        evidence_text = "\n".join(
            f"[{item['id']}] {item['source']}: {item['text']}" for item in catalog
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the RCA reasoning component of an SRE assistant. "
                    "Use only the supplied evidence. Do not invent metrics, logs, traces, incidents, "
                    "or infrastructure facts. Return JSON only with keys root_cause, recommended_action, "
                    "prevention, confidence, and evidence_ids. evidence_ids must contain only IDs from "
                    "the supplied catalogue. Recommendations must be diagnostic or low-risk; do not claim "
                    "that remediation has already been executed."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Create a concise probable RCA for this incident.\n\n"
                    f"Evidence catalogue:\n{evidence_text}\n\n"
                    "Return one JSON object. Confidence must be an integer from 0 to 100."
                ),
            },
        ]

        response = completion_fn(
            model=resolved.model,
            messages=messages,
            temperature=resolved.temperature,
            timeout=resolved.timeout_seconds,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM returned empty content")

        parsed = json.loads(_strip_json_fence(content))
        rca = GroundedRCA.model_validate(parsed)
        citations_valid, cited_ids = _validate_citations(rca, catalog)
        if not citations_valid:
            return {
                "status": "rejected_unsupported_citations",
                "model": resolved.model,
                "evidence_catalog": catalog,
                "cited_evidence_ids": cited_ids,
            }

        return {
            "status": "available",
            "model": resolved.model,
            "evidence_catalog": catalog,
            "hypothesis": {
                "root_cause": rca.root_cause,
                "recommended_action": rca.recommended_action,
                "prevention": rca.prevention,
                "confidence": rca.confidence,
                "evidence_ids": cited_ids,
            },
        }
    except (json.JSONDecodeError, ValidationError, ValueError, IndexError, AttributeError) as exc:
        return {
            "status": "invalid_model_output",
            "model": resolved.model,
            "evidence_catalog": catalog,
            "error_type": type(exc).__name__,
        }
    except Exception as exc:  # Provider/API failures must preserve safe fallback behavior.
        return {
            "status": "unavailable",
            "model": resolved.model,
            "evidence_catalog": catalog,
            "error_type": type(exc).__name__,
        }
