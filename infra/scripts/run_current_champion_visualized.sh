#!/usr/bin/env bash
set -euo pipefail

CONFIG="${CONFIG:-infra/configs/champion/CURRENT_ENGINES.yaml}"
TIER="${TIER:-smoke}"
JOBS="${JOBS:-8}"
IMAGE="${CHAMPION_IMAGE:-pointchess/champion:local}"
VIS_INTERVAL="${VIS_INTERVAL:-0.5}"
SKIP_DOCKER_BUILD="${SKIP_DOCKER_BUILD:-1}"

cd "$(dirname "$0")/../.."

args=(
  python3 infra/scripts/run_local_docker_champion_visual.py
  --config "$CONFIG"
  --tier "$TIER"
  --jobs "$JOBS"
  --image "$IMAGE"
  --interval "$VIS_INTERVAL"
)

if [ "$SKIP_DOCKER_BUILD" != "1" ]; then
  args+=(--build-image)
fi

"${args[@]}"
