#!/usr/bin/env bash
set -euo pipefail

TASK="${TASK:-CURRENT_ENGINES}"
CONFIG="${CONFIG:-infra/configs/champion/CURRENT_ENGINES.yaml}"
TIER="${TIER:-smoke}"
JOBS="${JOBS:-8}"
IMAGE="${CHAMPION_IMAGE:-pointchess/champion:local}"
VIS_INTERVAL="${VIS_INTERVAL:-0.5}"
SKIP_DOCKER_BUILD="${SKIP_DOCKER_BUILD:-1}"
VIS_CONTAINER="pointchess_champion_watch_$$"

cd "$(dirname "$0")/../.."

if [ "$SKIP_DOCKER_BUILD" != "1" ]; then
  docker build -f infra/docker/Dockerfile.champion -t "$IMAGE" .
fi

visualizer_pid=""

cleanup() {
  if [ -n "$visualizer_pid" ]; then
    docker stop "$VIS_CONTAINER" >/dev/null 2>&1 || true
    wait "$visualizer_pid" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

docker run --rm \
  --name "$VIS_CONTAINER" \
  -v "$PWD:/repo" \
  -w /repo \
  "$IMAGE" \
  python infra/scripts/watch_champion.py \
    --config "$CONFIG" \
    --task "$TASK" \
    --jobs "$JOBS" \
    --tests-only \
    --interval "$VIS_INTERVAL" &
visualizer_pid="$!"

sleep 1

set +e
docker run --rm \
  -v "$PWD:/repo" \
  -w /repo \
  "$IMAGE" \
  python infra/scripts/run_local_champion.py \
    --task "$TASK" \
    --config "$CONFIG" \
    --tier "$TIER" \
    --jobs "$JOBS" \
    --skip-create-worktrees
status="$?"
set -e

sleep 1
cleanup
trap - EXIT INT TERM

echo
echo "Final Champion visualization snapshot:"
docker run --rm \
  -v "$PWD:/repo" \
  -w /repo \
  "$IMAGE" \
  python infra/scripts/watch_champion.py \
    --config "$CONFIG" \
    --task "$TASK" \
    --jobs "$JOBS" \
    --tests-only \
    --once \
    --no-clear

exit "$status"
