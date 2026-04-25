# Design contract

Lead architect: **Claude**
Advisors: OpenAI, Grok, Gemini, DeepSeek, Kimi

## Topic: Board representation

_Which internal board representation should the engine use - 8x8 mailbox, 0x88, or bitboards? Justify your pick under the pure-Python / no-third-party-deps constraint._

## Decision
The engine will use an **8x8 mailbox** representation, implemented as a flat 64-element list indexed 0..63 (a1=0 ... h8=63), with sentinel-aware move generation via precomputed offset tables.

## Reasoning
OpenAI and DeepSeek both made strong cases for 0x88, and DeepSeek's point about branchless `square & 0x88` validity checks is genuinely correct *in C*. But both advisors underweight the decisive fact: in pure Python, the cost of a single bytecode operation (LOAD_FAST, BINARY_AND, POP_JUMP) dwarfs the difference between `sq & 0x88` and `0 <= r < 8 and 0 <= f < 8`. The "branchless" win evaporates in the interpreter. DeepSeek's own concession - that 0x88 complicates piece-square table indexing and rank/file mapping - is exactly the daily friction we'd pay for a phantom speedup.

Grok's proposal influenced the final call most directly: clarity, debuggability, and direct rank/file arithmetic matter enormously when we also need to implement castling rights, en passant, pinned-piece detection, threefold repetition, and a PST-based evaluator. I'm overriding the 2-vote majority for 0x88 because the majority's performance argument doesn't survive contact with CPython's execution model, and the maintainability cost is real and recurring.

I am, however, rejecting Grok's specific 2D list-of-lists suggestion. A **flat 64-element list** gives single-dereference access (matching 0x88's one advantage) while preserving trivial `sq // 8`, `sq % 8` rank/file math. Off-board detection uses precomputed per-square offset tables for knights/kings and precomputed rays for sliders - this is faster in Python than either repeated bounds checks *or* 0x88 masking, because the table itself encodes legality.

## Implementation directive

**Module:** `engine/board.py`

**Core representation:**
- `Board.squares: list[int]` of length 64. Index 0 = a1, 7 = h1, 56 = a8, 63 = h8 (i.e., `sq = rank * 8 + file`).
- Piece encoding: integers. `EMPTY = 0`. White pieces = 1..6 (P,N,B,R,Q,K). Black pieces = 9..14 (P,N,B,R,Q,K). Color bit = `piece & 8`. Type = `piece & 7`. This keeps color/type checks to a single bitwise op.
- Helpers: `sq(file, rank) -> int`, `file_of(sq)`, `rank_of(sq)`, `mirror(sq)` for PST.

**Board state fields (all on `Board`):**
- `squares`, `side_to_move` (0=white, 1=black), `castling_rights` (4-bit int: WK=1,WQ=2,BK=4,BQ=8), `ep_square` (int or -1), `halfmove_clock`, `fullmove_number`, `zobrist_key`, `history: list` (for undo + repetition).

**Move generation:** `engine/movegen.py`
- Precompute at import time:
  - `KNIGHT_TARGETS: list[list[int]]` — for each of 64 squares, the list of legal destination squares (off-board pruned).
  - `KING_TARGETS: list[list[int]]` — same for king.
  - `RAYS: dict[direction, list[list[int]]]` — for each of 8 directions and each square, the list of squares along that ray until edge. Used for bishop/rook/queen.
  - `PAWN_ATTACKS[color][sq]: list[int]`.
- No `& 0x88` checks anywhere. No per-step `0 <= r < 8` checks in hot paths — legality is baked into the precomputed tables.

**Move object:** namedtuple or small class `Move(from_sq, to_sq, promo, flags)` where `flags` encodes capture/ep/castle/double-push.

