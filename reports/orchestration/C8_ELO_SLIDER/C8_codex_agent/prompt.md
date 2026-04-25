# Champion Methodology Audit Prompt

Candidate: `C8_codex_agent`

Task: `C8_ELO_SLIDER`

Orchestration type: `codex_agent`

## Task Spec

# C8 - Approximate Elo / Strength Slider

## Objective

Add adjustable playing strength.

## Why This Matters

This improves demo quality and enables calibration experiments.

## Deliverables

- Strength config from roughly 400 to 2400.
- Depth scaling.
- Time scaling.
- Controlled evaluation noise.
- Top-k suboptimal move sampling.
- UCI and/or UI exposure.

## Work Packages

- C8.1 - Define strength configuration fields and explicitly document that values are approximate.
- C8.2 - Implement depth and time scaling by strength.
- C8.3 - Implement controlled evaluation noise or move-score perturbation with fixed-seed reproducibility.
- C8.4 - Implement top-k legal move sampling that preserves legality.
- C8.5 - Expose strength through UCI options and any UI if applicable.
- C8.6 - Add calibration experiment against fixed opponents or limited-strength Stockfish.
- C8.7 - Report blunder rate, average centipawn loss if available, and behavior changes by strength.

## Harness and Observability

- Strength tests must log seed, configured strength, chosen move, legal move count, and search budget.
- Calibration reports must say "estimated relative strength" rather than exact Elo.
- The final showcase should include a table or chart of strength setting versus observed behavior.
- Illegal move rate must remain zero at every strength.

## Handoff / Next Task

Next tasks:

1. E3_TOURNAMENT_RUNNER calibration run.
2. N6_NEURAL_STRENGTH_CALIBRATION if neural/data-driven sampling is pursued.
3. E5_FINAL_REPORT_TEMPLATE for final reporting after tournaments.

Handoff requirements:

- UCI exposes strength settings in a way the tournament runner can configure.
- Calibration artifacts are saved and linked from reports.
- Claims are framed as approximate and time-control-specific.

## Pre-Commit Tests by Work Package

Before each `C8.*` commit, run the targeted tests for that work package and record the exact command/output summary in the commit body.

- C8.1 - Unit tests for strength config bounds, defaults, invalid values, and documentation examples.
- C8.2 - Unit tests proving low strength gets lower depth/time budget and high strength gets higher budget.
- C8.3 - Unit tests for fixed-seed reproducibility, bounded noise, and no noise-driven illegal move output.
- C8.4 - Unit tests for top-k legal move sampling, distribution changes by strength, and zero illegal selections.
- C8.5 - UCI option transcript tests for setting strength and observing changed search configuration.
- C8.6 - Calibration smoke test against fixed opponent or limited Stockfish when available, with caveated output.
- C8.7 - Report-generation tests or validation for blunder-rate/behavior table and final C8 regression suite.

## Required Tests/Evals

- Low strength uses smaller search budget.
- High strength uses larger search budget.
- All strengths return legal moves.
- Fixed seed gives reproducible weaker play.
- Move choice distribution changes by strength.
- Blunder rate decreases as strength increases.

## Required Code Review Checklist

- Does not claim exact Elo.
- Weaker play is plausible, not random illegal nonsense.
- Strength config is documented.
- Works from UCI and UI if applicable.
- Calibration method is explained.

## Git/PR Protocol

- Branch: `agent/C8-elo-slider`
- Report: `/reports/tasks/C8_ELO_SLIDER.md`
- Commit prefix: `C8:`

## Acceptance Criteria

- Slider changes engine behavior.
- No legality regression.
- Basic Stockfish calibration can be run.

## Failure Conditions

- Slider has no effect.
- Slider causes illegal moves.
- Implementation fakes exact Elo claims.

## Suggested Owner Role

Strength Tuning Engineer / UI Engineer.

## Dependencies

C4_ALPHA_BETA_SEARCH, C7_UCI_COMPATIBILITY.

## Priority Level

P2.


## Required Orchestration Evidence

- implementation plan

- files allowed to change

- tests/evals to run

- interface risks

- expected report fields

- cost/time logging plan