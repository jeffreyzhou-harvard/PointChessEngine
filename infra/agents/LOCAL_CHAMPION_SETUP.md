# Local Champion Setup

Champion mode can run entirely on one local machine. A VM is optional infrastructure for later reproducibility and long tournament runs.

## Local Architecture

```text
Local machine
   |
   |-- PointChessEngine canonical checkout
   |-- ../worktrees/<candidate> git worktrees
   |-- Claude-first / Cursor / Replit-generated branches
   |-- Champion scripts
   |-- tests, reports, scoring, promotion
```

Each agent or framework gets its own git worktree. Do not run multiple agents in the same working tree.

## Why Local First

Local-first Champion mode is the MVP because it avoids cloud setup while preserving the important benchmark properties:

- same canonical baseline
- separate candidate branches
- repeatable tests
- comparison reports
- explicit promotion gate
- archived loser branches

Move to a VM later when you need cleaner reproducibility, isolated hardware, or long tournament runs.

## One-Time Setup

From the canonical repo checkout:

```bash
cd PointChessEngine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p ../worktrees
```

## Create Candidate Worktrees

Use the config for the milestone:

```bash
python infra/scripts/create_candidate_worktrees.py \
  --config infra/configs/champion/C3_STATIC_EVALUATION.yaml.example
```

This creates worktrees such as:

```text
../worktrees/C3-react-claude
../worktrees/C3-debate-heterogeneous
../worktrees/C3-replit-agent
../worktrees/C3-custom-parallel
```

## Assign Agents

Point each agent at a different worktree:

- Claude Code / Claude CLI: `../worktrees/C3-react-claude`
- Claude-led debate ensemble: `../worktrees/C3-debate-heterogeneous`
- Replit-generated branch: `../worktrees/C3-replit-agent`
- custom parallel runner, usually Claude as builder with other models as critics: `../worktrees/C3-custom-parallel`

Codex is kept only as an optional adapter in the scripts. The default config examples are Claude-first. The recommended local builder is Claude CLI. The recommended Docker/GitHub setup is `POINTCHESS_DEFAULT_BUILDER_PROVIDER=anthropic`, which uses Anthropic for Claude-style candidates while preserving RLM candidates on the `rlms` path.

Each candidate branch should use:

```text
experiments/<task>/<candidate>
```

## Evaluate Locally

After candidate branches are ready:

```bash
python infra/scripts/run_champion_stage.py \
  --task C3_STATIC_EVALUATION \
  --config infra/configs/champion/C3_STATIC_EVALUATION.yaml.example \
  --run-tests \
  --score \
  --write-report
```

Or use the local convenience wrapper:

```bash
python infra/scripts/run_local_champion.py \
  --task C3_STATIC_EVALUATION \
  --config infra/configs/champion/C3_STATIC_EVALUATION.yaml.example
```

Reports are written under:

```text
reports/comparisons/<task_id>/
```

## Promote Locally

Promotion is never automatic. After reviewing the comparison report:

```bash
python infra/scripts/promote_candidate.py \
  --config infra/configs/champion/C3_STATIC_EVALUATION.yaml.example \
  --candidate-id C3_react_claude \
  --confirm
```

By default this prints the safe merge commands. Add `--execute` only after reviewing the commands.

## Local Safety Rules

- Never let two agents use the same worktree.
- Never edit canonical `main` directly during candidate generation.
- Never promote without passing tests and a comparison report.
- Never delete loser branches automatically.
- Keep cost/time and model assignment records for every candidate.

## Evaluate Current Engines in Parallel

To compare the engine artifacts already checked into the repo:

```bash
python infra/scripts/run_local_champion.py \
  --task CURRENT_ENGINES \
  --config infra/configs/champion/CURRENT_ENGINES.yaml \
  --jobs 7 \
  --skip-create-worktrees \
  --continue-on-failure
```

This runs the registered UCI engines concurrently and writes results under
`reports/comparisons/CURRENT_ENGINES/`.

## Dockerized Champion POC

Build the same image used by GitHub Actions:

```bash
docker build -f infra/docker/Dockerfile.champion -t pointchess/champion:local .
```

Run the current-engine Champion stage inside Docker:

```bash
docker run --rm \
  -v "$PWD:/repo" \
  -w /repo \
  pointchess/champion:local \
  python infra/scripts/run_local_champion.py \
    --task CURRENT_ENGINES \
    --config infra/configs/champion/CURRENT_ENGINES.yaml \
    --jobs 7 \
    --skip-create-worktrees
```