**Make/unmake:** `Board.make_move(move)` and `Board.unmake_move()` using a history stack of `(captured_piece, prev_castling, prev_

## Topic: Move generation strategy

_Should move generation produce strictly-legal moves up front, or pseudo-legal moves filtered by a make-then-check-king-safety step? Consider correctness risk vs. CPU cost in pure Python._

## Decision
Move generation will produce **pseudo-legal moves**, filtered for legality via a make-move / king-safety-check / unmake-move pipeline. A single shared `is_square_attacked(square, by_color)` routine is the authoritative legality oracle.

## Reasoning
All three responding advisors (OpenAI, DeepSeek, Grok) converged on pseudo-legal generation, and the consensus is correct for a pure-Python engine: pin tables and discovered-check logic require ray-walking loops that are punishingly slow under the CPython interpreter, while a single attack-detection function is both faster in practice and dramatically easier to test.

DeepSeek's framing was the most rigorous — specifically the point that the post-move legality check collapses to an O(1)-style `is_square_attacked` call on the king square, and that maintaining pin tables is the real cost being avoided. That insight shapes the implementation directive. OpenAI's emphasis on isolating legality filtering as a distinct, separately-testable stage is also adopted; it directly reduces correctness risk on castling-through-check and en passant discovered checks, which are the historically buggy cases.

I am overriding Grok's "10–20% illegal moves" figure (DeepSeek correctly flagged it as inflated) and rejecting all hybrid/selective-strict schemes — they add branches for negligible gain. I am also rejecting bitboard pin detection outright for this engine, per DeepSeek's correct observation that Python big-int bit ops are not a win here.

One concession adopted from Grok/DeepSeek: when the side to move is **in check**, the filter rejection rate spikes, so the make/unmake path must be cheap enough that even check-evasion positions are tolerable. This is a performance constraint on the make/unmake implementation, not a license to add a special-case generator.

## Implementation directive

**Module:** `movegen.py`

**Required functions:**
- `generate_pseudo_legal_moves(board, color) -> list[Move]` — enumerates all moves obeying piece movement rules, including castling candidates, en passant candidates, and all four promotion choices. Does NOT consider whether the move leaves own king in check. Does NOT consider whether castling passes through attacked squares (that is handled in the legality filter, see below).
- `generate_legal_moves(board, color) -> list[Move]` — calls `generate_pseudo_legal_moves`, then for each move: `board.make_move(m)`, test legality, `board.unmake_move(m)`; yields only legal moves. This is the function the search and UCI layers call.
- `is_square_attacked(board, square, by_color) -> bool` — single authoritative attack oracle. Used by legality filter, check detection, castling legality, and king-safety eval. Must be implemented once and reused everywhere.

**Legality filter rules inside `generate_legal_moves`:**
1. After `make_move`, reject if `is_square_attacked(board, own_king_square, opponent_color)` is true.
2. For castling moves specifically, additionally reject if any of the king's transit squares (origin, intermediate, destination) is attacked **before** make_move, or if the king is currently in check. This is the only piece-specific pre-filter permitted.
3. En passant is handled via the standard make/unmake path — no special discovered-check logic; the post-move attack test on the king covers it.

**Make/unmake contract (`board.py`):**
- `make_move(move)` must push an undo record (captured piece, castling rights, en passant square, halfmove clock, zobrist key delta) onto an internal stack.
- `unmake_move(move)` must restore exactly. No full board copying — incremental update only. This is mandatory; the filter approach depends on cheap make/unmake.

**Forbidden in this engine:**
- Precomputed pin tables or absolute-pin detection during generation.
- Bitboard-based attack generation using Python ints.
- Any "strict-legal" or hybrid generator that duplicates legality logic outside `generate_legal_moves`.

**Test obligations (`tests/test_movegen.py`):**
- Perft tests at depths 1–4 from the standard position and from "Kiwipete" (Position

## Topic: Search algorithm and extensions

_Beyond minimax + alpha-beta, which extensions are most worth implementing in pure Python (iterative deepening, transposition table, quiescence, null-move pruning, late-move reductions, killer / history heuristics)? Pick the smallest set that meets the master brief without slowing every search to a crawl._

## Decision
Adopt alpha-beta within iterative deepening, plus quiescence search, a Zobrist-keyed transposition table, and **both killer and history heuristics** for move ordering. Defer null-move pruning and late-move reductions.

## Reasoning
DeepSeek's argument is decisive on the move-ordering question: in pure Python, where nodes/sec is the binding constraint, alpha-beta's effectiveness collapses without good ordering, and killers + history are ~40 lines of code with negligible runtime cost and no correctness risk. OpenAI's "clarity" objection conflates ordering heuristics (safe, local, easily unit-tested) with pruning heuristics (which change tree semantics and can hide bugs) — that conflation is the flaw I'm overriding the OpenAI position on.

Grok's compromise (killers yes, history no) is a false economy as DeepSeek correctly identified: history is a 64×64 int table updated on beta cutoffs, and it orders the quiet moves that killers miss. The marginal cost is trivial; the marginal ELO is real.

I follow the consensus on rejecting null-move and LMR for v1: both interact badly with an untuned evaluation and a slow interpreter, and zugzwang/verification logic is exactly the kind of subtle bug we cannot afford on a pure-Python timeline. Grok's concession on Zobrist hashing is adopted — it is non-negotiable for TT correctness.

Quiescence is captures + promotions only (per DeepSeek); adding check evasions explodes the q-search tree in Python. Iterative deepening drives both time control and the PV-first ordering that feeds the TT on the next iteration.

## Implementation directive

**Module: `search.py`**

- `iterative_deepening(board, time_limit_ms, max_depth) -> Move`
  - Loop depth = 1..max_depth, calling `alphabeta` at each depth with full window `(-INF, +INF)`.
  - Check elapsed time between iterations and inside `alphabeta` every 2048 nodes; return best move from last *completed* depth on timeout or `stop`.
  - No aspiration windows.

- `alphabeta(board, depth, alpha, beta, ply) -> int`
  - Standard fail-hard alpha-beta.
  - TT probe at entry: on hit with sufficient depth, return value respecting EXACT/LOWER/UPPER flag.
  - At `depth <= 0` call `quiescence(board, alpha, beta)`.
  - Move ordering priority: (1) TT move, (2) MVV-LVA captures + promotions, (3) two killer slots for this ply, (4) history score `history[from][to]`, (5) remainder.
  - On beta cutoff for a quiet move: store as killer (shift killer[ply][0] → killer[ply][1]; new move → killer[ply][0]; reject duplicates) and increment `history[from][to] += depth*depth`.
  - Store result in TT with flag (EXACT / LOWER on beta cutoff / UPPER on no alpha raise) and depth.
  - One-ply check extension: if side to move is in check, search depth+1 (cap total extensions per branch at 2 to prevent explosion).

- `quiescence(board, alpha, beta) -> int`
  - Stand-pat = static eval; return beta on stand-pat ≥ beta; raise alpha if stand-pat > alpha.
  - Generate captures and promotions only (no check evasions, no quiet checks).
  - Order by MVV-LVA. Delta-prune obviously losing captures (stand-pat + captured_value + 200 < alpha → skip).

**Module: `tt.py`**
- Zobrist keys: 64-bit ints, initialized once in `zobrist.py` with `random.Random(seed=0xC0FFEE)` over [piece×square, side-to-move, castling rights (4 bits), ep file (8)].
- TT: fixed-size dict-backed table, **2^20 entries (1,048,576)**, replace-always policy, entries store `(key, depth, value, flag, best_move)`.
- Cleared on `ucinewgame`.

## Topic: Evaluation features

_What features should the evaluation function include, and how should they be weighted? Include / exclude with reasons: material, piece-square tables, mobility, king safety, pawn structure, bishop pair, passed pawns, center control, tempo. Be specific about coefficients or relative ordering._

## Decision
Adopt a tapered evaluation with the following terms: material, tapered piece-square tables, mobility, king safety, pawn structure (doubled/isolated/backward), bishop pair, and passed pawns (rank-scaled). Exclude explicit center control and tempo as standalone terms. Centipawn-denominated weights, no percentage budgets.

## Reasoning
DeepSeek's framing — centipawn-denominated weights rather than Grok's fixed percentage budget — is correct. A 70% material cap fights the search; the right discipline is "material is ~100 cp/pawn and positional terms accumulate against that scale." This also makes the ELO slider trivial: scale positional terms by a single coefficient.

Grok's tapered PST and rank-scaled passed pawns win on substance. Static PSTs misvalue kings and pawns dramatically between middlegame and endgame; the ~50 LOC cost is justified and both DeepSeek and OpenAI conceded the point in critique.

I override DeepSeek's "evaluate king safety/mobility on only ~10% of nodes" lazy-eval scheme. It causes search instability (eval inconsistency across sibling nodes breaks alpha-beta ordering). Instead, use lazy evaluation the standard way: cheap material+PST first, full eval only when the lazy score is within a margin of the alpha-beta window. OpenAI was right that selective skipping is dangerous; the standard lazy-eval pattern gives the speed without the inconsistency.

OpenAI's exclusion of center control and tempo stands — PSTs subsume center control, and tempo is noise at our search depths.

## Implementation directive

**Module:** `engine/evaluate.py`

**Top-level function:** `evaluate(board) -> int` returns centipawns from side-to-move's perspective.

**Game phase:** Compute `phase` in [0, 24] from non-pawn material (N=1, B=1, R=2, Q=4 per side, max 24 = opening). Interpolate: `score = (mg_score * phase + eg_score * (24 - phase)) // 24`.

