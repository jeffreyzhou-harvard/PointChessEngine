# Design contract

Voted into existence by: OpenAI, Grok, Gemini, DeepSeek, Kimi, Claude

## Topic: Board representation
_Question: Which internal board representation should the engine use - 8x8 mailbox, 0x88, or bitboards? Justify your pick under the pure-Python / no-third-party-deps constraint._

_Tally: Claude:2, OpenAI:1, DeepSeek:1, Kimi:1; winner: **Claude**_

# Proposal: 10x12 Mailbox Board Representation

**1. Recommendation.** Use a 10x12 mailbox (a flat 120-element list with sentinel "off-board" squares framing a 64-square interior).

**2. Why this fits pure Python.** Bitboards rely on fast bitwise ops over 64-bit integers; Python's arbitrary-precision ints make this dramatically slower than in C, erasing bitboards' main advantage. 0x88 saves a few bounds checks but needs nibble arithmetic that Python doesn't accelerate. A 10x12 mailbox lets move generation use simple precomputed direction offsets (e.g., knight = ±8,±12,±19,±21; bishop = ±11,±9): one integer add + one sentinel check replaces row/column math. It's the representation most Python chess tutorials use, easiest to debug (print the array), and fastest to iterate on - which matters more than micro-optimization given Python's interpreter overhead.

**3. Tradeoffs accepted.** Slower than bitboards for attack detection and pawn-structure evaluation; we'll do per-square scans instead of population counts. Memory is fine (120 ints). Magic move generation is off the table. We accept ~100k-500k NPS, sufficient for a 400-2400 ELO slider.

**4. Implementation directive.**
- File: `engine/board.py`.
- Constants: `EMPTY=0`, `OFFBOARD=7`, piece codes 1-6 with sign for color (+white, -black). Module-level `MAILBOX120` (length 120) and `MAILBOX64` (length 64) translation tables.
- Class `Board` with attributes: `squares` (list[int], length 120), `side_to_move` (±1), `castling_rights` (int bitmask, 4 bits: KQkq), `ep_square` (int 0-119 or None), `halfmove_clock` (int), `fullmove_number` (int), `zobrist_key` (int), `history` (list).
- Methods: `from_fen(fen: str) -> Board`, `to_fen() -> str`, `make_move(move) -> None`, `unmake_move() -> None`, `is_square_attacked(sq: int, by_color: int) -> bool`, `piece_at(sq: int) -> int`.
- Direction tables exposed as module constants: `KNIGHT_OFFSETS`, `BISHOP_OFFSETS`, `ROOK_OFFSETS`, `KING_OFFSETS`.
- File `engine/squares.py` provides `algebraic_to_120(s)` / `sq120_to_algebraic(i)`.

## Topic: Move generation strategy
_Question: Should move generation produce strictly-legal moves up front, or pseudo-legal moves filtered by a make-then-check-king-safety step? Consider correctness risk vs. CPU cost in pure Python._

_Tally: Claude:4, Kimi:1; winner: **Claude**_

# Proposal: Pseudo-Legal Generation with Make/Unmake Filtering

**1. Recommendation.** Generate pseudo-legal moves and filter them by making the move, testing whether the side-to-move's king is attacked, and unmaking — exposing both `generate_pseudo_legal(board)` and `generate_legal(board)` so the search can choose.

**2. Why this fits a pure-Python engine.** Strictly-legal generation requires correctly handling pins, discovered checks, en passant pin edge cases, and castling-through-check — all notoriously bug-prone. In pure Python, the dominant cost is interpreter overhead, not the king-safety check itself, so the "expensive" filter is cheap relative to the search nodes saved by avoiding bugs. Pseudo-legal + filter is the canonical approach used by most reference engines precisely because it concentrates correctness in one well-tested predicate (`is_square_attacked`) that we already need for check detection, checkmate, and stalemate.

**3. Tradeoffs accepted.** We pay a make/unmake cost per generated-but-illegal move (mostly pinned pieces). We mitigate this by (a) generating captures separately for quiescence, (b) using cheap legality shortcuts for castling (squares-attacked test, no make/unmake), and (c) keeping make/unmake incremental rather than copying the board.

**4. Implementation directive.**
- File: `movegen.py`.
- Functions: `generate_pseudo_legal(board) -> list[Move]`, `generate_legal(board) -> list[Move]`, `generate_captures(board) -> list[Move]`.
- Helper in `board.py`: `is_square_attacked(board, square, by_color) -> bool`, `make_move(board, move) -> Undo`, `unmake_move(board, undo) -> None`.
- `generate_legal` iterates pseudo-legal moves, calls `make_move`, rejects if `is_square_attacked(king_square, opponent)`, then `unmake_move`.
- Castling generated directly in legal form: verify king's start, transit, and destination squares are unattacked before emitting.
- Search (`search.py`) calls `generate_legal` at the root and inside the main loop; uses `generate_captures` + per-move legality check inside quiescence.
- Tests in `tests/test_movegen.py` include perft counts at depths 1–4 from the standard position and Kiwipete to lock in correctness.

