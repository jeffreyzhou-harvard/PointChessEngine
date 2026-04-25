# C7 - Production UCI Compatibility

## Objective

Implement production UCI engine mode for the real engine, satisfying the C0 UCI contract and E2 compliance suite.

## Why This Matters

UCI lets the engine run in tournament tools, external chess GUIs, Stockfish calibration matches, and generated-engine round robins. C0 defines the external contract; C7 connects the actual engine to it.

## Deliverables

Support:

- `uci`
- `isready`
- `ucinewgame`
- `position`
- `go`
- `stop`
- `quit`

Optional:

- `setoption name Skill value <n>`
- `setoption name UCI_Elo value <n>`

## Work Packages

- C7.1 - Implement UCI process entrypoint and startup banner.
- C7.2 - Implement command parser for `uci`, `isready`, `ucinewgame`, `position`, `go`, `stop`, and `quit`.
- C7.3 - Connect `position` to C1/C2 state loading and move application.
- C7.4 - Connect `go depth` to C4/C5 fixed-depth search.
- C7.5 - Connect `go movetime` and `stop` to C6 timed search when available.
- C7.6 - Emit standard `info` diagnostics and final `bestmove`.
- C7.7 - Add transcript tests and FastChess smoke instructions.

## Harness and Observability

- UCI transcript tests must save raw stdin/stdout/stderr logs.
- Every `go` response should include parseable `bestmove`; diagnostics should prefer standard `info` fields.
- Invalid commands must be logged and ignored or reported without crashing.
- E2 compliance output should be linked from the task report.

## Handoff / Next Task

Next tasks:

1. E3_TOURNAMENT_RUNNER smoke run with the real engine.
2. C8_ELO_SLIDER for optional strength controls.
3. C5/C6 if tactical or timed features are not yet complete.

Handoff requirements:

- Tournament runner can launch the engine command from the registry.
- E2 passes against the real engine, not only the fake C0 engine.
- UCI output includes enough diagnostics for eval dashboards.

## Pre-Commit Tests by Work Package

Before each `C7.*` commit, run the targeted tests for that work package and record the exact command/output summary in the commit body.

- C7.1 - Process startup test: engine launches, prints valid `id`/`option` lines as appropriate, and exits on `quit`.
- C7.2 - Parser unit tests for `uci`, `isready`, `ucinewgame`, `position`, `go`, `stop`, `quit`, and unknown commands.
- C7.3 - Position transcript tests for `startpos`, `startpos moves ...`, FEN, and invalid position input.
- C7.4 - `go depth` transcript tests returning legal `bestmove` and standard `info` when available.
- C7.5 - `go movetime` and `stop` transcript tests with timeout tolerance and best-so-far behavior when C6 exists.
- C7.6 - Output-format tests for parseable `info` lines, final `bestmove`, no extra blocking prompts, and stderr logging.
- C7.7 - Full E2 UCI compliance suite, C2 legality gate, and FastChess smoke if installed.

## Required Tests/Evals

- `uci` returns `uciok`.
- `isready` returns `readyok`.
- `position startpos moves e2e4` loads correctly.
- `position fen ...` loads correctly.
- `go depth 3` returns `bestmove`.
- `go movetime 100` returns `bestmove`.
- `quit` exits cleanly.
- Invalid command does not crash process.
- FastChess smoke test works if FastChess is installed.

## Required Code Review Checklist

- Is UCI separate from engine core?
- Is command parsing robust?
- Are time controls passed correctly?
- Does the process exit cleanly?
- Are errors handled gracefully?

## Git/PR Protocol

- Branch: `agent/C7-uci-compatibility`
- Report: `/reports/tasks/C7_UCI_COMPATIBILITY.md`
- Commit prefix: `C7:`

## Acceptance Criteria

- UCI transcript tests pass.
- Engine runs in tournament harness.

## Failure Conditions

- Engine cannot be launched as UCI.
- `go` hangs.
- Position parsing is wrong.

## Suggested Owner Role

UCI Engineer.

## Dependencies

C0_ENGINE_INTERFACE, C4_ALPHA_BETA_SEARCH, preferably C6_TIME_TT_ITERATIVE.

## Priority Level

P2.
