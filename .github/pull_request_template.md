# Task PR

## Task

Task ID:

Task file:

Branch:

## Work Packages

- [ ] `<WORK_PACKAGE_ID>` -
- [ ] `<WORK_PACKAGE_ID>` -

## Summary

What changed:

## Commits

List one commit per work package:

- `<WORK_PACKAGE_ID>: <short description>` - `<commit hash>`

## Tests Run

Targeted unit tests:

```text

```

Dependency regressions:

```text

```

Full task/eval checks:

```text

```

## Eval Artifacts

Reports/logs generated:

- 

## Code Review

Self-review completed with `infra/tasks/evals/E4_CODE_REVIEW_RUBRIC.md`:

- Score:
- Decision:
- Main risks:

## AI Workflow

- Agent framework/model:
- Major prompts or agent steps:
- Estimated cost:
- Wall-clock time:

## Known Limitations

- 

## Interface Notes

Public interfaces changed:

- [ ] No
- [ ] Yes, described below

Details:

## Next Task

Recommended next task:

## Checklist

- [ ] PR title uses `[<TASK_ID>] <task title>`.
- [ ] One commit exists per completed work package.
- [ ] Each work package commit records tests run.
- [ ] Required pre-commit unit tests passed for each `C*.*` work package.
- [ ] Dependency regression tests passed or skipped with reason.
- [ ] Task report exists at `reports/tasks/<TASK_ID>.md`.
- [ ] Run observability artifacts were updated if part of an orchestrated run.
- [ ] No unrelated future task scope was implemented.
- [ ] No tests were removed to make the build pass.
- [ ] No benchmark answers were hardcoded.
