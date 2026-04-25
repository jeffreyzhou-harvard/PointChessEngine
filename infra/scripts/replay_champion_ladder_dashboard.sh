#!/usr/bin/env bash
set -euo pipefail

STEP_SECONDS="${STEP_SECONDS:-1.25}"
HOLD_SECONDS="${HOLD_SECONDS:-2.5}"
REFRESH_SECONDS="${REFRESH_SECONDS:-1}"

cd "$(dirname "$0")/../.."

python infra/scripts/replay_champion_ladder_dashboard.py \
  --loop \
  --open \
  --step-seconds "$STEP_SECONDS" \
  --hold-seconds "$HOLD_SECONDS" \
  --refresh-seconds "$REFRESH_SECONDS"
