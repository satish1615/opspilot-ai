#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"

section() {
  printf '\n===== %s =====\n' "$1"
}

section "HEALTHY"
curl -fsS -X POST "$BASE_URL/admin/reset"
printf '\n'
curl -fsS "$BASE_URL/synthetic/booking-check"
printf '\n'

section "HIGH LATENCY"
curl -fsS -X POST \
  "$BASE_URL/admin/failure-mode" \
  -H "Content-Type: application/json" \
  -d '{"mode":"high_latency","latency_ms":1500}'
printf '\n'
# The synthetic check intentionally returns HTTP 503 when the 500 ms SLO is breached.
curl -sS "$BASE_URL/synthetic/booking-check"
printf '\n'

section "DEPENDENCY FAILURE"
curl -fsS -X POST \
  "$BASE_URL/admin/failure-mode" \
  -H "Content-Type: application/json" \
  -d '{"mode":"dependency_failure","latency_ms":1}'
printf '\n'
# The synthetic check intentionally returns HTTP 503 for the simulated dependency outage.
curl -sS "$BASE_URL/synthetic/booking-check"
printf '\n'

section "RESET"
curl -fsS -X POST "$BASE_URL/admin/reset"
printf '\n'

printf '\nDemo scenarios sent. Allow a few seconds for batched telemetry export.\n'
