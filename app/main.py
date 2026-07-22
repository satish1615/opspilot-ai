from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.analyzer import analyze_alert


app = FastAPI(
    title="OpsPilot AI",
    description="Agentic SRE platform for incident investigation and remediation",
    version="0.3.0",
)


class Alert(BaseModel):
    alert_type: Literal[
        "HIGH_CPU",
        "HIGH_MEMORY",
        "DISK_FULL",
        "SERVICE_DOWN",
        "HTTP_5XX_SPIKE",
    ]
    server: str = Field(min_length=2)
    value: float
    threshold: float
    severity: Literal["low", "medium", "high", "critical"]


@app.get("/")
def home():
    return {"message": "OpsPilot AI backend is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/alerts", status_code=201)
def receive_alert(alert: Alert):
    analysis = analyze_alert(
        alert_type=alert.alert_type,
        value=alert.value,
        threshold=alert.threshold,
    )

    return {
        "alert_id": str(uuid4()),
        "status": "analysed",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "alert": alert,
        "analysis": analysis,
    }