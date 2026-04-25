# Agent Orchestration Plan

This document defines how an agent runner should execute the benchmark task suite without needing ad hoc instructions.

## Objective

Enable a human or agent orchestrator to say "tackle the tasks" and get a complete, observable run: implementation branches, task reports, eval artifacts, review records, tournament logs, and a final project showcase.

## Execution Model

Use one top-level task file as the unit of assignment. Inside each task, complete the `Work Packages` in order unless the file marks them as parallelizable.

For each task:

1. Read `tasks/START_HERE.md`.
2. Read `tasks/AGENT_PROTOCOL.md`.
3. Read this orchestration plan.
4. Read `tasks/UNIT_TESTS.md`.
5. Read the assigned task file.
6. Read every dependency task file.
7. Inspect the repo and current reports.
8. Create or update a task branch.
9. Complete work packages one by one.
10. Run the work package's pre-commit unit tests.
11. Run dependency regression checks.
12. Commit the work package.
13. Update task report and run observability artifacts.
14. Repeat until all work packages are complete.
15. Run full task-level checks.
16. Open PR or prepare merge summary.
17. Point explicitly to the next task.

## Agent Framework Contract

Agent frameworks may plan and execute however they want as long as they preserve the external evidence trail.

Allowed:

- subagents
- parallel research
- self-review loops
- generated tests
- generated eval scripts
- framework-specific memory or planning tools

Required:

- obey task dependencies
- do not implement future scope
- run tests before each work-package commit
- commit after each work package
- record cost/time/prompt or major-step usage when available
- produce recognizable PRs and reports

## Task States

Each task report must declare one state:

- `blocked`: Cannot start because dependencies or tools are missing.
- `in_progress`: Work has started but no PR is ready.
- `review_ready`: Implementation and tests are complete; review is needed.
- `accepted`: Review passed and task can be merged.
- `superseded`: Replaced by a later task or different approach.

## Dependency Policy

Agents may start a task only when all hard dependencies are `accepted`.

Agents may inspect future tasks to avoid incompatible choices, but they must not implement future scope. If a future-facing interface decision is needed, document it in the task report under `Interface Notes`.

## Branch Policy

Use one branch per top-level task unless the orchestrator intentionally splits a task across agents.

Default branch:

```text
agent/<task-id>-<short-name>
```

If splitting a task into concurrent work packages, use:

```text
agent/<task-id>.<work-package-id>-<short-name>
```

Example:

```text
agent/C2.3-sliding-pieces
```

## Work Package Commit Gate

Every `C*.*` work package must pass its local gate before commit:

- targeted unit tests for that work package
- regression tests from dependencies that could be affected
- fast project-wide tests if available
- updated task report or run status entry

If a work package is documentation-only, the commit body must explicitly say so and name the validation performed.

If a work package cannot pass because a dependency is missing, mark the task report `blocked` and do not continue into later implementation work.

## Required Artifacts

Each task must produce:

- Task report: `reports/tasks/<TASK_ID>.md`
- One commit per work package.
- Test/eval output summary in the report.
- Any generated logs referenced from the report.
- Code review summary using `tasks/evals/E4_CODE_REVIEW_RUBRIC.md`.
- Next-task recommendation.

Full orchestration runs should also produce:

- Run manifest: `reports/runs/<RUN_ID>/manifest.md`
- Task status table: `reports/runs/<RUN_ID>/task_status.md`
- Cost/time table: `reports/runs/<RUN_ID>/ai_usage.md`
- Eval index: `reports/runs/<RUN_ID>/eval_index.md`
- Final showcase: `reports/runs/<RUN_ID>/showcase.md`

## Observability Schema

Every task report must include these run-observability fields:

- Task ID
- Branch
- Work package IDs completed
- Commit hash per work package
- Commit hash or PR link
- Agent/model used
- Prompt count
- Wall-clock time
- Estimated cost if available
- Tests run
- Tests skipped and why
- Eval artifacts generated
- Known risks
- Next task

## GitHub PR Recognition

PRs should be easy to identify in GitHub without opening the diff.

Required PR title:

```text
[<TASK_ID>] <task title>
```

Required PR description sections:

```markdown
## Task

## Work Packages

## Summary

## Tests Run

## Eval Artifacts

## Commits

## Code Review

## AI Workflow

## Cost / Time

## Known Limitations

## Next Task
```

Recommended labels:

- `task:<TASK_ID>`
- `area:classical`, `area:neural`, or `area:eval`
- `benchmark-artifact`
- `needs-review`
- `uci`, `perft`, or `tournament` when relevant

Every eval artifact should record:

- Engine command
- Git commit
- Task state
- Date/time
- Hardware or runner notes when relevant
- Time control or limits
- Pass/fail result
- Crash/timeout/illegal-move counts when relevant

## Orchestration Order

Recommended default path:

1. C0_ENGINE_INTERFACE
2. E1_PERFT_SUITE
3. E2_UCI_COMPLIANCE
4. E3_TOURNAMENT_RUNNER
5. E4_CODE_REVIEW_RUBRIC
6. C1_BOARD_FEN_MOVE
7. C2_LEGAL_MOVE_GENERATION
8. C3_STATIC_EVALUATION
9. C4_ALPHA_BETA_SEARCH
10. C7_UCI_COMPATIBILITY
11. C5_TACTICAL_HARDENING
12. C6_TIME_TT_ITERATIVE
13. C8_ELO_SLIDER
14. N1_DATASET_LABELING
15. N2_ENCODER_LEGAL_MASK
16. N4_NEURAL_POLICY_ORDERING
17. N5_HYBRID_ENGINE
18. N3_NEURAL_VALUE_EVAL
19. N6_NEURAL_STRENGTH_CALIBRATION
20. E5_FINAL_REPORT_TEMPLATE

Parallelizable after C0 and eval scaffolding:

- C1 can proceed while E1/E2/E3 are refined if interfaces are stable.
- C3 evaluation design can be drafted after C2 interfaces are clear, but implementation waits for legal move generation.
- N1 data schema can be drafted after C1, but legal-label validation waits for C2.

## Final Showcase Gate

The final showcase is complete only when it includes:

- Engine command and UCI startup transcript.
- Perft legality summary.
- UCI compliance summary.
- Tournament standings.
- Stockfish calibration caveat and results.
- Code review score table.
- AI usage and cost/time table.
- Known limitations.
- Reproducibility instructions.

## Stop Conditions

The orchestrator must stop and request human review if:

- A task requires changing an accepted public interface.
- Legal move generation regresses after any later task.
- UCI compliance regresses after C7.
- A benchmark result appears to be hardcoded or non-reproducible.
- An agent claims exact Elo without calibration evidence.
