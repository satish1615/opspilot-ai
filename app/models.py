"""SQLAlchemy models used by OpsPilot AI."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Incident(Base):
    """Persisted monitoring alert or human-created incident."""

    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="analysed", index=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    server: Mapped[str | None] = mapped_column(String(150), nullable=True)
    business_service: Mapped[str | None] = mapped_column(String(150), nullable=True)

    alert_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    reported_severity: Mapped[str | None] = mapped_column(String(20), nullable=True)

    impact: Mapped[str | None] = mapped_column(String(20), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    affected_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workaround_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    issue_detected: Mapped[bool] = mapped_column(Boolean)
    technical_severity: Mapped[str] = mapped_column(String(20), index=True)
    priority: Mapped[str] = mapped_column(String(2), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    subcategory: Mapped[str] = mapped_column(String(80))
    assignment_group: Mapped[str] = mapped_column(String(120))
    probable_cause: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    confidence: Mapped[int] = mapped_column(Integer)

    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    similar_incidents_json: Mapped[str] = mapped_column(Text, default="[]")
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True)
    remediation_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approval_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
