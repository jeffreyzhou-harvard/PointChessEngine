# Champion Methodology Audit Prompt

Candidate: `C0_custom_parallel`

Task: `C0_ENGINE_INTERFACE`

Orchestration type: `custom_langchain_parallel`

## Task Spec

# C0 - UCI Engine Contract and Benchmark Harness

## Objective

Define the UCI-first external contract every generated engine must satisfy, plus the benchmark harness behavior used to launch, drive, observe, and validate engines.

## Why This Matters

We are comparing AI workflows. To compare them fairly, every generated engine must expose the same tournament-facing protocol even if its internal architecture is completely different.

The benchmark contract is UCI, not a required in-process Python API. Later tasks may create internal interfaces as needed, but all final evaluation, tournament play, and calibration must operate through the UCI process boundary.

## Deliverables

- UCI engine launch contract.
- Required UCI command subset.
- Engine registry/manifest schema.
- UCI transcript runner or harness specification.
- Standard parsed result envelope.
- Minimal fake UCI engine for testing the harness.
- Timeout, crash, and malformed-output handling.
- Observability/logging format for all engine runs.
- Documentation explaining how future engines plug into the harness.

Required UCI command support for benchmark engines:

```text
uci
isready
ucinewgame
position startpos [moves ...]
position fen <fen> [moves ...]
go depth <n>
go movetime <ms>
stop
quit
```

Recommended UCI diagnostics:

```text
info depth 3 score cp 31 nodes 12345 time 100 pv e2e4 e7e5
bestmove e2e4
```

Harness result envelope:

```json
{
  "engine_id": "example-engine",
  "command": ["python", "-m", "engine.uci"],
  "git_commit": "unknown",
  "position": "startpos",
  "moves": [],
  "limits": {"depth": 3, "movetime_ms": null},
  "bestmove": "e2e4",
  "ponder": null,
  "info": [
    {"depth": 3, "score_cp": 31, "nodes": 12345, "time_ms": 100, "pv": ["e2e4", "e7e5"]}
  ],
  "timings": {"startup_ms": 25, "ready_ms": 3, "go_ms": 101},
  "exit_status": "ok",
  "stdout_log": "path/to/stdout.log",
  "stderr_log": "path/to/stderr.log"
}
```

The fake UCI engine may return a fixed legal-looking move for harness tests, but it must be marked as fake and excluded from strength tournaments.

## Work Packages

- C0.1 - Define the UCI process contract: launch command, working directory, environment, startup timeout, command timeout, and shutdown behavior.
- C0.2 - Define the engine registry/manifest schema: engine ID, command, working directory, supported options, author/agent metadata, and notes.
- C0.3 - Define or implement the transcript harness behavior: send UCI commands, capture stdout/stderr, parse `info` and `bestmove`, and preserve raw logs.
- C0.4 - Define malformed-output handling: missing `uciok`, missing `readyok`, invalid `bestmove`, crash, timeout, and nonzero exit.
- C0.5 - Define observability artifacts: per-run transcript, parsed JSON/structured result, timing summary, and report links.
- C0.6 - Add a fake UCI engine or fake-engine spec that E1/E2/E3 can use before a real engine exists.

## Harness and Observability

- Every harness invocation must record engine ID, command, commit if available, position, limits, stdout/stderr logs, parsed result, and timing.
- Harness logs should be referenced from `reports/evals/` or `reports/runs/<RUN_ID>/eval_index.md`.
- The harness must distinguish invalid protocol, illegal move, crash, timeout, and normal loss.
- Later eval tasks should consume this contract rather than inventing separate engine interfaces.

## Handoff / Next Task

After C0, run these tasks next:

1. E2_UCI_COMPLIANCE to codify protocol transcript tests.
2. E1_PERFT_SUITE to define legality gates.
3. E3_TOURNAMENT_RUNNER to consume the same engine registry.
4. C1_BOARD_FEN_MOVE to begin the internal engine implementation.

## Pre-Commit Tests by Work Package

Before each `C0.*` commit, run the targeted tests for that work package and record the exact command/output summary in the commit body.

- C0.1 - Launch-contract tests: fake command starts, startup timeout is enforced, shutdown path exits cleanly.
- C0.2 - Registry schema tests: valid registry loads, missing command fails, fake engine is marked non-tournament.
- C0.3 - Transcript harness tests: sends `uci`, `isready`, `position`, and `go`; captures stdout/stderr.
- C0.4 - Malformed-output tests: missing `uciok`, missing `readyok`, invalid `bestmove`, crash, and hang are distinct failures.
- C0.5 - Observability tests: result envelope includes engine ID, command, limits, timing, logs, parsed `info`, and `bestmove`.
- C0.6 - Fake UCI engine tests: fake engine passes C0 harness but is excluded from strength tournaments.

## Required Tests/Evals

- Fake UCI engine responds to `uci` with `uciok`.
- Fake UCI engine responds to `isready` with `readyok`.
- Harness can send `position startpos` and `go depth 1`.
- Harness parses `bestmove e2e4`.
- Harness parses at least one standard `info` line.
- Harness rejects malformed `bestmove` output.
- Harness times out a hung fake engine.
- Harness logs raw transcript and parsed diagnostics.
- Interface documentation exists and says UCI is the external contract.

## Required Code Review Checklist

- Is the contract UCI-first rather than tied to one implementation language?
- Is the supported UCI subset sufficient for E1/E2/E3/C7?
- Are diagnostics standardized through parseable UCI `info` lines and harness metadata?
- Can neural and non-neural engines both use it as external processes?
- Are errors handled cleanly?
- Are fake engines clearly excluded from final tournaments?

## Git/PR Protocol

- Branch: `agent/C0-engine-interface`
- Report: `/reports/tasks/C0_ENGINE_INTERFACE.md`
- Commit prefix: `C0:`

## Acceptance Criteria

- Tests pass.
- At least one fake UCI engine passes through the harness.
- Documentation explains how future engines should implement UCI mode.
- E1, E2, E3, and C7 can all build against the same external contract.

## Failure Conditions

- Contract is tied to one programming language or in-process API.
- No fake UCI engine or fake-engine spec exists.
- No UCI transcripts or diagnostics are logged.
- Harness cannot distinguish crash, timeout, malformed output, and normal result.
- Future tasks cannot build against the interface.

## Suggested Owner Role

Architect / Integrator.

## Dependencies

None.

## Priority Level

P0.


## Required Orchestration Evidence

- implementation plan

- files allowed to change

- tests/evals to run

- interface risks

- expected report fields

- cost/time logging plan