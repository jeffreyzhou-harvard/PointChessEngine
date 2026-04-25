# Contract Tests

Frozen public-interface contract tests. **Every engine in
`arena.engines.REGISTRY` runs the same set of UCI checks**; pytest
parameterizes the suite over the registry so each test reports per
engine id (`test_x[oneshot_nocontext]`, `test_x[debate]`, ...). An
engine that fails to launch is recorded as a SKIP, not a hard
failure, so a single broken member can't take the whole suite down.

Currently 9 contract tests × 7 registered engines = 63 cases:

| file                      | what every engine must do                    |
|---------------------------|----------------------------------------------|
| `test_handshake.py`       | launch, return non-empty `id name`, complete `uci`/`uciok` and `isready`/`readyok` |
| `test_position_and_go.py` | accept startpos / startpos+moves; `go movetime` returns a python-chess-legal bestmove; three sequential `go`s don't crash |
| `test_info_lines.py`      | emit at least one `info` line carrying depth/nodes/score/time; reported scores are numeric `cp` or `mate` |
| `test_lifecycle.py`       | `ucinewgame` + new `position` + `go` works; calling it twice is idempotent |

To add a new contract test: write a `test_*` function that takes the
`uci_client` fixture (and optionally `engine_id`) - parameterization
happens automatically.

To onboard a new engine: add it to `arena.engines.REGISTRY`. Every
contract test will start running against it on the next `pytest`.

---

## Original spec (frozen interface notes)

Public interfaces are frozen unless changed through `/tasks/evals/E6_INTERFACE_CHANGE_PROTOCOL.md` if that file exists. If it does not exist, create and approve an interface-change protocol before changing shared contracts.

Agents may change internals, but candidate implementations must satisfy shared interfaces. Candidate implementations may use adapters if their internals differ.

## Promotion Gate

A candidate can only be promoted into canonical if it passes:

- interface contract tests
- current milestone tests
- previous milestone regression tests
- integration smoke tests
- code review

The canonical branch must always pass all tests up to the current milestone.

## Intended Contracts

Engine interface:

- launchable engine command
- UCI-compatible process boundary
- parseable `info` and `bestmove` output

Board interface:

- parse FEN
- serialize FEN deterministically
- expose side to move, castling, en passant, halfmove, fullmove

Move interface:

- parse UCI move strings
- serialize UCI move strings
- represent promotions

Evaluator interface:

- accept a legal position
- return deterministic numeric score
- document score perspective

Search interface:

- accept position and limits
- return legal move
- report diagnostics such as depth, nodes, time, score

UCI interface:

- support `uci`, `isready`, `ucinewgame`, `position`, `go`, `stop`, `quit`
- return `uciok`, `readyok`, and `bestmove` as required

## Candidate Promotion Checklist

- candidate branch exists
- candidate report exists
- tests run
- contract tests pass
- milestone tests pass
- previous tests pass
- no public interface changes unless approved
- code review score exists
- benchmark results exist if applicable
- AI usage/cost logged
- winner comparison report generated
