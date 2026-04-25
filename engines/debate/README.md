# CouncilEngine

A pure-Python chess engine built end-to-end from the binding design contract
agreed by the architecture council (lead architect: Claude; advisors: OpenAI,
Grok, Gemini, DeepSeek, Kimi). Stdlib-only; no third-party dependencies.

## Quick start

    # Run as a UCI engine (default).
    python main.py

    # Or run the playable web UI.
    python main.py --ui --port 8080
    # then open http://127.0.0.1:8080/

    # Or run both at once.
    python main.py --both --port 8080

    # Tests
    python -m pytest -q

## Architecture

### Board representation (`engine/board.py`)

8x8 mailbox in a flat 64-element list. `index = rank * 8 + file`, so
`a1 = 0`, `h1 = 7`, `a8 = 56`, `h8 = 63`. Pieces are encoded as integers
where `EMPTY=0`, white pieces are 1..6, black pieces are 9..14; color =
`piece & 8`, type = `piece & 7`. This single-dereference layout matches the
one performance advantage 0x88 had while keeping `sq // 8` / `sq % 8`
rank/file math trivial — exactly the trade the contract calls for.

State on `Board`: `squares`, `side_to_move`, `castling_rights` (4-bit:
WK=1, WQ=2, BK=4, BQ=8), `ep_square` (-1 if none), `halfmove_clock`,
`fullmove_number`, `zobrist_key`, and an `history` undo stack used for
incremental `unmake_move`.

### Move generation (`engine/movegen.py`)

Pseudo-legal generation, filtered for legality via make / king-attack-check /
unmake. The single authoritative attack oracle is
`is_square_attacked(board, square, by_color)`. Per the contract:

- No 0x88 checks. No per-step bounds checks in hot paths.
- Precomputed at import time: `KNIGHT_TARGETS`, `KING_TARGETS`, `RAYS`
  (8 directions × 64 squares), `PAWN_ATTACKS`, pawn-push tables.
- Castling is the only piece with a pre-filter: cannot castle out of,
  through, or into check.
- En passant uses no special discovered-check logic; the post-move attack
  test on the king covers it (and is unit-tested).

The contract's explicit perft obligations are enforced in `tests/test_rules.py`:

| Position | Depth | Expected | Status |
|---|---|---|---|
| Starting position | 1, 2, 3, 4 | 20, 400, 8902, 197281 | ✅ |
| Kiwipete | 1, 2 | 48, 2039 | ✅ |
| Position 3 (EP / pinning endgame) | 1, 2, 3 | 14, 191, 2812 | ✅ |
| Position 4 | 1, 2 | 6, 264 | ✅ |

### Evaluation (`engine/evaluate.py`, exported also as `engine/eval.py`)

Tapered evaluation in centipawns from side-to-move's perspective.

- **Material**: P=100, N=320, B=330, R=500, Q=900.
- **Tapered PSTs**: `PST_MG[piece]` and `PST_EG[piece]`. King MG favours
  castled corners; king EG favours the centre. Black squares mirror via
  `sq ^ 56`.
- **Phase**: 0..24 from non-pawn material (N=1, B=1, R=2, Q=4 per side).
  `score = (mg*phase + eg*(24-phase)) // 24`.
- **Mobility**: quiet target counts. N=4, B=5, R=2 MG / 4 EG, Q=1 cp/move.
- **King safety (MG, scaled by phase/24)**: pawn shield, open/semi-open
  king-file penalty, attacker-count penalties (-20/-50/-90/-140).
- **Pawn structure**: doubled (-15 MG / -25 EG), isolated (-15 / -20),
  backward (-10 both).
- **Passed pawns** (white POV; mirrored for black): rank-scaled +10/17/25/40/70/120,
  endgame ×1.5.
- **Bishop pair**: +30 MG / +50 EG.
- **Excluded**: explicit centre control and tempo (per contract).
- **Lazy evaluation**: cheap material+PST first; full eval only when the
  lazy score is within `LAZY_MARGIN = 200` of the alpha-beta window.

### Search (`engine/search.py`)

Alpha-beta within iterative deepening, plus quiescence, transposition
table, killers, and history. Per the contract, **no null-move and no LMR**.

- `iterative_deepening(board, time_limit_ms, max_depth, stop_event, ...)`:
  loops depth = 1..max_depth with full window, returns the best move from
  the last *completed* depth on stop or timeout.
- `alphabeta(...)`: fail-hard, TT probe with EXACT/LOWER/UPPER flags,
  one-ply check extension capped at 2 per branch, killer + history update
  on quiet beta cutoffs.
- `quiescence(...)`: stand-pat from eval; captures + promotions only;
  delta pruning at `stand_pat + captured_value + 200 < alpha`.
