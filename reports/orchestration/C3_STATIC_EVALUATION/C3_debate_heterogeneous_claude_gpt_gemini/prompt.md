# Champion Methodology Audit Prompt

Candidate: `C3_debate_heterogeneous_claude_gpt_gemini`

Task: `C3_STATIC_EVALUATION`

Orchestration type: `debate_ensemble`

## Task Spec

# C3 - Static Handcrafted Evaluation

## Objective

Implement a basic handcrafted chess evaluation function.

## Why This Matters

The engine needs chess judgment before search can become strategic.

## Deliverables

Evaluation terms:

- Material balance.
- Piece-square tables.
- Mobility.
- Center control.
- Pawn structure.
- King safety.
- Terminal position scoring.

Expose:

```python
evaluate(position) -> score
```

Score convention must be documented clearly.

## Work Packages

- C3.1 - Define score convention, units, terminal values, and side-to-move perspective.
- C3.2 - Implement material balance and piece-square tables.
- C3.3 - Add mobility and center-control terms using legal or pseudo-legal move data as appropriate.
- C3.4 - Add pawn-structure terms: doubled, isolated, passed, and advanced pawns.
- C3.5 - Add king-safety terms with simple, explainable heuristics.
- C3.6 - Add deterministic weight configuration and documentation for future tuning.
- C3.7 - Add evaluation diagnostics for tests and reports.

## Harness and Observability

- Evaluation tests must log the term breakdown for failing positions when feasible.
- The task report must document score sign, rough scale, and terminal score policy.
- Later search tasks should be able to request a single scalar score and optional diagnostics.
- Do not tune weights against hidden tournament results.

## Handoff / Next Task

Next task: C4_ALPHA_BETA_SEARCH.

Handoff requirements:

- C4 can call the evaluator from any legal or terminal position.
- Terminal scoring is consistent with checkmate/stalemate from C2.
- Evaluation is deterministic under repeated calls.

## Pre-Commit Tests by Work Package

Before each `C3.*` commit, run the targeted tests for that work package and record the exact command/output summary in the commit body.

- C3.1 - Unit tests for score sign, side-to-move perspective, terminal checkmate score, terminal stalemate score, and documented score units.
- C3.2 - Unit tests for material deltas, piece-square table symmetry, and starting position near-zero score.
- C3.3 - Unit tests for mobility and center-control term changes on controlled positions.
- C3.4 - Unit tests for doubled pawns, isolated pawns, passed pawns, and advanced passed-pawn bonus.
- C3.5 - Unit tests for exposed king penalty, castled/safer king bonus if implemented, and no terminal-score override mistakes.
- C3.6 - Unit tests for deterministic weight loading/defaults and stable evaluation with fixed config.
- C3.7 - Unit tests for optional evaluation diagnostics and full C3 regression suite.

## Required Tests/Evals

- Extra queen evaluates better than equal material.
- Checkmate evaluates as decisive.
- Stalemate evaluates as draw.
- Symmetric starting position evaluates near zero.
- Advanced passed pawn receives bonus.
- Exposed king receives penalty.
- More legal mobility generally improves score.

## Required Code Review Checklist

- Are terms modular?
- Are weights documented?
- Is score perspective consistent?
- Are terminal states handled first?
- Can weights be tuned later?

## Git/PR Protocol

- Branch: `agent/C3-static-evaluation`
- Report: `/reports/tasks/C3_STATIC_EVALUATION.md`
- Commit prefix: `C3:`

## Acceptance Criteria

- Sanity tests pass.
- Evaluation is deterministic.
- Evaluation integrates with engine interface.

## Failure Conditions

- Score sign flips incorrectly.
- Terminal states are mishandled.
- Evaluation has unexplained hardcoded behavior.

## Suggested Owner Role

Engine Engineer.

## Dependencies

C2_LEGAL_MOVE_GENERATION.

## Priority Level

P1.


## Required Orchestration Evidence

- implementation plan

- files allowed to change

- tests/evals to run

- interface risks

- expected report fields

- cost/time logging plan