# PyChess — pure-Python ensemble chess engine

A pure-stdlib chess engine + UCI adapter + local web UI, built end-to-end
to a binding design contract voted into existence by an ensemble of
language models. Runs on CPython 3.10+ with no third-party dependencies.

## Quick start

```bash
# UCI on stdin/stdout (default; plug into any UCI GUI):
python main.py --uci

# Local web UI at http://127.0.0.1:8080/
python main.py --ui
python main.py --ui --port 9000

# Run the test suite:
pytest
```

## Architecture

The codebase mirrors the design contract section by section.

### Board representation — `engine/board.py`, `engine/squares.py`

10x12 mailbox (a flat 120-element list framed with `OFFBOARD=7`
sentinels). Piece codes are signed ints: `1..6 = P,N,B,R,Q,K` with `+`
for white, `-` for black. The `Board` class carries `squares`,
`side_to_move`, `castling_rights` (KQkq bitmask), `ep_square`,
`halfmove_clock`, `fullmove_number`, `zobrist_key`, and `history`.
FEN round-trips exactly (`Board.from_fen` / `Board.to_fen`).

Direction tables are exposed as module constants
(`KNIGHT_OFFSETS`, `BISHOP_OFFSETS`, `ROOK_OFFSETS`, `KING_OFFSETS`).
`engine/squares.py` provides `algebraic_to_120` / `sq120_to_algebraic`
plus the `MAILBOX120` / `MAILBOX64` translation tables.

### Move generation — `engine/movegen.py`

Pseudo-legal generation followed by a make/unmake king-safety filter.
Three entry points:

- `generate_pseudo_legal(board)` — all pseudo-legal moves (castling
  appended in already-legal form).
- `generate_legal(board)` — full legal move list.
- `generate_captures(board)` — captures + promotions (pseudo-legal),
  used by quiescence.

Castling is generated directly in legal form with explicit
unattacked-transit checks. Perft tests cover the standard position
through depth 4 (`197 281`), Kiwipete through depth 3 (`97 862`),
CPW position 3 through depth 4 (`43 238`), and CPW position 4 through
depth 3 (`9 467`).

### Search — `engine/search.py`

Iterative-deepening alpha-beta negamax with:

- transposition table (`dict` keyed by Zobrist, EXACT/LOWER/UPPER
  flags, capped at 1 000 000 entries),
- quiescence search (captures + promotions, stand-pat cutoff, hard
  cap at ply 64),
- null-move pruning (R=2; skipped in check, when `depth<3`, or if the
  side to move has only king + pawns),
- killer moves (2 slots per ply) and a `[12][120]` history table
  bumped by `depth*depth` on beta cutoffs,
- move ordering: TT move → captures (MVV-LVA) → killers → history,
- check extensions and twofold-repetition / fifty-move draw detection.

`search(board, SearchLimits(max_depth, time_ms, nodes), stop_flag)`
is the public entry; time is checked every 2048 nodes.
The result includes a list of `(move, score)` for every root move
of the last completed depth, which the ELO layer samples from.

LMR / aspiration windows / futility pruning are intentionally omitted
per the contract.

### Evaluation — `engine/evaluate.py`

Tapered mid/endgame eval combining:

- material (P=100/120, N=320/330, B=330/360, R=500/550, Q=900/950),
- per-piece-type 64-entry mid/eg piece-square tables,
- mobility (N=4, B=5, R=2/4, Q=1),
- king safety (mg only): −15 per missing pawn-shield square, −20 per
  open file adjacent to the king,
- pawn structure: doubled −15, isolated −12, backward −8 (cached by
  pawn hash),
- passed-pawn rank bonuses `[0,5,10,20,35,60,100,0]` (mg) /
  `[0,10,20,35,60,100,150,0]` (eg),
- bishop pair: +30 mg / +50 eg,
- tempo: +10 mg.

Phase is computed as `min(24, 4Q + 2R + B + N)`; the final score is
`(mg·phase + eg·(24-phase)) / 24`, returned in centipawns from the
side-to-move's perspective.

### ELO scaling — `engine/strength.py`

`params_for_elo(elo)` maps `400..2400` to a `StrengthParams` tuple of
`(max_depth, time_ms, top_k, temperature, blunder_prob)` via
piecewise-linear interpolation across the contract anchors:

