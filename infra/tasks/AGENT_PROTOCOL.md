# Agent Protocol

Every implementation agent must follow this workflow:

1. Read `/tasks/START_HERE.md`.
2. Read assigned task file.
3. Read `/tasks/ORCHESTRATION.md`.
4. Read `/tasks/UNIT_TESTS.md`.
5. Read dependency task files.
6. Inspect the current repo before editing.
7. Complete the assigned task's `Work Packages` in order.
8. Implement only the assigned task.
9. Add or update tests for the current work package.
10. Run the work package's pre-commit unit tests.
11. Run dependency regression checks listed by the task.
12. Commit the completed work package before starting the next work package.
13. Run the full task-level tests/evals before opening PR.
14. Self-review using `/tasks/evals/E4_CODE_REVIEW_RUBRIC.md`.
15. Write `/reports/tasks/<TASK_ID>.md`.
16. Open or prepare a task-specific PR.

Branch naming:

```text
agent/<task-id>-<short-name>
```

Commit message format:

```text
<TASK_ID>: <short description>
```

Work package commit message format:

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
- ...

Known limitations:
- ...

AI workflow:
- model/framework used
- number of major prompts
- approximate cost/time if available
```

Work package commits are mandatory for classical `C*.*` work packages. Do not squash them before review unless explicitly directed by a human. The commit sequence is part of the benchmark evidence.

Before every work package commit:

- run the targeted unit tests listed in `Pre-Commit Tests by Work Package`
- run the exact command listed in `/tasks/UNIT_TESTS.md` when one exists
- run the listed dependency regressions
- run the fast project-wide test suite if available
- record exact commands and outcomes in the commit body

If the required tests do not exist yet, create them as part of the work package. For engine implementation tasks, missing tests are a blocker.

PR title format:

```text
[<TASK_ID>] <task title>
```

PR branch format:

```text
agent/<task-id>-<short-name>
```

Every PR must include:

- task ID
- PR title using `[<TASK_ID>]`
- branch name
- work packages completed
- commits by work package
- summary of changes
- tests run
- benchmark/eval results
- code review notes
- known limitations
- AI workflow used
- cost/time if available
- next recommended task
- any interface notes or compatibility risks

Recommended PR labels:

- `task:<TASK_ID>`
- `area:classical`, `area:neural`, or `area:eval`
- `needs-review`
- `benchmark-artifact`
- `uci`, `perft`, or `tournament` when relevant

Do not:

- implement unrelated future tasks
- silently change public interfaces
- remove tests to make the build pass
- hardcode benchmark answers
- use Stockfish as the engine unless a task explicitly permits reference/calibration
- bypass legal move generation
- claim exact Elo without calibration

Every task report must contain:

```markdown
# <TASK_ID> Report

## Objective

## Implementation Summary

## Work Packages Completed

## Commits

## Tests Added

## Tests Run

## Eval Results

## Code Review Findings

## AI Usage

## Cost / Time

## Observability Artifacts

## Interface Notes

## Known Limitations

## Next Recommended Task
```

For orchestrated runs, also update:

- `reports/runs/<RUN_ID>/manifest.md`
- `reports/runs/<RUN_ID>/task_status.md`
- `reports/runs/<RUN_ID>/ai_usage.md`
- `reports/runs/<RUN_ID>/eval_index.md`
