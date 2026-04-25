# E4 - Code Review Rubric

## Objective

Define the required review rubric for every task PR before merge.

## Why This Matters

The benchmark evaluates engineering process as much as final engine strength. A common review rubric makes quality, rigor, and AI oversight comparable across workflows.

## Deliverables

- Shared 40-point review rubric.
- Required review summary template.
- Decision thresholds.
- Guidance for reviewing AI-generated code.

## Work Packages

- E4.1 - Define scoring categories and thresholds.
- E4.2 - Define required review summary template.
- E4.3 - Define how reviewers should evaluate AI-generated code and benchmark integrity.
- E4.4 - Define how review scores roll up into final reports.

## Harness and Observability

- Every task report must link or paste its review summary.
- Run-level status tables should include review score and decision.
- Final report should summarize review scores by task and workflow.

## Handoff / Next Task

Next task: all implementation tasks.

Handoff requirements:

- Every PR has a consistent review score.
- Final report can compare engineering quality across agents/workflows.

Every task PR must be reviewed before merge.

Score each category 0-5:

1. Satisfies task objective
2. Tests are meaningful
3. Preserves legal chess behavior
4. Code is modular and readable
5. Handles edge cases
6. Avoids hardcoded benchmark cheating
7. AI-generated code was critically evaluated
8. Documentation/logs updated

Total: 40.

Decision:

- 36-40: accept
- 28-35: accept with minor fixes
- 20-27: revise
- below 20: reject

Required review summary:

```markdown
# Code Review Summary

Task:
Branch:
Reviewer:
AI workflow:
Score:

## Main strengths

## Main issues

## Required fixes

## Tests verified

## Risk level

## Decision
```

## Required Tests/Evals

- Rubric is referenced by `tasks/AGENT_PROTOCOL.md`.
- Review template can be copied into PRs or task reports.
- Scoring thresholds are unambiguous.
- Categories cover correctness, tests, documentation, and AI oversight.

## Required Code Review Checklist

- Is the rubric clear enough for different reviewers to apply consistently?
- Does it prioritize legal chess behavior and meaningful tests?
- Does it explicitly reject hardcoded benchmark cheating?
- Does it require critical review of AI-generated code?
- Are decisions tied to concrete score ranges?

## Git/PR Protocol

- Branch: `agent/E4-code-review-rubric`
- Report: `/reports/tasks/E4_CODE_REVIEW_RUBRIC.md`
- Commit prefix: `E4:`

## Acceptance Criteria

- Every task PR can be scored out of 40.
- Review summaries use the required template.
- Merge decisions are tied to documented thresholds.

## Failure Conditions

- Rubric is too vague to apply.
- AI usage is not reviewed.
- There is no decision threshold for merge readiness.

## Suggested Owner Role

Reviewer / Engineering Lead.

## Dependencies

None.

## Priority Level

P0.
