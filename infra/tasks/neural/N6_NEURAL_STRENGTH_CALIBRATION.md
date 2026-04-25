# N6 - Neural Strength Calibration

## Objective

Use neural or data-driven move-quality estimates to make the Elo slider more human-like.

## Why This Matters

A good strength slider is a high-value demo feature and supports creativity/ingenuity.

## Deliverables

- Move-quality bucket predictor or sampler.
- Strength-dependent move sampling.
- Average centipawn loss or blunder-rate profile.
- Integration with C8 slider.
- Calibration report.

## Work Packages

- N6.1 - Define move-quality buckets and sampling behavior by strength.
- N6.2 - Implement predictor or sampler using N1/N2 data.
- N6.3 - Integrate sampler with C8 strength configuration.
- N6.4 - Add fixed-seed reproducibility and legality gates.
- N6.5 - Measure blunder rate or average centipawn loss across strength settings.
- N6.6 - Run fixed-opponent calibration and document caveats.

## Harness and Observability

- Calibration logs must record strength, seed, selected move, candidate scores if available, and opponent.
- Reports must avoid exact Elo claims unless a supported calibration method exists.
- Final showcase should compare C8 classical sampling versus N6 neural/data-driven sampling.

## Handoff / Next Task

Next task: E5_FINAL_REPORT_TEMPLATE.

Handoff requirements:

- Strength behavior is measurable and reproducible.
- Illegal move rate is zero.
- Calibration evidence is linked from final report artifacts.

## Required Tests/Evals

- Low strength permits weaker legal moves.
- High strength prefers stronger moves.
- Illegal move rate remains zero.
- Fixed seed is reproducible.
- Blunder rate decreases with strength.
- Observed performance changes against fixed opponents.

## Required Code Review Checklist

- Does not claim exact Elo.
- Sampling is explainable.
- No random illegal blunders.
- Calibration is documented.
- Strength behavior is testable.

## Git/PR Protocol

- Branch: `agent/N6-neural-strength-calibration`
- Report: `/reports/tasks/N6_NEURAL_STRENGTH_CALIBRATION.md`
- Commit prefix: `N6:`

## Acceptance Criteria

- Slider behavior becomes more realistic.
- Calibration evidence exists.
- No legality regression.

## Failure Conditions

- Random nonsense moves.
- No measurable difference by strength.
- Illegal moves appear.

## Suggested Owner Role

Strength Tuning Engineer / Neural Engineer.

## Dependencies

C8_ELO_SLIDER, N1_DATASET_LABELING, N2_ENCODER_LEGAL_MASK.

## Priority Level

P4.