## Topic: Search algorithm and extensions
_Question: Beyond minimax + alpha-beta, which extensions are most worth implementing in pure Python (iterative deepening, transposition table, quiescence, null-move pruning, late-move reductions, killer / history heuristics)? Pick the smallest set that meets the master brief without slowing every search to a crawl._

_Tally: Claude:2, DeepSeek:1, Kimi:1, Grok:1; winner: **Claude**_

# Search Algorithm Proposal

**1. Recommendation.** Implement iterative-deepening alpha-beta with a transposition table, quiescence search, null-move pruning, and killer + history move ordering — but skip late-move reductions.

**2. Why this fits pure Python.** Each chosen feature multiplies effective depth far more than its per-node cost. The TT eliminates re-search across iterations (essential for ID), quiescence kills horizon-effect blunders, null-move buys ~1-2 plies cheaply, and killer/history ordering is what actually makes alpha-beta cut. LMR, by contrast, demands careful re-search logic and tuning; in pure Python its bookkeeping overhead often eats the depth it saves. The chosen set is the standard "strong amateur" recipe and is well-documented.

**3. Tradeoffs accepted.** ~150-250 ELO left on the table from omitting LMR, aspiration windows, and futility pruning. We accept zugzwang risk in null-move (mitigated by disabling it in endgames). TT uses Zobrist hashing with a fixed-size dict — occasional collisions over perfect replacement schemes.

**4. Implementation directive.**
- File `search.py` exposes `search(board, limits) -> SearchResult` where `limits` carries `max_depth`, `time_ms`, `nodes`.
- Internal `negamax(board, depth, alpha, beta, ply) -> int` and `quiesce(board, alpha, beta) -> int`.
- Iterative deepening loop from depth 1 to `max_depth`, checking time after every 2048 nodes; return best move from last completed depth.
- Transposition table: `dict[zobrist_key] -> (depth, score, flag, best_move)` with `flag ∈ {EXACT, LOWER, UPPER}`; cap size at 1,000,000 entries, evict on insert when full.
- Quiescence: captures and promotions only, stand-pat cutoff, depth-unlimited but capped at ply+8.
- Null-move: `R=2`, skip if in check, if depth<3, or if side-to-move has only king+pawns.
- Killers: 2 slots per ply (array sized 64). History: `int[12][64]` indexed by piece-type and to-square, incremented by `depth*depth` on beta cutoffs.
- Move ordering priority: TT move → captures (MVV-LVA) → killers → history.

## Topic: Evaluation features
_Question: What features should the evaluation function include, and how should they be weighted? Be specific about coefficients or relative ordering for material, piece-square tables, mobility, king safety, pawn structure, bishop pair, passed pawns, center control, tempo._

_Tally: Claude:4, Kimi:1; winner: **Claude**_

## Proposal: Tapered Evaluation with Classical Features

**1. Recommendation:** Use a tapered (midgame/endgame interpolated) evaluation combining material, PSTs, mobility, king safety, pawn structure, bishop pair, passed pawns, and a small tempo bonus, returning centipawns from the side-to-move's perspective.

**2. Why this fits a pure-Python engine:** Each feature is cheap, well-understood, and incrementally testable. PSTs do most of the heavy lifting (positional placement) at near-zero cost since they're table lookups. Tapering avoids the classic bug where a king sits on e1 in the endgame. Skipping NNUE/complex king-safety tables keeps us within Python performance budgets while still reaching ~1800-class play.

**3. Tradeoffs accepted:** No king-attacker tables, no mobility-area refinements, no complex pawn-shelter scoring. We accept ~100-200 Elo left on the table in exchange for code that is fast in Python and easy to debug.

**4. Implementation directive** (`evaluate.py`, function `evaluate(board) -> int`):

- **Material (mg/eg):** P=100/120, N=320/330, B=330/360, R=500/550, Q=900/950, K=0.
- **PSTs:** 64-entry mg and eg tables per piece type (standard Chess Programming Wiki values, scaled to ±50). Mirror for Black.
- **Tapering:** phase = min(24, 4·Q + 2·R + 1·(B+N)); `score = (mg·phase + eg·(24-phase)) / 24`.
- **Mobility:** count pseudo-legal moves per piece; weight N=4, B=5, R=2(mg)/4(eg), Q=1.
- **King safety (mg only):** −15 per missing pawn shield square in front of king; −20 per open file adjacent to king.
- **Pawn structure:** doubled −15, isolated −12, backward −8.
- **Passed pawns:** rank-indexed bonus [0,5,10,20,35,60,100,0] (mg), [0,10,20,35,60,100,150,0] (eg).
- **Bishop pair:** +30 mg, +50 eg.
- **Tempo:** +10 for side to move (mg only).