| ELO  | depth | time   | top_k | temp | blunder |
|------|-------|--------|-------|------|---------|
| 400  | 1     | 50 ms  | 8     | 2.0  | 0.20    |
| 800  | 2     | 100 ms | 6     | 1.2  | 0.10    |
| 1200 | 3     | 300 ms | 4     | 0.6  | 0.03    |
| 1600 | 4     | 800 ms | 3     | 0.3  | 0.0     |
| 2000 | 5     | 2000ms | 2     | 0.1  | 0.0     |
| 2400 | 7     | 5000ms | 1     | 0.0  | 0.0     |

`select_move(scored_moves, params, rng)` returns the argmax when
`top_k == 1`, otherwise softmax-samples among the top-K (logit =
`(score − best) / 100 / temperature`). With probability
`blunder_prob` it picks uniformly among the top-K, excluding moves
that drop eval by more than 300 cp vs the best move.
The RNG is seedable via the UCI `Seed` option.

### UCI — `engine/uci.py`

Implements `uci`, `isready`, `ucinewgame`, `position`, `go`,
`stop`, `quit`, and `setoption name UCI_Elo|Seed value …`.
`go` accepts `depth`, `movetime`, `wtime`/`btime`/`winc`/`binc`,
`nodes`, and `infinite`. Search runs in a worker thread; `stop`
sets a `threading.Event` checked inside the search loop.

### Engine facade — `engine/core.py`

Class `Engine` is shared by both adapters: `new_game()`,
`set_position(fen, moves)`, `go(params, on_bestmove, on_info,
sync=False)`, `stop()`, `set_elo(elo)` (`400 ≤ elo ≤ 2400`),
`set_seed(seed)`, `quit()`, plus `legal_uci_moves()`,
`fen()`, `game_status()`, and `push_uci(uci)` for the UI.

### Web UI — `ui/server.py`, `ui/static/`

`http.server.ThreadingHTTPServer` bound to `127.0.0.1`. Routes:

- `GET  /` → `static/index.html`
- `GET  /static/...` → static assets
- `GET  /state` → `{ fen, legal_moves, status, side_to_move,
  human_color, thinking, elo }`; if it is the engine's turn and no
  search is running, kicks one off
- `POST /move` `{ move }` → applies a UCI move
- `POST /new`  `{ elo, human_color }` → resets, sets ELO, picks side
- `POST /stop` → stops the running search

The page renders the board from FEN with Unicode glyphs and polls
`/state` every 300 ms while the engine is thinking. No build step,
no external JS.

## Tests

```bash
pytest
```

The suite covers FEN round-tripping, attack detection, Zobrist
incrementality, perft (initial up to depth 4; Kiwipete depth 3;
CPW positions 3 and 4), special-move generation (castling,
no-castle-through-check, promotions, en-passant), evaluation terms
in isolation, mate-in-one detection, hanging-piece avoidance,
ELO interpolation + sampling, the UCI handshake including
`go depth`, and an HTTP smoke test that drives the local UI server.

## Layout

```
engine/
  __init__.py
  board.py        # 10x12 mailbox, FEN, make/unmake, attacks, zobrist
  squares.py      # MAILBOX120/64, algebraic <-> sq120
  movegen.py      # pseudo-legal / legal / captures
  evaluate.py     # tapered eval (material, PST, mobility, ...)
  search.py       # iterative-deepening alpha-beta + TT + qsearch + ...
  strength.py     # ELO -> params, softmax/blunder move selection
  core.py         # Engine facade shared by UCI and UI
  uci.py          # UCI loop
ui/
  server.py       # http.server adapter
  static/
    index.html
    app.js
tests/
  test_board.py test_movegen.py test_eval.py test_search.py
  test_strength.py test_uci.py test_engine_core.py test_ui.py
main.py
```

## Notes & limitations

- Pure Python: ~100 k–500 k NPS, sufficient for the 400–2400 slider.
- Threefold-repetition is implemented as twofold for simplicity and
  speed (a draw claim only triggers in search; UI-side adjudication
  is left to the GUI).
- The HTTP UI is local-only (`127.0.0.1`); there is no auth and the
  server is intentionally not exposed beyond the loopback interface.
