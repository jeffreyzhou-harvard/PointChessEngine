# Champion Methodology Audit Prompt

Candidate: `C1_codex_agent`

Task: `C1_BOARD_FEN_MOVE`

Orchestration type: `codex_agent`

## Task Spec

# C1 - Board, FEN, and Move Representation

## Objective

Implement the core chess state representation.

## Why This Matters

Every later task depends on representing positions correctly.

## Deliverables

- Board representation.
- Piece representation.
- Move representation.
- FEN parser.
- FEN serializer.
- UCI move notation parser/serializer.
- Side-to-move tracking.
- Castling rights.
- En passant square.
- Halfmove and fullmove counters.

## Work Packages

- C1.1 - Define board coordinates, squares, colors, pieces, and immutable or copy-safe position state.
- C1.2 - Implement FEN parsing with descriptive validation errors.
- C1.3 - Implement deterministic FEN serialization.
- C1.4 - Implement UCI move representation and parse/serialize helpers, including promotions.
- C1.5 - Track side to move, castling rights, en passant square, halfmove clock, and fullmove number.
- C1.6 - Add focused tests and fixtures for valid, invalid, and round-trip positions.

## Harness and Observability

- Add test fixtures with names that later perft and UCI tasks can reuse.
- Record parser failure examples in the task report.
- Document the position and move APIs that C2 must consume.
- Do not expose this as the benchmark interface; external evaluation remains UCI through C0/C7.

## Handoff / Next Task

Next task: C2_LEGAL_MOVE_GENERATION.

Handoff requirements:

- C2 can construct positions from FEN.
- C2 can enumerate or apply UCI moves using the move representation.
- Serialization is stable enough for perft failure reports.

## Pre-Commit Tests by Work Package

Before each `C1.*` commit, run the targeted tests for that work package and record the exact command/output summary in the commit body.

- C1.1 - Unit tests for square indexing, piece/color representation, equality/copy behavior, and empty/start position construction.
- C1.2 - Unit tests for valid FEN parsing, invalid FEN errors, missing fields, bad ranks, bad side-to-move, bad counters, and bad castling/en passant fields.
- C1.3 - Unit tests for starting FEN serialization, custom FEN serialization, deterministic round trips, and counter preservation.
- C1.4 - Unit tests for UCI move parsing/serialization, invalid UCI moves, captures if represented, and promotion notation.
- C1.5 - Unit tests for side-to-move, castling rights, en passant square, halfmove clock, and fullmove number preservation.
- C1.6 - Run the full C1 parser/serializer/move test suite plus any fast existing project tests.

## Required Tests/Evals

- Starting FEN parses correctly.
- Starting FEN serializes back correctly.
- Custom FEN round trip works.
- Invalid FEN raises clean error.
- Side-to-move parsed correctly.
- Castling rights parsed correctly.
- En passant square parsed correctly.
- Move `e2e4` parses and serializes correctly.
- Promotion move `e7e8q` parses and serializes correctly.

## Required Code Review Checklist

- Is board state separate from UI and search?
- Is move representation clear?
- Are FEN edge cases handled?
- Are errors descriptive?
- Is serialization deterministic?

## Git/PR Protocol

- Branch: `agent/C1-board-fen-move`
- Report: `/reports/tasks/C1_BOARD_FEN_MOVE.md`
- Commit prefix: `C1:`

## Acceptance Criteria

- All FEN and move tests pass.
- Board state can be used by legal move generation.
- No search/evaluation/UI logic is mixed into this layer.

## Failure Conditions

- FEN roundtrip fails.
- Invalid FEN silently succeeds.
- Board state is coupled to UI/search.

## Suggested Owner Role

Chess Rules Engineer.

## Dependencies

C0_ENGINE_INTERFACE.

## Priority Level

P1.


## Required Orchestration Evidence

- implementation plan

- files allowed to change

- tests/evals to run

- interface risks

- expected report fields

- cost/time logging plan