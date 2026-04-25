# N4 - Neural Policy for Move Ordering

## Objective

Use a neural policy model to rank legal moves for search.

## Why This Matters

Move ordering can improve alpha-beta efficiency without replacing the classical engine.

## Deliverables

- Policy model.
- Legal masked output.
- Top-k move ranking.
- Integration with move ordering.
- Fallback to classical ordering.
- Benchmark comparing classical vs neural ordering.

## Work Packages

- N4.1 - Define policy target and top-k metrics.
- N4.2 - Implement policy model or inference adapter.
- N4.3 - Apply N2 legal mask before move selection.
- N4.4 - Convert policy output into ordered legal move lists.
- N4.5 - Integrate ordered moves into C4/C5/C6 search without changing alpha-beta correctness.
- N4.6 - Benchmark top-k accuracy, nodes searched, tactical solve rate, and latency.
- N4.7 - Document fallback to classical ordering.

## Harness and Observability

- Every benchmark must record model version, encoder version, engine commit, and fallback state.
- Illegal move mask failures must fail the task immediately.
- Search comparisons must report both quality and overhead.

## Handoff / Next Task

Next task: N5_HYBRID_ENGINE.

Handoff requirements:

- N5 can enable or disable neural policy ordering through config.
- C6 search remains correct if the neural policy is unavailable.
- Benchmarks identify whether neural ordering helped or hurt.

## Required Tests/Evals

- Top-k moves are legal.
- Masked policy never selects illegal moves.
- Search still returns legal moves.
- Fallback works if model unavailable.
- Top-1/top-3/top-5 accuracy reported.
- Nodes searched under fixed time compared against C6.
- Tactical solve rate compared against C6.

## Required Code Review Checklist

- Is neural policy advisory only?
- Does alpha-beta correctness remain intact?
- Is inference latency measured?
- Is fallback safe?
- Is model version pinned?

## Git/PR Protocol

- Branch: `agent/N4-neural-policy-ordering`
- Report: `/reports/tasks/N4_NEURAL_POLICY_ORDERING.md`
- Commit prefix: `N4:`

## Acceptance Criteria

- Neural ordering integrates with search.
- No legality regression.
- Engine impact is measured.

## Failure Conditions

- Illegal move selected.
- Search becomes slower without documentation.
- No benchmark comparison.

## Suggested Owner Role

Neural Engineer / Engine Engineer.

## Dependencies

N1_DATASET_LABELING, N2_ENCODER_LEGAL_MASK, C4_ALPHA_BETA_SEARCH.

## Priority Level

P3.
