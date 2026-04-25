# N1 - Dataset and Labeling Pipeline

## Objective

Create a reproducible chess-position dataset for neural experiments.

## Why This Matters

Neural tasks are only meaningful if the data is valid, legal, and aligned with the chess engine.

## Deliverables

- FEN dataset.
- Legal moves per position.
- Labels:
  - best move if available
  - top-k moves if available
  - evaluation score if available
  - game result if available
  - centipawn-loss bucket if available
- Train/validation/test split.
- Dataset schema documentation.

## Work Packages

- N1.1 - Define dataset sources, license/usage notes, and reproducibility constraints.
- N1.2 - Define row schema for FEN, legal moves, labels, source, split, and metadata.
- N1.3 - Implement deterministic sampling and train/validation/test split policy.
- N1.4 - Validate every FEN and every labeled move against C1/C2.
- N1.5 - Log label distributions and leakage checks.
- N1.6 - Document loader contract for N2/N3/N4.

## Harness and Observability

- Dataset generation must write a manifest with source, seed, counts, split hashes if available, and validation summary.
- Validation failures must report row ID, FEN, label, and reason.
- Dataset reports should be linked from `reports/evals/` or the active run folder.

## Handoff / Next Task

Next task: N2_ENCODER_LEGAL_MASK.

Handoff requirements:

- N2 can load split records deterministically.
- Every labeled move is legal under C2.
- Schema version is documented.

## Required Tests/Evals

- Every FEN is valid.
- Every labeled move is legal.
- Train/validation/test split is deterministic.
- No duplicate leakage across splits.
- Label distribution is logged.
- Dataset loader returns expected fields.

## Required Code Review Checklist

- Is the data source documented?
- Is there leakage?
- Are labels legal?
- Is generation reproducible?
- Is schema stable and documented?

## Git/PR Protocol

- Branch: `agent/N1-dataset-labeling`
- Report: `/reports/tasks/N1_DATASET_LABELING.md`
- Commit prefix: `N1:`

## Acceptance Criteria

- Dataset can be generated or loaded.
- Dataset validity checks pass.
- Neural tasks can consume it.

## Failure Conditions

- Illegal labels.
- Invalid FENs.
- Non-reproducible split.
- Undocumented data source.

## Suggested Owner Role

Neural/Data Engineer.

## Dependencies

C1_BOARD_FEN_MOVE, C2_LEGAL_MOVE_GENERATION.

## Priority Level

P3.
