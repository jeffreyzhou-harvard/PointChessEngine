# N2 - Position Encoder and Legal Move Mask

## Objective

Create neural model inputs from chess positions and enforce legality through masks.

## Why This Matters

Neural components must not output illegal moves.

## Deliverables

- Board tensor encoder.
- Side-to-move feature.
- Castling rights feature.
- En passant feature.
- Move-index mapping.
- Legal move mask.
- Batch encoding.

## Work Packages

- N2.1 - Define tensor planes and scalar features.
- N2.2 - Define stable move-index mapping, including promotions and special moves.
- N2.3 - Implement single-position encoder.
- N2.4 - Implement legal move mask from C2 legal moves.
- N2.5 - Implement batch encoding and shape checks.
- N2.6 - Measure encoding and masking latency on representative batches.

## Harness and Observability

- Encoder tests must log shape, dtype, feature version, and move-index version.
- Mask mismatches must report FEN, expected legal moves, masked moves, missing moves, and extra moves.
- Artifacts should identify the C2 commit or implementation version used for legal labels.

## Handoff / Next Task

Next tasks:

1. N4_NEURAL_POLICY_ORDERING.
2. N3_NEURAL_VALUE_EVAL.

Handoff requirements:

- Neural models can consume encoder outputs without knowing chess internals.
- Policy heads can map logits back to UCI moves.
- Illegal moves are masked before policy sampling.

## Required Tests/Evals

- Starting position encodes correctly.
- Custom FEN encodes correctly.
- Legal mask exactly matches legal moves from engine.
- Promotion moves are represented.
- En passant is represented.
- Batch shapes are correct.
- Encoding is deterministic.

## Required Code Review Checklist

- Is move-index mapping documented?
- Can illegal moves leak through the mask?
- Is encoder independent from model architecture?
- Are edge cases covered?
- Is latency measured?

## Git/PR Protocol

- Branch: `agent/N2-encoder-legal-mask`
- Report: `/reports/tasks/N2_ENCODER_LEGAL_MASK.md`
- Commit prefix: `N2:`

## Acceptance Criteria

- Encoder and mask pass all tests.
- Neural policy/value tasks can use the interface.

## Failure Conditions

- Legal mask mismatch.
- Unstable move indexing.
- Illegal move allowed by mask.

## Suggested Owner Role

Neural Engineer.

## Dependencies

N1_DATASET_LABELING, C2_LEGAL_MOVE_GENERATION.

## Priority Level

P3.
