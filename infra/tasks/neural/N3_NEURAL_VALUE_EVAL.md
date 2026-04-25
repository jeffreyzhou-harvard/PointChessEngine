# N3 - Neural Value Evaluator

## Objective

Train or implement a small neural model that evaluates chess positions.

## Why This Matters

This tests whether neural evaluation can improve or replace handcrafted evaluation.

## Deliverables

- Value model.
- Training script.
- Inference wrapper.
- Checkpoint save/load.
- Evaluation report.
- Optional integration with classical search.

## Work Packages

- N3.1 - Define value target, score scaling, and train/eval split usage.
- N3.2 - Implement small value model and deterministic forward pass.
- N3.3 - Implement training loop with seed control.
- N3.4 - Implement checkpoint save/load and inference wrapper.
- N3.5 - Validate overfit on a tiny dataset.
- N3.6 - Compare against C3 handcrafted evaluation.
- N3.7 - Document latency and failure fallback.

## Harness and Observability

- Training reports must include seed, dataset version, model version, loss curves or summary metrics, and hardware notes.
- Inference reports must include latency and output range.
- If integrated into search, the task must log fallback behavior when a checkpoint is missing.

## Handoff / Next Task

Next tasks:

1. N5_HYBRID_ENGINE if value integration is promising.
2. E5_FINAL_REPORT_TEMPLATE for reporting even if results are negative.

Handoff requirements:

- N5 can load the inference wrapper safely.
- Classical engine still has a C3 fallback.
- Comparison against handcrafted evaluation is documented.

## Required Tests/Evals

- Forward pass shape is correct.
- Model output is finite.
- Model can overfit a tiny dataset.
- Checkpoint save/load works.
- Inference is deterministic in eval mode.
- Validation loss is reported.
- Inference latency is reported.

## Required Code Review Checklist

- Are training and inference separated?
- Is seed control implemented?
- Is model version documented?
- Is score scaling documented?
- Is there fallback if model fails?

## Git/PR Protocol

- Branch: `agent/N3-neural-value-eval`
- Report: `/reports/tasks/N3_NEURAL_VALUE_EVAL.md`
- Commit prefix: `N3:`

## Acceptance Criteria

- Model trains and evaluates.
- Inference wrapper works.
- Result is compared against handcrafted evaluator.

## Failure Conditions

- Model cannot train.
- Outputs NaN/inf.
- No comparison to classical baseline.

## Suggested Owner Role

Neural Engineer.

## Dependencies

N1_DATASET_LABELING, N2_ENCODER_LEGAL_MASK, C3_STATIC_EVALUATION.

## Priority Level

P4.
