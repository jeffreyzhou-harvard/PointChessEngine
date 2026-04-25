# Champion Promotion Protocol

Promotion means selecting one candidate implementation and merging or cherry-picking it into the canonical baseline branch.

The promoted implementation becomes the canonical baseline. It does not become ground truth. Ground truth remains the task specs and tests/evals.

## Promotion Requirements

A candidate can only be promoted if:

- candidate branch exists
- candidate report exists
- tests were run
- contract tests pass
- milestone tests pass
- previous milestone regression tests pass
- no public interface changes unless approved
- code review score exists
- benchmark results exist if applicable
- AI usage/cost logged
- comparison report generated

## Promotion Rules

- Never auto-promote unless `--promote` and `--confirm` are passed.
- Never delete loser branches.
- Promotion should prefer merge/cherry-pick with a clear commit message.
- If the winner is a synthesis of multiple candidates, create a new integration branch.
- Canonical `main` must always pass all tests up to the current milestone.

## Merge Strategy

Recommended default:

```text
git checkout main
git merge --no-ff <winner-branch>
```

If a candidate contains useful isolated commits but not the whole branch:

```text
git checkout -b integration/<task>/<winner-or-synthesis> main
git cherry-pick <commit>
```

## Loser Branch Policy

Loser branches are archived by leaving them in place and linking them from the comparison report. Do not delete them automatically. They are part of the workflow benchmark evidence.

## Synthesis Winner Policy

If the best result combines pieces from multiple candidates:

1. Create `integration/<task>/<short-name>`.
2. Cherry-pick or manually integrate selected changes.
3. Run the same tests/evals as candidate branches.
4. Write an integration candidate report.
5. Score the integration branch as its own candidate.
6. Promote only after passing all gates.
