"""Pydantic request and response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

AlertType = Literal[
    "HIGH_CPU",
    "HIGH_MEMORY",
    "DISK_FULL",
    "SERVICE_DOWN",
    "HTTP_5XX_SPIKE",
]
Severity = Literal["low", "medium", "high", "critical"]
ImpactUrgency = Literal["low", "medium", "high"]
Priority = Literal["P1", "P2", "P3", "P4"]
SourceType = Literal["monitoring_alert", "human_incident"]


class MonitoringAlertCreate(BaseModel):
    alert_type: AlertType
    server: str = Field(min_length=2, max_length=150)
    value: float
    threshold: float
    severity: Severity | None = None
    business_service: str | None = Field(default=None, max_length=150)

    @model_validator(mode="after")
    def validate_threshold(self) -> "MonitoringAlertCreate":
        if self.alert_type != "SERVICE_DOWN" and self.threshold <= 0:
            raise ValueError("threshold must be greater than zero for metric alerts")
        return self


class HumanIncidentCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10, max_length=4000)
    impact: ImpactUrgency
    urgency: ImpactUrgency
    affected_users: int = Field(default=1, ge=1, le=1_000_000)
    business_service: str | None = Field(default=None, max_length=150)
    workaround_available: bool = False


class RemediationApprovalRequest(BaseModel):
    approved_by: str = Field(min_length=2, max_length=120)
    note: str | None = Field(default=None, max_length=1000)


class EvidenceItem(BaseModel):
    runbook_id: str
    title: str
    matched_keywords: list[str]
    safe_first_steps: list[str]


class SimilarIncident(BaseModel):
    incident_id: str
    title: str
    category: str
    priority: Priority
    similarity_score: int


class AnalysisResponse(BaseModel):
    issue_detected: bool
    technical_severity: Severity
    priority: Priority
    category: str
    subcategory: str
    assignment_group: str
    probable_cause: str
    recommended_action: str
    confidence: int = Field(ge=0, le=100)
    evidence: list[EvidenceItem]
    similar_incidents: list[SimilarIncident]
    approval_required: bool
    remediation_approved: bool


class IncidentResponse(BaseModel):
    incident_id: str
    source_type: SourceType
    status: str
    created_at: str
    input: dict
    analysis: AnalysisResponse
    approval: dict


class IncidentListResponse(BaseModel):
    total: int
    incidents: list[IncidentResponse]


class InvestigationHypothesis(BaseModel):
    root_cause: str
    recommended_action: str
    confidence: int = Field(ge=0, le=100)


class TelemetryEvidenceItem(BaseModel):
    source: Literal["tempo", "mimir", "loki"]
    kind: Literal["trace", "metric", "log"]
    summary: str
    details: dict


class InvestigationResponse(BaseModel):
    incident_id: str
    status: Literal["grounded_baseline", "needs_more_evidence", "no_issue_detected"]
    workflow: str
    reasoning_mode: str
    steps: list[str]
    evidence_count: int = Field(ge=0)
    similar_incident_count: int = Field(ge=0)
    telemetry_evidence_count: int = Field(ge=0)
    observability: dict
    telemetry_evidence: list[TelemetryEvidenceItem]
    hypothesis: InvestigationHypothesis
