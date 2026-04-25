# Parallelization Plan

This document defines how Champion mode uses parallel work without losing integration discipline. The existing `/tasks` suite remains the source of milestone scope. This file describes how agents and candidates can execute those tasks in parallel.

## Champion Mode Tracks

Champion mode has two separate tracks.

Champion engine track:

- Multiple orchestration frameworks produce candidate implementations for the same milestone.
- Each candidate starts from the same canonical baseline.
- Candidates are tested, reviewed, benchmarked, and scored.
- The best candidate is promoted into canonical `main`.

Workflow benchmark track:

- Each orchestration framework may also maintain a persistent branch across milestones.
- This allows fair end-to-end comparison of frameworks across the full project.
- Workflow branches are not automatically canonical. They are experimental records.

Do not call the winner "ground truth." The winner becomes the canonical baseline. Ground truth remains the task specs and test/eval suites.

## Recommended Execution Environment

Start local-first:

- one canonical checkout
- one git worktree per candidate
- one agent/framework per worktree
- Champion scripts run from the canonical checkout

Move to an Ubuntu VM later only when you need a cleaner machine, isolated hardware, or long tournament runs.

## Terminology

- Task spec: an `/infra/tasks/*.md` file defining a milestone.
- Ground truth tests: unit tests, contract tests, perft tests, UCI tests, tournament evals.
- Canonical baseline: current best merged engine state.
- Candidate implementation: one framework/model setup's attempt at a milestone.
- Promoted implementation: candidate selected and merged into canonical.
- Workflow branch: persistent branch for one orchestration framework across milestones.

## Five Layers of Parallelization

### 1. Workstream Parallelization

Workstreams:

- rules
- search
- UCI/tournament
- neural
- review/integration
- reports

Workstreams may run in parallel only when dependencies and public interfaces are stable. Workstream agents may inspect future tasks, but they must not implement future scope.

### 2. AI-Agent Task Parallelization

Codex, Claude, Replit Agent, Cursor agents, and custom runners may work on separate branches or worktrees. Each agent must follow the assigned task file, write reports, run tests, and preserve a reviewable git history.

### 3. Candidate-Solution Parallelization

Multiple frameworks solve the same milestone from the same canonical baseline. Candidate branches use:

```text
experiments/<task>/<candidate>
```

Examples:

```text
experiments/C3/react_claude
experiments/C3/debate_heterogeneous_claude_gpt_gemini
experiments/C4/codex_agent
```

### 4. Evaluation/Tournament Parallelization

Evaluation can run independently across candidates:

- unit tests
- perft tests
- UCI checks
- FastChess matches when available
- Stockfish calibration when available

Evaluation parallelism must not hide failures. Every candidate must have its own report directory and raw logs.

### 5. Neural/Data Parallelization

Neural and data work can split into:

- dataset generation
- encoding
- model training
- policy evals
- value evals

Neural candidates must still pass legality and interface gates before promotion.

## Rules

- No agent may edit unrelated modules.
- No agent may change public interfaces without approval.
- Every candidate works on a branch named `experiments/<task>/<candidate>`.
- Every candidate starts from the frozen canonical baseline commit for that milestone.
- Every candidate must include tests or clearly state why tests are not possible.
- Every candidate must produce a task/candidate report.
- Every candidate must be code-reviewed before promotion.
- Loser branches are archived, not deleted.
- The canonical branch must always pass all tests up to the current milestone.

## Supported Orchestration Patterns

- `one_shot_no_context`
- `one_shot_with_context`
- `react`
- `chain_of_thought_decomposition`
- `gstack`
- `cursor_agents`
- `codex_agent`
- `replit_agent`
- `debate_ensemble`
- `debate_non_ensemble`
- `rlm`
- `custom_langchain_parallel`
- `custom_openai_agents_sdk`

Orchestration pattern is not the same as model provider or execution environment.

Candidate ID format:

```text
<task_id>_<orchestration>_<model_setup>
```

Examples:

- `C3_react_claude`
- `C3_debate_heterogeneous_claude_gpt_gemini`
- `C4_codex_agent`
- `C8_replit_agent`
