# Champion Methodology Audit Prompt

Candidate: `C5_custom_parallel`

Task: `C5_TACTICAL_HARDENING`

Orchestration type: `custom_langchain_parallel`

## Task Spec

# C5 - Tactical Hardening

## Objective

Improve tactical strength through move ordering, quiescence search, and mate scoring.

## Why This Matters

Basic fixed-depth search often misses tactics due to horizon effects.

## Deliverables

- Capture prioritization.
- Check prioritization.
- Move ordering.
- Quiescence search.
- Mate-distance scoring.
- Optional killer/history heuristic.

## Work Packages

- C5.1 - Add baseline tactical suite and record C4 results before changing search.
- C5.2 - Implement move ordering for captures, checks, promotions, and previous principal variation when available.
- C5.3 - Implement quiescence search for noisy leaf positions with clear bounds.
- C5.4 - Implement mate-distance scoring so faster mates are preferred.
- C5.5 - Optionally add killer and history heuristics if they are measurable and well-contained.
- C5.6 - Compare C5 against C4 on tactical tests, nodes searched, and small match results.

## Harness and Observability

- Tactical reports must include before/after solve counts against C4.
- Search diagnostics must include nodes, depth, quiescence nodes if tracked, and elapsed time.
- Any search limit changes must be visible in logs.
- Quiescence recursion must have explicit stopping conditions.

## Handoff / Next Task

Next task: C6_TIME_TT_ITERATIVE.

Handoff requirements:

- C6 can preserve C5 tactical improvements while adding time control.
- C6 can compare timed play against C5.
- No C2 legality gate regresses.

## Pre-Commit Tests by Work Package

Before each `C5.*` commit, run the targeted tests for that work package and record the exact command/output summary in the commit body.

- C5.1 - Baseline tactical suite run against C4 with saved results and no engine behavior changes except fixtures/reporting.
- C5.2 - Unit tests for capture/check/promotion ordering and proof that ordering does not drop or add legal moves.
- C5.3 - Unit tests for quiescence termination, capture-only/noisy continuation behavior, and bounded node count.
- C5.4 - Unit tests for mate-distance scoring where sooner mate is preferred and delayed loss is scored correctly.
- C5.5 - Unit tests for optional killer/history heuristic table updates, resets, and correctness-preserving fallback.
- C5.6 - C5-vs-C4 tactical comparison, legality regression, and small match or self-play smoke test.

## Required Tests/Evals

- Tactical suite improves over C4.
- Mate sooner preferred over mate later.
- Quiescence does not recurse forever.
- Capture ordering prioritizes valuable captures.
- Search still returns legal moves only.
- C5 beats C4 in a small match set.

## Required Code Review Checklist

- Is quiescence bounded?
- Does move ordering preserve correctness?
- Are tactical diagnostics logged?
- Are search limits respected?
- Are improvements measured against C4?

## Git/PR Protocol

- Branch: `agent/C5-tactical-hardening`
- Report: `/reports/tasks/C5_TACTICAL_HARDENING.md`
- Commit prefix: `C5:`

## Acceptance Criteria

- Tactical benchmark improves.
- No legality regression.
- No severe speed regression without explanation.

## Failure Conditions

- Infinite recursion.
- Illegal moves.
- No measurable improvement over C4.

## Suggested Owner Role

Engine Engineer.

## Dependencies

C4_ALPHA_BETA_SEARCH.

## Priority Level

P2.


## Required Orchestration Evidence

- implementation plan

- files allowed to change

- tests/evals to run

- interface risks

- expected report fields

- cost/time logging plan