# Champion Methodology Audit Prompt

Candidate: `C2_debate_heterogeneous_claude_gpt_gemini`

Task: `C2_LEGAL_MOVE_GENERATION`

Orchestration type: `debate_ensemble`

## Task Spec

# C2 - Legal Move Generation and Rule Correctness

## Objective

Generate only legal chess moves.

## Why This Matters

A chess engine that returns illegal moves cannot be evaluated meaningfully.

## Deliverables

- Pseudo-legal move generation.
- Legal move filtering.
- Check detection.
- Pinned piece handling.
- Castling legality.
- En passant legality.
- Promotion handling.
- Checkmate detection.
- Stalemate detection.

## Work Packages

- C2.1 - Implement attack detection and king-safety primitives.
- C2.2 - Generate pseudo-legal pawn, knight, king, sliding-piece, and promotion moves.
- C2.3 - Implement special move rules: castling, en passant, and promotion choices.
- C2.4 - Implement make/unmake or apply/copy semantics with state restoration tests.
- C2.5 - Filter pseudo-legal moves into legal moves by preventing own-king exposure.
- C2.6 - Implement check, checkmate, and stalemate detection.
- C2.7 - Integrate perft hooks and debug output for mismatched counts.

## Harness and Observability

- Perft failures must report FEN, depth, expected count, actual count, and root move breakdown when possible.
- Legality tests must include special-rule fixture names that can be reused by E1.
- Add a zero-illegal-move gate that later search and UCI tasks can reuse.
- Record known unsupported depths or performance limits in the task report.

## Handoff / Next Task

Next tasks:

1. C3_STATIC_EVALUATION for position scoring.
2. C4_ALPHA_BETA_SEARCH after C3 is accepted.

Handoff requirements:

- C3 can ask for terminal state and legal mobility.
- C4 can generate legal moves at every search node.
- E1 can call perft against this implementation.

## Pre-Commit Tests by Work Package

Before each `C2.*` commit, run the targeted tests for that work package and record the exact command/output summary in the commit body.

- C2.1 - Unit tests for attacked squares, king in check, double check, and attacks from every piece type.
- C2.2 - Unit tests for pseudo-legal pawn, knight, king, bishop, rook, queen, and promotion move generation on simple positions.
- C2.3 - Unit tests for legal castling preconditions, en passant availability, en passant capture application, and all promotion choices.
- C2.4 - Unit tests proving apply/unapply or copy-based move application preserves board state, counters, castling, and en passant state.
- C2.5 - Unit tests for pinned pieces, king moves into check, en passant discovered-check edge case, and every legal move leaving own king safe.
- C2.6 - Unit tests for check detection, checkmate, stalemate, insufficient no-legal-move ambiguity if represented, and terminal status.
- C2.7 - Perft tests for starting position depth 1 and 2, plus root breakdown on at least one special-rule fixture.

## Required Tests/Evals

- Starting position legal moves = 20.
- Perft depth 1 from starting position = 20.
- Perft depth 2 from starting position = 400.
- Promotion choices generated.
- Castling through check is illegal.
- Castling when path is blocked is illegal.
- En passant works.
- En passant discovered-check edge case is handled.
- Pinned piece cannot expose king.
- Checkmate detected.
- Stalemate detected.
- Every generated legal move leaves own king safe.

## Required Code Review Checklist

- Are pseudo-legal and legal generation separated?
- Is make/unmake or apply/copy state safe?
- Are special rules handled generally, not as hardcoded hacks?
- Are perft failures easy to debug?
- Does the implementation avoid illegal king states?

## Git/PR Protocol

- Branch: `agent/C2-legal-move-generation`
- Report: `/reports/tasks/C2_LEGAL_MOVE_GENERATION.md`
- Commit prefix: `C2:`

## Acceptance Criteria

- Perft depth 1 and 2 pass from starting position.
- Special move tests pass.
- Engine never returns illegal moves in the test suite.

## Failure Conditions

- Any illegal move is generated as legal.
- Castling/en passant/promotion are missing.
- Checkmate/stalemate are not detected.

## Suggested Owner Role

Chess Rules Engineer.

## Dependencies

C1_BOARD_FEN_MOVE, E1_PERFT_SUITE.

## Priority Level

P1.


## Required Orchestration Evidence

- implementation plan

- files allowed to change

- tests/evals to run

- interface risks

- expected report fields

- cost/time logging plan