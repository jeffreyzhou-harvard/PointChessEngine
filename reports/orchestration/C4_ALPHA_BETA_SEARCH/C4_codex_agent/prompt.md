# Champion Methodology Audit Prompt

Candidate: `C4_codex_agent`

Task: `C4_ALPHA_BETA_SEARCH`

Orchestration type: `codex_agent`

## Task Spec

# C4 - Alpha-Beta Search

## Objective

Implement a real search engine using minimax or negamax with alpha-beta pruning.

## Why This Matters

This turns the evaluator into a playable chess engine.

## Deliverables

- Negamax or minimax search.
- Alpha-beta pruning.
- Fixed-depth search.
- Terminal state handling.
- Search diagnostics:
  - best move
  - score
  - depth
  - nodes
  - time
  - principal variation if available

## Work Packages

- C4.1 - Define search API used internally by C7 UCI and E3 tournament tooling.
- C4.2 - Implement fixed-depth negamax or minimax with terminal handling.
- C4.3 - Add alpha-beta pruning with node counting and deterministic move iteration.
- C4.4 - Preserve board state across search through make/unmake or copy semantics.
- C4.5 - Return structured search diagnostics: best move, score, depth, nodes, time, and principal variation if available.
- C4.6 - Add tactical smoke tests such as mate in one and obvious material blunder avoidance.
- C4.7 - Add a random-legal baseline and self-play comparison.

## Harness and Observability

- Every search result should be convertible to UCI `bestmove` plus optional `info` diagnostics.
- Search tests must record depth, nodes, elapsed time, and selected move.
- Self-play logs should include game result, illegal move count, crash count, and seed.
- Search should expose enough diagnostics for C5/C6 to measure improvement.

## Handoff / Next Task

Next tasks:

1. C7_UCI_COMPATIBILITY to expose the engine through the C0 UCI contract.
2. C5_TACTICAL_HARDENING to improve tactical strength.

Handoff requirements:

- C7 can call search with depth and movetime-like limits.
- C5 can reuse move ordering and diagnostics without changing correctness.
- E3 can run self-play or tournament games once C7 is accepted.

## Pre-Commit Tests by Work Package

Before each `C4.*` commit, run the targeted tests for that work package and record the exact command/output summary in the commit body.

- C4.1 - Unit tests for search input limits, result object fields, legal best-move output, and conversion to UCI-ready move strings.
- C4.2 - Unit tests for fixed-depth terminal handling, mate/stalemate leaves, depth-zero evaluation, and no legal moves.
- C4.3 - Unit tests for alpha-beta node counts, deterministic move order, and score equality with unpruned minimax on tiny positions if feasible.
- C4.4 - Unit tests proving search does not mutate board state or counters after exploring moves.
- C4.5 - Unit tests for diagnostics: best move, score, depth, nodes, elapsed time, and principal variation if implemented.
- C4.6 - Unit tests for mate in one, simple queen blunder avoidance, and legal move return in tactical fixtures.
- C4.7 - Self-play smoke test against random legal baseline plus full C1/C2/C3 regression suite.

## Required Tests/Evals

- Search always returns legal move.
- Finds mate in one.
- Avoids obvious queen blunder in simple position.
- Search does not mutate board state unexpectedly.
- Deterministic result under fixed depth.
- C4 beats random legal baseline in self-play.

## Required Code Review Checklist

- Are score signs correct?
- Are alpha/beta updates correct?
- Are terminal states handled?
- Are legal moves used at every node?
- Are diagnostics accurate?

## Git/PR Protocol

- Branch: `agent/C4-alpha-beta-search`
- Report: `/reports/tasks/C4_ALPHA_BETA_SEARCH.md`
- Commit prefix: `C4:`

## Acceptance Criteria

- Fixed-depth search works.
- Engine can play complete games.
- Engine beats random baseline.

## Failure Conditions

- Illegal move returned.
- Search crashes in terminal positions.
- Board state corruption after search.

## Suggested Owner Role

Engine Engineer.

## Dependencies

C2_LEGAL_MOVE_GENERATION, C3_STATIC_EVALUATION.

## Priority Level

P1.


## Required Orchestration Evidence

- implementation plan

- files allowed to change

- tests/evals to run

- interface risks

- expected report fields

- cost/time logging plan