Run a stronger tier:

```bash
docker run --rm \
  -v "$PWD:/repo" \
  -w /repo \
  pointchess/champion:local \
  python infra/scripts/run_local_champion.py \
    --task CURRENT_ENGINES \
    --config infra/configs/champion/CURRENT_ENGINES.yaml \
    --tier contract \
    --jobs 7 \
    --skip-create-worktrees
```

Run the orchestration audit before evaluating the RLM candidate:

```bash
python infra/scripts/run_agent_orchestration.py \
  --config infra/configs/champion/CURRENT_ENGINES.yaml \
  --candidate CURRENT_rlm \
  --task C0_ENGINE_INTERFACE \
  --mode audit
```

Run a live Claude-backed candidate builder locally:

```bash
python infra/scripts/run_local_champion.py \
  --task C3_STATIC_EVALUATION \
  --config infra/configs/champion/C3_STATIC_EVALUATION.yaml.example \
  --candidate C3_react_claude \
  --run-builders \
  --builder-provider claude_cli \
  --commit-builds \
  --builder-timeout 1800
```

```bash
docker run --rm \
  -v "$PWD:/repo" \
  -w /repo \
  pointchess/champion:local \
  python infra/scripts/run_local_champion.py \
    --task CURRENT_ENGINES \
    --config infra/configs/champion/CURRENT_ENGINES.yaml \
    --candidate CURRENT_rlm \
    --tier smoke \
    --milestone-task C0_ENGINE_INTERFACE \
    --run-orchestration \
    --orchestration-mode audit \
    --skip-create-worktrees
```

Audit mode proves the Docker path is invoking the orchestration layer and
writing trace artifacts. Live mode is the actual model-backed agent run and
requires provider credentials.

Run the full C0-C8 classical ladder inside Docker:

```bash
docker run --rm \
  -v "$PWD:/repo" \
  -w /repo \
  pointchess/champion:local \
  python infra/scripts/run_classical_ladder.py --task all --jobs 3
```

For per-task candidate comparison, use the corresponding
`infra/configs/champion/C*_*.yaml.example` file, create candidate worktrees from
the frozen baseline, run the configured orchestrators, then run Champion. The
ladder validates the canonical checkout; the per-task configs choose winners.

When running C* candidate configs in Docker, mount a host worktree directory so
the container can see candidate branches:

```bash
mkdir -p ../worktrees
docker run --rm \
  -v "$PWD:/repo" \
  -v "$PWD/../worktrees:/worktrees" \
  -w /repo \
  pointchess/champion:local \
  python infra/scripts/run_champion_stage.py \
    --task C3_STATIC_EVALUATION \
    --config infra/configs/champion/C3_STATIC_EVALUATION.yaml.example \
    --create-worktrees \
    --run-orchestration \
    --orchestration-mode audit \
    --run-tests \
    --score \
    --write-report \
    --jobs 4
```

Champion reports include graph-ready data:

```text
reports/comparisons/<task>/metrics.csv
reports/comparisons/<task>/metrics.jsonl
reports/comparisons/<task>/metrics.json
reports/orchestration/<task>/metrics.csv
reports/orchestration/<task>/metrics.jsonl
reports/orchestration/<task>/metrics.json
```

Use these files for pass/fail plots, duration/speedup charts, score rankings,
and orchestration cost/latency comparisons.

## Full Candidate Ladder

To run the whole C0-C8 candidate ladder:

```bash
docker run --rm \
  -v "$PWD:/repo" \
  -v "$PWD/../worktrees:/worktrees" \
  -w /repo \
  pointchess/champion:local \
  python infra/scripts/run_champion_ladder.py \
    --tasks all \
    --run-orchestration \
    --orchestration-mode audit \
    --allow-missing-worktrees \
    --continue-on-failure \
    --jobs 4
```

Audit mode creates prompt/report traces for every methodology candidate and
runs live RLM audit where configured, but it does not produce implementation
patches. A task is promotable only when at least one real candidate worktree
exists, has changes beyond the frozen baseline, and passes that task's Champion
gate.

Run one engine smoke check:

```bash
docker run --rm \
  -v "$PWD:/repo" \
  -w /repo \
  pointchess/champion:local \
  python infra/scripts/uci_smoke.py --engine debate
```

The Docker path is intentionally the same command shape as GitHub Actions and
the optional self-hosted VM runner.
