"""Synthetic airline-style booking service for controlled incident scenarios.

The service intentionally supports safe failure injection. It uses only synthetic
records and must never be connected to customer or production data.
"""

from __future__ import annotations

import asyncio
from enum import Enum
from threading import RLock

from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class FailureMode(str, Enum):
    """Supported, reversible demo failure modes."""

    HEALTHY = "healthy"
    HIGH_LATENCY = "high_latency"
    DEPENDENCY_FAILURE = "dependency_failure"


class FailureModeRequest(BaseModel):
    """Configuration accepted by the failure-injection endpoint."""

    mode: FailureMode
    latency_ms: int = Field(default=1500, ge=1, le=10_000)


class DemoServiceState:
    """Thread-safe in-memory state for the synthetic service."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._mode = FailureMode.HEALTHY
        self._latency_ms = 1500

    def snapshot(self) -> dict[str, str | int | bool]:
        with self._lock:
            return {
                "mode": self._mode.value,
                "latency_ms": self._latency_ms,
                "synthetic": True,
            }

    def configure(self, mode: FailureMode, latency_ms: int) -> dict[str, str | int | bool]:
        with self._lock:
            self._mode = mode
            self._latency_ms = latency_ms
            return self.snapshot()

    def reset(self) -> dict[str, str | int | bool]:
        return self.configure(FailureMode.HEALTHY, 1500)


state = DemoServiceState()

app = FastAPI(
    title="OpsPilot Synthetic Booking Service",
    description=(
        "A controlled, synthetic service used to generate healthy, high-latency, "
        "and dependency-failure scenarios for the OpsPilot AI hackathon demo."
    ),
    version="0.1.0",
)


@app.get("/")
def service_info() -> dict:
    """Return service identity and current reversible demo state."""

    return {
        "name": "OpsPilot Synthetic Booking Service",
        "purpose": "Controlled telemetry and remediation demonstration",
        **state.snapshot(),
    }


@app.get("/health", response_model=None)
def health_check() -> JSONResponse | dict:
    """Return a deliberately shallow health check.

    High-latency mode still returns HTTP 200. This models the official use-case
    scenario where infrastructure dashboards remain green while a real customer
    journey is degraded. Dependency failure returns HTTP 503.
    """

    snapshot = state.snapshot()
    if snapshot["mode"] == FailureMode.DEPENDENCY_FAILURE.value:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "dependency": "synthetic-inventory-service",
                **snapshot,
            },
        )

    return {
        "status": "healthy",
        "check_type": "shallow",
        **snapshot,
    }


@app.get("/bookings/{booking_id}")
async def read_booking(
    booking_id: str = Path(min_length=4, max_length=40, pattern=r"^[A-Za-z0-9-]+$")
) -> dict:
    """Return a synthetic booking while applying the selected failure mode."""

    snapshot = state.snapshot()

    if snapshot["mode"] == FailureMode.HIGH_LATENCY.value:
        await asyncio.sleep(int(snapshot["latency_ms"]) / 1000)

    if snapshot["mode"] == FailureMode.DEPENDENCY_FAILURE.value:
        raise HTTPException(
            status_code=503,
            detail="Synthetic inventory dependency is unavailable",
        )

    return {
        "booking_id": booking_id.upper(),
        "journey_status": "confirmed",
        "passenger": "Synthetic Traveller",
        "route": "DEMO-ORIGIN to DEMO-DESTINATION",
        "synthetic": True,
        "service_mode": snapshot["mode"],
    }


@app.get("/admin/state")
def read_failure_state() -> dict:
    """Expose the current demo state for scripts and test automation."""

    return state.snapshot()


@app.post("/admin/failure-mode")
def set_failure_mode(request: FailureModeRequest) -> dict:
    """Enable one safe and reversible failure scenario."""

    return {
        "message": "Synthetic failure mode updated",
        **state.configure(request.mode, request.latency_ms),
    }


@app.post("/admin/reset")
def reset_failure_mode() -> dict:
    """Return the service to its healthy baseline."""

    return {
        "message": "Synthetic service reset",
        **state.reset(),
    }
