#!/usr/bin/env bash
# One-click demo: simulated key-leak scenario, end to end.
# Touches no real service (SIMULATION_MODE=1). Pipe-friendly for recording.
set -euo pipefail
cd "$(dirname "$0")/.."

export SIMULATION_MODE=1
export DB_PATH="${DB_PATH:-/tmp/relaypilot-demo.db}"
export DETECTOR_FORCE_HEURISTIC="${DETECTOR_FORCE_HEURISTIC:-1}"
rm -f "$DB_PATH"

echo "RelayPilot demo — simulated key leak (SIMULATION_MODE=1, DB=$DB_PATH)"
echo
PYTHONPATH="$(cd .. && pwd):${PYTHONPATH:-}" python3 -m relaypilot.sim.scenario
