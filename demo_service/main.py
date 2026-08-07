"""Synthetic airline-style booking service for controlled incident scenarios.

The service intentionally supports safe failure injection. It uses only synthetic
records and must never be connected to customer or production data.
"""

from __future__ import annotations

import asyncio
from enum import Enum
from threading import RLock
from time import perf_counter

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from demo_service.telemetry import configure_telemetry, get_application_logger


DEFAULT_SYNTHETIC_SLO_MS = 500
SYNTHETIC_DEPENDENCY = "synthetic-inventory-service"


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
    version="0.4.0",
)

telemetry_config = configure_telemetry(app)
logger = get_application_logger()


def _liveness_payload() -> dict[str, str | bool]:
    """Return public liveness information without exposing demo controls."""

    return {
        "status": "alive",
        "check_type": "liveness",
        "synthetic": True,
    }


async def _build_booking(
    booking_id: str,
    snapshot: dict[str, str | int | bool],
) -> dict[str, str | bool]:
    """Build one synthetic booking while applying the selected failure mode."""

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
        "service_mode": str(snapshot["mode"]),
    }


@app.get("/")
def service_info() -> dict:
    """Return service identity and current reversible demo state."""

    return {
        "name": "OpsPilot Synthetic Booking Service",
        "purpose": "Controlled telemetry and remediation demonstration",
        **state.snapshot(),
    }


@app.get("/health/live")
def liveness_check() -> dict:
    """Report whether the application process is running."""

    return _liveness_payload()


@app.get("/health/ready", response_model=None)
def readiness_check():
    """Report whether the service can currently accept booking traffic."""

    snapshot = state.snapshot()
    if snapshot["mode"] == FailureMode.DEPENDENCY_FAILURE.value:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "check_type": "readiness",
                "dependency": SYNTHETIC_DEPENDENCY,
                "synthetic": True,
            },
        )

    return {
        "status": "ready",
        "check_type": "readiness",
        "synthetic": True,
    }


@app.get("/synthetic/booking-check", response_model=None)
async def synthetic_booking_check(
    slo_ms: int = Query(
        default=DEFAULT_SYNTHETIC_SLO_MS,
        ge=1,
        le=10_000,
        description="Maximum acceptable booking journey duration in milliseconds.",
    ),
):
    """Execute and evaluate an outside-in synthetic booking journey."""

    snapshot = state.snapshot()

    if snapshot["mode"] == FailureMode.DEPENDENCY_FAILURE.value:
        logger.error(
            "Synthetic booking check failed because dependency is unavailable",
            extra={
                "opspilot.event": "synthetic_booking_check",
                "opspilot.status": "failed",
                "opspilot.reason": "dependency_unavailable",
                "opspilot.dependency": SYNTHETIC_DEPENDENCY,
                "opspilot.slo_ms": slo_ms,
                "opspilot.synthetic": True,
            },
        )
        return JSONResponse(
            status_code=503,
            content={
                "status": "failed",
                "check_type": "synthetic",
                "journey": "booking",
                "reason": "dependency_unavailable",
                "dependency": SYNTHETIC_DEPENDENCY,
                "slo_ms": slo_ms,
                "synthetic": True,
            },
        )

    started = perf_counter()
    await _build_booking("SYNTHETIC-CHECK", snapshot)
    response_time_ms = round((perf_counter() - started) * 1000, 2)

    result = {
        "check_type": "synthetic",
        "journey": "booking",
        "response_time_ms": response_time_ms,
        "slo_ms": slo_ms,
        "synthetic": True,
    }

    if response_time_ms > slo_ms:
        logger.warning(
            "Synthetic booking check breached the configured SLO",
            extra={
                "opspilot.event": "synthetic_booking_check",
                "opspilot.status": "degraded",
                "opspilot.reason": "slo_violation",
                "opspilot.response_time_ms": response_time_ms,
                "opspilot.slo_ms": slo_ms,
                "opspilot.synthetic": True,
            },
        )
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "reason": "slo_violation",
                **result,
            },
        )

    logger.info(
        "Synthetic booking check completed within SLO",
        extra={
            "opspilot.event": "synthetic_booking_check",
            "opspilot.status": "healthy",
            "opspilot.response_time_ms": response_time_ms,
            "opspilot.slo_ms": slo_ms,
            "opspilot.synthetic": True,
        },
    )
    return {
        "status": "healthy",
        **result,
    }


@app.get("/bookings/{booking_id}")
async def read_booking(
    booking_id: str = Path(min_length=4, max_length=40, pattern=r"^[A-Za-z0-9-]+$")
) -> dict:
    """Return a synthetic booking while applying the selected failure mode."""

    return await _build_booking(booking_id, state.snapshot())


@app.get("/admin/state")
def read_failure_state() -> dict:
    """Expose the current demo state for scripts and test automation."""

    return state.snapshot()


@app.get("/admin/telemetry")
def read_telemetry_config() -> dict[str, str | bool]:
    """Expose non-secret telemetry configuration for local demo diagnostics."""

    return {
        "enabled": telemetry_config.enabled,
        "service_name": telemetry_config.service_name,
        "environment": telemetry_config.environment,
        "otlp_endpoint": telemetry_config.otlp_endpoint,
    }


@app.post("/admin/failure-mode")
def set_failure_mode(request: FailureModeRequest) -> dict:
    """Enable one safe and reversible failure scenario."""

    snapshot = state.configure(request.mode, request.latency_ms)
    logger.info(
        "Synthetic failure mode updated",
        extra={
            "opspilot.event": "failure_mode_updated",
            "opspilot.failure_mode": request.mode.value,
            "opspilot.latency_ms": request.latency_ms,
            "opspilot.synthetic": True,
        },
    )
    return {
        "message": "Synthetic failure mode updated",
        **snapshot,
    }


@app.post("/admin/reset")
def reset_failure_mode() -> dict:
    """Return the service to its healthy baseline."""

    snapshot = state.reset()
    logger.info(
        "Synthetic service reset to healthy baseline",
        extra={
            "opspilot.event": "failure_mode_reset",
            "opspilot.failure_mode": FailureMode.HEALTHY.value,
            "opspilot.synthetic": True,
        },
    )
    return {
        "message": "Synthetic service reset",
        **snapshot,
    }
