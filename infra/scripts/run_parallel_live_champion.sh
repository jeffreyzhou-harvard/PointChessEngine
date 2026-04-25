#!/usr/bin/env bash
set -euo pipefail

TASKS="${TASKS:-${1:-C0_ENGINE_INTERFACE}}"
TIER="${TIER:-smoke}"
JOBS="${JOBS:-4}"
BUILDER_TIMEOUT="${BUILDER_TIMEOUT:-1800}"
ORCHESTRATION_TIMEOUT="${ORCHESTRATION_TIMEOUT:-300}"
IMAGE="${CHAMPION_IMAGE:-pointchess/champion:local}"

cd "$(dirname "$0")/../.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${ANTHROPIC_KEY:-}" ]; then
  echo "Missing Anthropic credentials. Set ANTHROPIC_API_KEY or ANTHROPIC_KEY in your shell or .env." >&2
  exit 2
fi

if [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${OPEN_AI_KEY:-}" ]; then
  echo "Missing OpenAI credentials. Set OPENAI_API_KEY or OPEN_AI_KEY in your shell or .env for the RLM candidate." >&2
  exit 2
fi

mkdir -p ../worktrees

if [ "${SKIP_DOCKER_BUILD:-0}" != "1" ]; then
  docker build -f infra/docker/Dockerfile.champion -t "$IMAGE" .
fi

docker run --rm \
  -v "$PWD:/repo" \
  -v "$PWD/../worktrees:/worktrees" \
  -w /repo \
  -e POINTCHESS_DEFAULT_BUILDER_PROVIDER=anthropic \
  -e OPENAI_API_KEY \
  -e OPEN_AI_KEY \
  -e ANTHROPIC_API_KEY \
  -e ANTHROPIC_KEY \
  -e GEMINI_API_KEY \
  -e GEMINI_KEY \
  -e GOOGLE_API_KEY \
  -e XAI_API_KEY \
  -e GROK_KEY \
  -e MOONSHOT_API_KEY \
  -e KIMI_KEY \
  -e DEEPSEEK_API_KEY \
  -e DEEPSEEK_KEY \
  "$IMAGE" \
  python infra/scripts/run_champion_ladder.py \
    --tasks "$TASKS" \
    --tier "$TIER" \
    --create-worktrees \
    --run-orchestration \
    --orchestration-mode live \
    --orchestration-timeout "$ORCHESTRATION_TIMEOUT" \
    --run-builders \
    --builder-timeout "$BUILDER_TIMEOUT" \
    --commit-builds \
    --continue-on-failure \
    --jobs "$JOBS"
