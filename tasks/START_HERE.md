# Start Here for Autonomous Agents

This is the entrypoint for any AI agent framework working on the chess engine benchmark.

The human should not need to micromanage implementation. The agent framework may use its own planning style, memory, subagents, tools, or review loop, but it must satisfy this project contract.

## Mission

Build and evaluate a chess engine as a controlled benchmark for AI-assisted software engineering workflows.

The final engine matters, but the measured artifact is bigger:

- task decomposition
- implementation quality
- tests and evals
- review discipline
- observability
- cost/time tracking
- final tournament and calibration evidence

## Required Reading Order

Before editing code, read:

1. `tasks/START_HERE.md`
2. `tasks/AGENT_PROTOCOL.md`
3. `tasks/ORCHESTRATION.md`
4. `tasks/PRIORITY_PLAN.md`
5. `tasks/UNIT_TESTS.md`
6. The assigned task file
7. All dependency task files
8. Current reports under `reports/tasks/` and `reports/runs/` if they exist

## Framework Freedom

Agent frameworks may choose their own methodology:

- single-agent execution
- planner/worker split
- parallel subagents
- critique/revision loops
- tool-augmented coding
- test-first development
- implementation-first with immediate tests

The framework must still obey the task boundaries, commit cadence, test gates, and reporting requirements in this repo.

## Unit of Work

The top-level task file is the PR unit by default.

The `Work Packages` inside a task are the commit units. For classical tasks, these are IDs such as `C2.1`, `C2.2`, and `C2.3`.

Each work package must end with:

1. implementation or documentation updates for that work package
2. targeted unit tests for that work package
3. relevant regression tests from prior accepted work
4. a commit whose message starts with the work package ID
5. an update to the task report or run status if this is an orchestrated run

Do not move to the next work package until the current package has a passing test gate or a documented blocker.

## Commit Rule

Every work package must have its own commit.

Commit message format:

```text
<WORK_PACKAGE_ID>: <short description>
```

Examples:

```text
C1.2: implement FEN parser validation
C2.5: filter legal moves by king safety
C7.6: emit UCI info and bestmove diagnostics
```

Commit body:

```text
Implemented:
- ...

Tests:
- targeted unit tests run:
- regression tests run:

Observability:
- logs/reports updated:

AI workflow:
- framework/model:
- prompts or agent steps:
- estimated cost/time:

Known limitations:
- ...
```

Do not squash work-package commits before review unless the human explicitly asks for it. The commit history is part of the benchmark evidence.

## Pre-Commit Test Gate

Before each work-package commit, run:

1. the targeted unit tests listed in `tasks/UNIT_TESTS.md`
2. the targeted unit tests listed in the task's `Pre-Commit Tests by Work Package`
3. any dependency regression tests named by the task
4. any existing project-wide fast test suite if it is available

If a test runner does not exist yet, the work package must either add one or document why the current package is docs-only. For engine implementation tasks, missing tests are a blocker, not a pass.

Record the exact commands and outcomes in the commit body and task report.

## Branch and PR Shape

Default branch:

```text
agent/<task-id>-<short-name>
```

Split work-package branch, when needed:

```text
agent/<task-id>.<work-package-id>-<short-name>
```

PR title format:

```text
[<TASK_ID>] <human-readable task title>
```

Examples:

```text
[C2] Legal move generation and rule correctness
[C7] Production UCI compatibility
```

PR description must include:

- Task ID
- Work packages completed
- Commits by work package
- Summary of behavior
- Tests run
- Eval artifacts and links
- Code review score or checklist
- Known limitations
- AI framework/model used
- Prompt count or major agent steps
- Cost/time if available
- Next recommended task

Use labels when available:

- `task:<TASK_ID>`
- `area:classical`, `area:neural`, or `area:eval`
- `needs-review`
- `benchmark-artifact`
- `uci`, `perft`, or `tournament` when relevant

## Human Escalation

Stop and ask for human review only when:

- task dependencies are contradictory
- passing the task requires changing an accepted public contract
- legal chess behavior regresses
- UCI compatibility regresses after C7
- tests reveal ambiguous chess-rule behavior not covered by the tasks
- benchmark results look non-reproducible or suspicious

Otherwise, continue through the next work package and leave a clear audit trail.

## Final Output

An orchestrated run is done when it can show:

- final engine command
- UCI compliance result
- legality/perft result
- tournament standings
- Stockfish calibration caveat and result
- code review summary
- AI usage/cost table
- task reports
- reproducibility instructions
