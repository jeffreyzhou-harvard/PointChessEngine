#!/usr/bin/env bash
set -euo pipefail

TASKS="${TASKS:-all}"
TIER="${TIER:-smoke}"
JOBS="${JOBS:-4}"
IMAGE="${CHAMPION_IMAGE:-pointchess/champion:local}"
SKIP_DOCKER_BUILD="${SKIP_DOCKER_BUILD:-1}"
RUN_ORCHESTRATION="${RUN_ORCHESTRATION:-0}"
ORCHESTRATION_MODE="${ORCHESTRATION_MODE:-audit}"
RUN_BUILDERS="${RUN_BUILDERS:-0}"
BUILDER_PROVIDER="${BUILDER_PROVIDER:-}"
COMMIT_BUILDS="${COMMIT_BUILDS:-0}"
CONTINUE_ON_FAILURE="${CONTINUE_ON_FAILURE:-1}"
LOCAL_REPO_DEMO="${LOCAL_REPO_DEMO:-1}"
CONFIG_ROOT="${CONFIG_ROOT:-infra/configs/champion}"
DEMO_CONFIG_ROOT="${DEMO_CONFIG_ROOT:-reports/comparisons/CHAMPION_LADDER/demo_configs}"

cd "$(dirname "$0")/../.."

mkdir -p ../worktrees

if [ "$SKIP_DOCKER_BUILD" != "1" ]; then
  docker build -f infra/docker/Dockerfile.champion -t "$IMAGE" .
fi

if [ "$LOCAL_REPO_DEMO" = "1" ]; then
  docker run --rm \
    -v "$PWD:/repo" \
    -w /repo \
    "$IMAGE" \
    python infra/scripts/prepare_ladder_demo_configs.py \
      --source-root "$CONFIG_ROOT" \
      --output-root "$DEMO_CONFIG_ROOT"
  CONFIG_ROOT="$DEMO_CONFIG_ROOT"
fi

args=(
  python infra/scripts/run_champion_ladder.py
  --tasks "$TASKS"
  --config-root "$CONFIG_ROOT"
  --tier "$TIER"
  --jobs "$JOBS"
  --allow-missing-worktrees
  --no-require-candidate-changes
)

if [ "$LOCAL_REPO_DEMO" != "1" ]; then
  args+=(--create-worktrees)
fi

if [ "$CONTINUE_ON_FAILURE" = "1" ]; then
  args+=(--continue-on-failure)
fi

if [ "$RUN_ORCHESTRATION" = "1" ]; then
  args+=(--run-orchestration --orchestration-mode "$ORCHESTRATION_MODE")
fi

if [ "$RUN_BUILDERS" = "1" ]; then
  args+=(--run-builders)
  if [ -n "$BUILDER_PROVIDER" ]; then
    args+=(--builder-provider "$BUILDER_PROVIDER")
  fi
  if [ "$COMMIT_BUILDS" = "1" ]; then
    args+=(--commit-builds)
  fi
fi

docker run --rm \
  -v "$PWD:/repo" \
  -v "$PWD/../worktrees:/worktrees" \
  -w /repo \
  "$IMAGE" \
  "${args[@]}"

echo
echo "Champion ladder HTML:"
echo "reports/comparisons/CHAMPION_LADDER/index.html"
