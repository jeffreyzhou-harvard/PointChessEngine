# E2 - UCI Compliance Suite

## Objective

Define the protocol tests every tournament engine must pass.

## Why This Matters

UCI compliance lets engines run in tournament managers, external GUIs, and calibration harnesses without custom integration work.

## Deliverables

- UCI transcript test harness.
- Command timeout handling.
- Process startup/shutdown checks.
- Structured pass/fail report.
- Documentation for adding protocol cases.

## Work Packages

- E2.1 - Define transcript runner using the C0 engine registry.
- E2.2 - Add startup and readiness tests.
- E2.3 - Add position-loading tests for `startpos`, move lists, and FEN.
- E2.4 - Add `go depth`, `go movetime`, `stop`, and `quit` tests.
- E2.5 - Add malformed or unknown command resilience tests.
- E2.6 - Define compliance report and raw transcript artifact layout.

## Harness and Observability

- Every transcript test must save raw stdin/stdout/stderr and parsed pass/fail status.
- Hangs, crashes, bad `bestmove`, and missing protocol tokens must be separate failure types.
- Reports should be consumable by E3 before admitting an engine to tournaments.

## Handoff / Next Task

Next tasks:

1. C7_UCI_COMPATIBILITY for real engine protocol implementation.
2. E3_TOURNAMENT_RUNNER for tournament admission checks.

Handoff requirements:

- C7 has clear transcript tests to pass.
- E3 can run only engines with passing E2 status.

## Required Tests/Evals

Required command tests:

- `uci` -> `uciok`
- `isready` -> `readyok`
- `ucinewgame`
- `position startpos`
- `position startpos moves e2e4 e7e5`
- `position fen <fen>`
- `go depth 1`
- `go movetime 100`
- `stop`
- `quit`

## Required Code Review Checklist

- Are subprocess timeouts enforced?
- Are stdout/stderr logs captured?
- Does the suite tolerate harmless informational UCI output?
- Are hangs and crashes reported clearly?
- Can it run against multiple generated engines?

## Git/PR Protocol

- Branch: `agent/E2-uci-compliance`
- Report: `/reports/tasks/E2_UCI_COMPLIANCE.md`
- Commit prefix: `E2:`

## Acceptance Criteria

- Engine process starts.
- Engine responds correctly.
- Engine does not hang.
- Engine returns `bestmove` for `go` commands.

## Failure Conditions

- A hung engine can stall the suite indefinitely.
- Required UCI commands are untested.
- The suite accepts malformed `bestmove` output.

## Suggested Owner Role

Evaluation Engineer / UCI Engineer.

## Dependencies

C0_ENGINE_INTERFACE.

## Priority Level

P0.
