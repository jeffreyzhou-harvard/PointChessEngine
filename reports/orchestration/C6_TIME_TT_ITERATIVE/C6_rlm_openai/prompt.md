# RLM PointChess Orchestration Prompt

Candidate: `C6_rlm_openai`

Task: `C6_TIME_TT_ITERATIVE`

## System

You are an RLM agent building a PointChess candidate engine.
Decompose the task recursively, keep public interfaces stable, implement only
the assigned scope, and verify legality through tests before proposing a merge.


## Recursive Decomposition Directive

Create a recursive build plan with child checks for:
1. UCI interface compatibility
2. legal move guarantees
3. evaluator signal sanity
4. search/time-control behavior
5. Champion-mode observability
Return the smallest patch that satisfies the milestone.


## Task Spec

# C6 - Time Management, Iterative Deepening, and Transposition Table

## Objective

Make the engine reliable under real time controls.

## Why This Matters

Tournament evaluation requires engines to return moves within time limits.

## Deliverables

- Iterative deepening.
- Time management.
- Best-so-far move.
- Transposition table.
- Search interruption.
- Depth/time diagnostics.

## Work Packages

- C6.1 - Define time-control input model for internal search and UCI `go` commands.
- C6.2 - Implement iterative deepening with best-so-far move preservation.
- C6.3 - Implement search interruption and deadline checks.
- C6.4 - Add transposition table with bound type, depth, score, best move, and safe replacement policy.
- C6.5 - Add timed-search diagnostics: depth reached, nodes, nps if available, hash stats if available, and stop reason.
- C6.6 - Benchmark C6 against C5 under fixed time controls.

## Harness and Observability

- Timed tests must record requested time, actual elapsed time, selected move, depth reached, and stop reason.
- Timeout failures must be reported separately from illegal move failures.
- Transposition table use must be disableable or measurable for comparison.
- C7 must be able to pass UCI time controls into this layer.

## Handoff / Next Task

Next tasks:

1. C7_UCI_COMPATIBILITY if not already accepted.
2. C8_ELO_SLIDER after timed search and UCI options are stable.

Handoff requirements:

- C7 can call timed search safely.
- C8 can scale depth/time/noise by strength.
- E3 can run games without frequent time forfeits.

## Pre-Commit Tests by Work Package

Before each `C6.*` commit, run the targeted tests for that work package and record the exact command/output summary in the commit body.

- C6.1 - Unit tests for time-control parsing/modeling, depth-only limits, movetime limits, and invalid limit handling.
- C6.2 - Unit tests for iterative deepening returning best-so-far move and increasing reported depth when time allows.
- C6.3 - Unit tests for deadline checks, interruption behavior, stop reason, and returning before timeout tolerance.
- C6.4 - Unit tests for transposition table store/probe, bound type behavior, depth replacement, collision safety, and legal best-move use.
- C6.5 - Unit tests for timed diagnostics: depth, nodes, elapsed time, stop reason, and hash stats if available.
- C6.6 - Timed C6-vs-C5 comparison, C2 legality regression, and UCI movetime smoke if C7 exists.

## Required Tests/Evals

- `movetime=100ms` returns within tolerance.
- Search returns best-so-far if interrupted.
- Repeated search is stable.
- Transposition table does not produce illegal moves.
- Depth reached improves under longer time.
- C6 beats or matches C5 under fixed time.

## Required Code Review Checklist

- Is time handling isolated?
- Are hash entries valid?
- Are bound types handled correctly?
- Does stop/interruption work?
- Are stale table entries safe?

## Git/PR Protocol

- Branch: `agent/C6-time-tt-iterative`
- Report: `/reports/tasks/C6_TIME_TT_ITERATIVE.md`
- Commit prefix: `C6:`

## Acceptance Criteria

- Engine can play timed games.
- Timeout rate is low.
- No legality regression.

## Failure Conditions

- Engine hangs.
- Engine regularly exceeds time.
- Transposition table corrupts search result.

## Suggested Owner Role

Engine Engineer / Systems Engineer.

## Dependencies

C5_TACTICAL_HARDENING.

## Priority Level

P2.


## Required Output

- recursively decompose the implementation plan

- identify files allowed to change

- identify tests to add or run

- identify interface risks

- produce a patch plan or patch instructions

- write candidate-report content with AI usage and limitations