# N5 - Hybrid Neural/Classical Engine

## Objective

Create a tournament-ready engine that combines classical search with neural assistance.

## Why This Matters

This is the main neural-assisted final artifact.

## Deliverables

One or more of:

- Classical search + neural policy ordering.
- Classical search + neural value evaluation.
- Classical search + neural move-quality sampling.
- Neural candidate pruning + classical final search.

Must include:

- UCI compatibility.
- Legal move guarantee.
- Fallback path.
- Benchmark report.

## Work Packages

- N5.1 - Choose hybrid strategy and document why it is worth testing.
- N5.2 - Implement clean neural/classical boundary with config flags.
- N5.3 - Add fallback behavior for missing model, failed inference, or slow inference.
- N5.4 - Ensure UCI mode can launch hybrid and classical variants.
- N5.5 - Run legality, UCI, timed, and tournament checks.
- N5.6 - Compare hybrid against best classical engine and generated-engine field.
- N5.7 - Record cost, latency, and model artifact requirements.

## Harness and Observability

- Hybrid tournament logs must identify model version and fallback events.
- Inference errors must be counted and surfaced in reports.
- Benchmark reports must separate engine strength from engineering overhead.

## Handoff / Next Task

Next tasks:

1. E3_TOURNAMENT_RUNNER final round robin.
2. N6_NEURAL_STRENGTH_CALIBRATION if strength sampling is pursued.
3. E5_FINAL_REPORT_TEMPLATE.

Handoff requirements:

- Final evals can launch both hybrid and classical baselines.
- Model artifacts and config are reproducible.
- Hybrid limitations are documented.

## Required Tests/Evals

- Passes legality tests.
- Passes UCI tests.
- Respects time controls.
- Neural failure does not crash engine.
- Hybrid vs best classical engine tournament.
- Hybrid vs generated engines tournament.
- Hybrid vs Stockfish calibration.

## Required Code Review Checklist

- Is neural/classical boundary clean?
- Is fallback explicit?
- Are model files/version documented?
- Is inference cost logged?
- Are results compared fairly?

## Git/PR Protocol

- Branch: `agent/N5-hybrid-engine`
- Report: `/reports/tasks/N5_HYBRID_ENGINE.md`
- Commit prefix: `N5:`

## Acceptance Criteria

- Hybrid engine can enter final tournament.
- No legality or UCI regression.
- Performance impact is measured.

## Failure Conditions

- Hybrid cannot play full games.
- Neural component causes crashes.
- No comparison against classical baseline.

## Suggested Owner Role

Integrator / Neural Engineer.

## Dependencies

N4_NEURAL_POLICY_ORDERING or N3_NEURAL_VALUE_EVAL, C7_UCI_COMPATIBILITY.

## Priority Level

P3.
