# E3 - Tournament Runner

## Objective

Define the generated-engine round robin and Stockfish calibration protocol.

## Why This Matters

Tournament results are the main comparative output for engine quality. A shared runner prevents each workflow from inventing incompatible strength measurements.

## Deliverables

- Script or instructions for generated-engine round robin.
- Script or instructions for Stockfish calibration.
- Result table format.
- PGN/log output format.

Generated-engine tournament:

- Every generated engine plays every other generated engine.
- Alternate colors.
- Use fixed time controls.
- Log wins/losses/draws/crashes/timeouts/illegal move forfeits.

Stockfish calibration:

- Play each engine against limited-strength Stockfish configurations.
- Do not claim exact Elo.
- Report estimated relative strength under our time controls.

Metrics:

- wins
- losses
- draws
- illegal move forfeits
- crashes
- timeouts
- average game length
- estimated Elo/ranking
- cost/time per tournament

## Work Packages

- E3.1 - Define engine registry input using the C0 manifest format.
- E3.2 - Implement or document round-robin pairing, color alternation, and fixed time controls.
- E3.3 - Gate entrants through E1 legality and E2 UCI compliance.
- E3.4 - Record PGN/log files, standings, crashes, timeouts, and illegal move forfeits.
- E3.5 - Define limited-strength Stockfish calibration protocol with caveats.
- E3.6 - Generate final result tables and run-level eval index entries.

## Harness and Observability

- Tournament logs must record engine command, commit, time control, game result, termination reason, and PGN or move log.
- Standings must separate losses from crashes, timeouts, and illegal move forfeits.
- Calibration reports must use "estimated relative strength" under stated time controls, not exact Elo.

## Handoff / Next Task

Next tasks:

1. C7_UCI_COMPATIBILITY for initial real-engine smoke tournaments.
2. C8_ELO_SLIDER for calibration experiments.
3. E5_FINAL_REPORT_TEMPLATE for final reporting.

Handoff requirements:

- Final report can consume tournament standings and calibration summaries.
- Failed games are auditable from logs.

## Required Tests/Evals

- Round-robin dry run with fake or sample engines.
- Color alternation verified.
- Crash and timeout handling verified.
- Illegal move forfeit path verified.
- Result table generated.
- PGN or game log generated.
- Stockfish calibration path documented and smoke-tested when Stockfish is available.

## Required Code Review Checklist

- Are pairings deterministic and reproducible?
- Are time controls applied consistently?
- Are crashes, illegal moves, and timeouts distinguished?
- Does the runner avoid exact Elo claims without calibration evidence?
- Are logs sufficient for later audit?

## Git/PR Protocol

- Branch: `agent/E3-tournament-runner`
- Report: `/reports/tasks/E3_TOURNAMENT_RUNNER.md`
- Commit prefix: `E3:`

## Acceptance Criteria

- Generated-engine round robin can be run from documented instructions.
- Stockfish calibration protocol is documented.
- Results include standings, failures, and logs.

## Failure Conditions

- Pairings are incomplete or biased by color.
- Failures are silently dropped.
- Results cannot be reproduced from logs.

## Suggested Owner Role

Evaluation Engineer / Tournament Director.

## Dependencies

C0_ENGINE_INTERFACE, E2_UCI_COMPLIANCE.

## Priority Level

P0.