Cache pawn-structure scores by pawn-hash. Unit-test each term in isolation in `tests/test_eval.py`.

## Topic: ELO scaling mechanism
_Question: How should the 400-2400 ELO slider map onto engine behaviour? Cover: depth scaling, time-per-move scaling, evaluation noise, top-K candidate sampling, and how to keep weak play believable rather than embarrassingly random._

_Tally: Claude:4, Kimi:1; winner: **Claude**_

# ELO Scaling Proposal

**1. Recommendation:** Map ELO to a tuple of (max_depth, time_budget, softmax_temperature, blunder_probability), where high ELO uses deep+greedy search and low ELO uses shallow search with weighted sampling over top-K moves plus occasional deliberate blunders.

**2. Why this fits pure Python:** A pure-Python search is slow, so we cannot rely on raw depth alone to span 2000 ELO points. Combining depth/time scaling (for the upper half) with move-selection stochasticity (for the lower half) gives a wide, smooth strength curve cheaply. Sampling from top-K via softmax keeps weak play *plausible* — the engine still picks reasonable-looking moves, just not the best one — while a small blunder probability injects the occasional human-like mistake without producing nonsense like hanging the queen on move 3.

**3. Tradeoffs accepted:** Strength is approximate, not calibrated to FIDE ratings. The same ELO may play 50–100 points differently across hardware. Stochastic play means the engine is non-deterministic at low settings (mitigated by a seedable RNG).

**4. Implementation directive:**
- File: `strength.py`
- Function: `params_for_elo(elo: int) -> StrengthParams` returning `(max_depth, time_ms, top_k, temperature, blunder_prob)`.
- Piecewise-linear interpolation across anchors:
  - 400: depth=1, time=50ms, top_k=8, temp=2.0, blunder=0.20
  - 800: depth=2, time=100ms, top_k=6, temp=1.2, blunder=0.10
  - 1200: depth=3, time=300ms, top_k=4, temp=0.6, blunder=0.03
  - 1600: depth=4, time=800ms, top_k=3, temp=0.3, blunder=0.0
  - 2000: depth=5, time=2000ms, top_k=2, temp=0.1, blunder=0.0
  - 2400: depth=7, time=5000ms, top_k=1, temp=0.0, blunder=0.0
- Function: `select_move(scored_moves, params, rng)` — if `top_k==1`, return argmax; else softmax-sample over top_k by score/temperature.
- Blunder: with `blunder_prob`, pick uniformly from top_k (excluding clearly losing moves: those dropping eval by >300cp vs best).
- RNG seeded via UCI option `Seed` (default: time-based).

## Topic: UCI + UI architecture
_Question: How should UCI and the human-playable UI be structured? Should the UI be a stdlib http.server + vanilla JS page or something richer? How are search threads, stop signals, and shared engine state managed across the two interfaces?_

_Tally: Claude:4, Kimi:1; winner: **Claude**_

# Proposal: UCI + UI Architecture

**1. Recommendation.** Build a UCI-first engine core, expose UCI over stdin/stdout in the standard way, and ship a thin `http.server`-based local web UI (vanilla HTML/JS, no build step) that talks to the same engine core via an in-process adapter — not by launching a UCI subprocess.

**2. Why this fits a pure-Python engine.** `http.server` and `threading` are stdlib, so no extras. A single `Engine` object shared by both front-ends keeps search/stop/state logic in one place; the UCI loop and the HTTP handler are just two adapters. Vanilla JS + a board rendered from FEN avoids any toolchain. A local-only HTTP server is the simplest cross-platform GUI Python offers without Tk quirks.

**3. Tradeoffs accepted.** No fancy board animations or analysis arrows; one user at a time; the HTTP server is bound to `127.0.0.1` only (no auth, no remote play); `http.server` is not high-performance, but moves are infrequent so it's fine.

**4. Implementation directive.**
- `engine/core.py`: class `Engine` with `new_game()`, `set_position(fen, moves)`, `go(params) -> bestmove` (runs in a worker thread, returns immediately; emits info via callback), `stop()`, `set_elo(elo: int)` where `400 <= elo <= 2400`, `quit()`. Internal `threading.Event` named `_stop_flag` checked in search.
- `engine/uci.py`: `run_uci(stream_in=sys.stdin, stream_out=sys.stdout)`; parses `uci`, `isready`, `ucinewgame`, `position`, `go`, `stop`, `quit`, `setoption name UCI_Elo value N`.
- `ui/server.py`: `serve(host="127.0.0.1", port=8080, engine=None)`; routes `GET /` (static HTML), `GET /state` (FEN + legal moves + game status JSON), `POST /move` (`{from,to,promotion}`), `POST /new` (`{elo, human_color}`), `POST /stop`.
- `ui/static/index.html` + `app.js`: poll `/state` every 300ms during engine turn.
- Entry point `main.py` with flags `--uci` (default) and `--ui [--port N]`.