**Material (centipawns, both phases identical):**
- P=100, N=320, B=330, R=500, Q=900, K=0

**Piece-square tables:** Provide TWO 64-entry tables per piece type: `PST_MG[piece]` and `PST_EG[piece]`. Use standard Stockfish-style values; king MG table favors castled corners, king EG table favors center. Tables are from White's POV; mirror for Black via `sq ^ 56`.

**Mobility:** Count pseudo-legal non-capture target squares per piece (exclude pawns and king).
- Knight: 4 cp/move, Bishop: 5 cp/move, Rook: 2 cp/move (MG) / 4 cp/move (EG), Queen: 1 cp/move.

**King safety (MG only, scaled by `phase/24`):**
- Pawn shield: for each of the 3 files in front of king, -15 cp if no friendly pawn, -10 cp if pawn advanced past 2nd rank from king.
- Open/semi-open file on king: -25 cp fully open, -15 cp semi-open.
- Attacker count within king zone (3x3 around king + forward): -20, -50, -90, -140 cp for 1,2,3,4+ attackers.

**Pawn structure (per pawn):**
- Doubled: -15 cp (MG), -25 cp (EG)
- Isolated: -15 cp (MG), -20 cp (EG)
- Backward: -10 cp both phases

**Passed pawns (rank-scaled, white's perspective; mirror for black):**
- Rank 2: +10, R3: +17, R4: +25, R5: +40, R6: +70, R7: +120 (MG)
- Endgame: multiply by 1.5

**Bishop pair:** +30 cp MG, +50 cp EG.

**Excluded:** No center-control term. No tempo term.

**Lazy evaluation:** Compute material+PST first. If `|lazy_score - alpha| > 200` AND `|lazy_score - beta| > 200`, return

## Topic: ELO scaling mechanism

_How should the 400-2400 ELO slider map onto engine behaviour? Cover: depth scaling, time-per-move scaling, evaluation noise, top-K candidate sampling, and how to keep weak play believable rather than embarrassingly random._

## Decision
Adopt a blended ELO scaling mechanism combining depth scaling, soft time caps, decreasing evaluation noise, and weighted top-K root sampling — closest to OpenAI's proposal, with DeepSeek's performance discipline applied to keep low-ELO play *cheaper*, not more expensive, than high-ELO play.

## Reasoning
OpenAI's blended approach is the only one that produces believably human weak play across the full 400–2400 range; pure depth scaling (DeepSeek) yields a "small Stockfish" that plays shallow but never hangs pieces like a 600-rated human actually does. Grok correctly identifies that top-K sampling adds realism but its 500cp noise variance is reckless — that magnitude will drop queens in obvious positions, which is exactly the "embarrassingly random" failure mode the topic warns against.

DeepSeek's critique about Python overhead is partially valid but overstated: top-K at the *root only* costs nothing extra because the root move list is already scored by the search. I'm overriding DeepSeek's rejection of top-K on that basis. I'm also overriding Grok's noise range — capping noise well below a minor piece value (max ~75cp) keeps blunders plausible rather than catastrophic.

DeepSeek's framing that "low ELO should compute less, not more" is adopted as a hard constraint: noise and top-K are O(root moves), not O(nodes), so they don't violate it. Time scaling stays but as a *ceiling*, not a primary lever, addressing Grok's hardware-variance concern by making depth the dominant signal.

Weighted (softmax) top-K beats uniform top-K — OpenAI's concession on this point is correct and adopted.

## Implementation directive

**Module:** `engine/strength.py`, exposing `class StrengthConfig` and `def configure(elo: int) -> StrengthConfig`.

**UCI option:** `setoption name UCI_Elo value <int>`, clamped to [400, 2400]. Also expose `setoption name UCI_LimitStrength value <bool>`; when false, engine plays at full strength regardless of slider.

**Interpolation:** Define `t = (elo - 400) / 2000.0`, clamped to [0,1]. All parameters below interpolate on `t`.

**Parameters (must be exactly these):**

| Parameter | At 400 (t=0) | At 2400 (t=1) | Curve |
|---|---|---|---|
| `max_depth` | 1 | 10 | linear, round to int |
| `soft_time_ms` | 100 | 3000 | linear (ceiling, not target) |
| `hard_time_ms` | 300 | 5000 | linear |
| `eval_noise_cp` (stddev of Gaussian added to leaf eval) | 75 | 0 | linear |
| `top_k` (root candidates considered) | 4 | 1 | linear, round to int, floor 1 |
| `softmax_temp_cp` (centipawns) | 80 | 1 | exponential decay: `80 * (1/80)**t` |

**Root move selection algorithm:**
1. Run alpha-beta to `max_depth` (with eval noise applied at leaves via `random.gauss(0, eval_noise_cp)` added to static eval before returning).
2. Collect all root moves with their search scores.
3. Take top `top_k` moves by score.
4. Sample one using softmax: `P(move_i) ∝ exp(score_i / softmax_temp_cp)`.
5. At `top_k == 1`, this degenerates to deterministic best-move; do not sample.

**Hard guardrails (override sampling/noise):**
- If a move delivers checkmate, play it unconditionally.
- If `top_k > 1`, drop any candidate whose score is worse than the best by more than `300 + 400*(1-t)` centipawns — prevents queen-hangs at low ELO while still allowing plausible-looking mistakes.
- Eval noise is applied only at leaf nodes in search, never to the final root score used for the guardrail comparison above (use noise-free re-score for the cutoff check).

**Determinism:** Accept `set

## Topic: UCI + UI architecture

_How should UCI and the human-playable UI be structured? Should the UI be a stdlib http.server + vanilla JS page or something richer? How are search threads, stop signals, and shared engine state managed across the two interfaces?_

## Decision
Build a dual-interface engine with a single thread-safe command queue feeding a singleton engine core, a dedicated interruptible search thread controlled by a `threading.Event` stop flag, a UCI reader thread on stdin/stdout, and a stdlib `http.server` thread serving a vanilla JS board UI that talks to the core via a small JSON HTTP API.

## Reasoning
DeepSeek's command-queue decoupling is the strongest single idea in the debate: it eliminates lock sprawl, removes the deadlock surface OpenAI's multi-thread shared-state design risks, and gives `stop` a single unambiguous meaning. I'm adopting it as the backbone.

OpenAI is right that the HTTP server must run in its own thread so long searches never block human interaction — DeepSeek's "just poll/refresh" answer is too austere for a playable UI. So I'm overriding DeepSeek on UI responsiveness: the HTTP handler thread enqueues commands and reads results from the engine core via a thread-safe state snapshot, not via blocking on the queue.

Grok's singleton `EngineState` is useful as a *read-only snapshot* (board FEN, search status, last bestmove, ELO) that the HTTP layer can serve without grabbing engine internals — but I reject Grok's "locks everywhere on shared mutable state" framing. Mutation goes through the queue; reads go through an atomic snapshot guarded by one `RLock`. This is the concession OpenAI and Grok both gestured at, formalized.

GIL-bound single-process threading is fine here; multiprocessing is rejected outright (IPC cost, serialization, no real win under pure-Python search).

## Implementation directive

**Modules (create exactly these):**
- `engine/board.py` — position, move gen, legality, repetition, 50-move, insufficient material.
- `engine/search.py` — alpha-beta, must accept `stop_event: threading.Event` and check it every node.
- `engine/eval.py` — material + PST + mobility + king safety + pawn structure.
- `engine/core.py` — `EngineCore` singleton class. Owns the board, search thread, and state snapshot.
- `engine/uci.py` — UCI reader loop on stdin; writer helper for stdout. Must be line-buffered (`sys.stdout.reconfigure(line_buffering=True)` or explicit `flush=True`).
- `ui/server.py` — `http.server.ThreadingHTTPServer` with a `BaseHTTPRequestHandler` subclass.
- `ui/static/index.html`, `ui/static/board.js`, `ui/static/board.css` — vanilla JS, no frameworks.
- `main.py` — entry point with flags `--uci` (default) and `--ui [--port N]` (default port 8080); `--both` runs both.
- `tests/` — `test_rules.py`, `test_search.py`, `test_eval.py`, `test_uci.py`, `test_core.py`.

**EngineCore contract:**
```
class EngineCore:
    cmd_queue: queue.Queue           # producers: UCI thread, HTTP thread
    stop_event: threading.Event      # set to abort current search
    search_thread: threading.Thread | None
    _snapshot_lock: threading.RLock
    _snapshot: dict                  # {fen, turn, legal_moves, last_bestmove,
                                     #  search_active, depth, score_cp, pv, elo}

    def submit(self, cmd: Command) -> None       # thread-safe enqueue
    def snapshot(self) -> dict                   # returns deep-copied dict
    def run_forever(self) -> None                # consumes cmd_queue on main worker thread
```
Exactly one consumer thread drains `cmd_queue`. Search runs on a *separate* worker thread spawned per `go`; `stop` sets `stop_event` and joins.

**Command types (dataclasses in `engine/core.py`):**
`CmdNewGame`, `CmdPosition(fen, moves)`, `CmdGo(wtime, btime, depth, movetime)`, `CmdStop`, `CmdQ
