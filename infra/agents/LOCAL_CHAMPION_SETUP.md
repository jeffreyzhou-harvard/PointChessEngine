# Local Champion Setup

Champion mode can run entirely on one local machine. A VM is optional infrastructure for later reproducibility and long tournament runs.

## Local Architecture

```text
Local machine
   |
   |-- PointChessEngine canonical checkout
   |-- ../worktrees/<candidate> git worktrees
   |-- Codex / Claude / Cursor / Replit-generated branches
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
../worktrees/C3-codex-agent
../worktrees/C3-replit-agent
../worktrees/C3-custom-parallel
```

## Assign Agents

Point each agent at a different worktree:

- Codex: `../worktrees/C3-codex-agent`
- Claude or Cursor: `../worktrees/C3-react-claude`
- debate ensemble: `../worktrees/C3-debate-heterogeneous`
- Replit-generated branch: `../worktrees/C3-replit-agent`
- custom parallel runner: `../worktrees/C3-custom-parallel`

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
  --candidate-id C3_codex_agent \
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
  --jobs 6 \
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
    --jobs 6 \
    --skip-create-worktrees
```

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
