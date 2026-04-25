# E1 - Perft and Rule-Correctness Suite

## Objective

Define the standard legality and perft tests every engine must pass before tournament play.

## Why This Matters

Perft is the main correctness gate for chess move generation. It gives a deterministic way to prove that generated engines obey legal chess before they are compared for strength.

## Deliverables

- Perft test harness.
- Known perft positions.
- Special rule test cases.
- Failure report format.

## Work Packages

- E1.1 - Define perft harness interface against the engine implementation and/or C0/C7 UCI command where applicable.
- E1.2 - Add baseline known positions and expected counts.
- E1.3 - Add special-rule fixtures for castling, en passant, promotion, pins, checkmate, and stalemate.
- E1.4 - Implement or specify root move breakdown for debugging mismatches.
- E1.5 - Define legality gate report format for tournament admission.

## Harness and Observability

- Perft reports must include FEN, depth, expected count, actual count, elapsed time, and root move breakdown if available.
- Legality gate output should be linked from `reports/evals/` and `reports/runs/<RUN_ID>/eval_index.md`.
- Tournament runner must reject engines that fail the required legality gate.

## Handoff / Next Task

Next task: C2_LEGAL_MOVE_GENERATION.

Handoff requirements:

- C2 knows exactly which perft and special-rule cases must pass.
- E3 can use E1 pass/fail status as a tournament gate.

## Required Tests/Evals

- Starting position perft depth 1 = 20.
- Starting position perft depth 2 = 400.
- Add deeper perft only if performance allows.
- Castling positions.
- En passant positions.
- Promotion positions.
- Pinned piece positions.
- Checkmate/stalemate positions.

## Required Code Review Checklist

- Are expected perft counts sourced and documented?
- Are failure reports useful enough to debug bad move generation?
- Can the suite run against any C0-compatible engine?
- Does the suite separate legality failures from performance limits?
- Are special rule cases explicit and reproducible?

## Git/PR Protocol

- Branch: `agent/E1-perft-suite`
- Report: `/reports/tasks/E1_PERFT_SUITE.md`
- Commit prefix: `E1:`

## Acceptance Criteria

- C2 must pass basic perft.
- All tournament engines must pass legality gate.
- Any failure must produce a useful debug report.

## Failure Conditions

- Missing baseline starting-position perft tests.
- Illegal move generation can pass the suite.
- Failures do not identify the position, depth, and mismatch.

## Suggested Owner Role

Evaluation Engineer / Chess Rules Engineer.

## Dependencies

C0_ENGINE_INTERFACE.

## Priority Level

P0.