- Move ordering: TT move → MVV-LVA captures/promos → killers → history → rest.
- Time check every 2048 nodes; respects `stop_event: threading.Event`.

### Transposition table (`engine/tt.py`, `engine/zobrist.py`)

- 64-bit Zobrist keys seeded with `random.Random(0xC0FFEE)`. Tables cover
  piece × square (raw piece int 0..14), side-to-move, all 16 castling-rights
  combos, and en-passant file (8).
- `TranspositionTable`: dict-backed, capped at `2^20 = 1,048,576` entries,
  replace-always policy. Stores `(key, depth, value, flag, best_move)`.
- Cleared on `ucinewgame`.

### ELO scaling (`engine/strength.py`)

`configure(elo: int, limit_strength: bool = True) -> StrengthConfig`. ELO is
clamped to [400, 2400]. `t = (elo - 400) / 2000`. Parameters interpolate
exactly per the contract:

| Parameter | At 400 | At 2400 | Curve |
|---|---|---|---|
| `max_depth` | 1 | 10 | linear, round |
| `soft_time_ms` | 100 | 3000 | linear |
| `hard_time_ms` | 300 | 5000 | linear |
| `eval_noise_cp` | 75 | 0 | linear |
| `top_k` | 4 | 1 | linear, round, floor 1 |
| `softmax_temp_cp` | 80 | 1 | exponential `80 * (1/80)**t` |
| `blunder_margin_cp` | 700 | 300 | `300 + 400*(1-t)` |

Root selection:

1. Search at `max_depth` with `random.gauss(0, eval_noise_cp)` added to leaf eval.
2. Take top `top_k` candidates by score.
3. Softmax-sample one, weights `exp(score / softmax_temp_cp)`.
4. **Hard guardrails**: forced mates are played unconditionally; any
   candidate worse than best by more than `blunder_margin_cp` is dropped.
5. `top_k == 1` (or `limit_strength=False`) → deterministic best move.

UCI options: `UCI_Elo` (spin, 400..2400) and `UCI_LimitStrength` (check).

### EngineCore + threading model (`engine/core.py`)

Singleton `EngineCore` owns the board, search thread, TT, and a
`_snapshot: dict` (FEN, turn, legal moves, last bestmove, search status,
depth, score_cp, PV, ELO, in_check, game_over, result) guarded by a single
`RLock`. All mutation flows through `cmd_queue: queue.Queue`. Reads flow
through `snapshot()` which returns a deep copy.

Commands (dataclasses): `CmdNewGame`, `CmdPosition`, `CmdGo`, `CmdStop`,
`CmdQuit`, `CmdSetElo`, `CmdSetLimitStrength`, `CmdMakeUserMove`,
`CmdSetSeed`. Exactly one consumer thread drains `cmd_queue` (the one
returned by `run_forever`); searches run on a *separate* worker thread
spawned per `CmdGo`. `CmdStop` sets `stop_event` and joins.

### UCI adapter (`engine/uci.py`)

Stdin reader / stdout writer. Line-buffered output via
`out.reconfigure(line_buffering=True)`. Implements `uci`, `isready`,
`ucinewgame`, `position [startpos|fen ...] [moves ...]`, `go [...]`, `stop`,
`quit`, `setoption name UCI_Elo|UCI_LimitStrength value ...`. The adapter
hooks `_info_writer` and `_bestmove_writer` on the core, so search progress
is emitted as `info depth ... score cp ... nodes ... nps ... time ... pv ...`
and `bestmove ...`.

### HTTP UI (`ui/`)

`ui/server.py` exposes `UIServer`, a `ThreadingHTTPServer` with handlers
for `/`, `/static/...`, and a JSON API:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/state`     | GET  | snapshot |
| `/api/newgame`   | POST | new game |
| `/api/position`  | POST | set fen + moves |
| `/api/move`      | POST | apply human UCI move |
| `/api/go`        | POST | trigger engine search (`movetime`/`depth`) |
| `/api/stop`      | POST | stop search |
| `/api/elo`       | POST | set `elo`, `limit` |

The HTTP handler thread enqueues commands and reads results via
`core.snapshot()` (no blocking on the queue). The frontend in
`ui/static/{index.html,board.js,board.css}` is vanilla JS, no frameworks.
Click a piece to see legal targets; click a target to move; the engine
replies automatically and the board polls `/api/state` at 400 ms.

## Tests

47 tests across `tests/test_rules.py` (perft + rules), `test_eval.py`
(material / bishop pair / passed pawn / symmetry), `test_search.py` (mate-in-1,
no-blunder, stop event, strength sampling), `test_strength.py` (ELO endpoint
exactness), `test_core.py` (core lifecycle + game-over detection),
`test_uci.py` (parsers + full-loop bestmove), `test_ui_server.py` (HTTP smoke
test against a live server on a random port).

    $ python -m pytest -q
    47 passed
