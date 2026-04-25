# Chain-of-Thought Chess Engine

A from-scratch chess engine built **incrementally, one stage at a time**, in
contrast to the sibling `oneshot_*` projects in this repo which were each
produced in a single pass. The point of this project is to make the design
decisions visible step by step and keep every stage individually verified
by tests before moving on.

## Project goal

A complete chess engine application that:

- lets a human play against the engine,
- speaks the **UCI** (Universal Chess Interface) protocol, and
- exposes an **ELO strength slider** so the engine can play at different
  skill levels.

## Hard requirements

- **Chess logic implemented from scratch.** No Stockfish or any other
  external chess engine is used for move generation, search, or evaluation.
- Full legal chess rules: legal moves, check/checkmate/stalemate, castling,
  en passant, promotion, pinned pieces, illegal-move rejection, threefold
  repetition, fifty-move rule, insufficient material.
- **FEN** import and export.
- **PGN** export.
- **UCI** protocol support.
- **User-playable interface** (browser).
- **Adjustable ELO slider.**
- Modular, maintainable architecture.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Rules engine | Pure Python (planned: 8x8 mailbox; bitboards possible later behind the same `Board` API) | "From scratch" rules out `python-chess`. Mailbox is the easiest representation to get **correct** first; performance can be improved later without touching callers. |
| Search | Pure Python alpha-beta (planned) | Same module boundary. Search depends only on `core` via a small surface. |
| UCI | `sys.stdin`/`sys.stdout` line loop | UCI is a line protocol; stdlib is enough. |
| UI | Stdlib `http.server` + static HTML/JS | No framework dependency; matches the sibling projects. |
| Tests | `pytest` | Already used in the sibling projects; the workspace `.venv` has it. |

**No third-party runtime dependencies for the engine itself.** The only
declared requirement (`pytest`) is for tests.

## Why this architecture supports UCI and ELO

- **One contract for both surfaces.**
  `Engine.search(board, limits) -> SearchResult` is the *only* method
  UCI and the UI consume. Anything that respects `SearchLimits` (depth,
  movetime, wtime/btime, etc.) plugs into a real chess GUI without
  changes.
- **ELO is a pure function.**
  `search.elo.config_from_elo(elo) -> EloConfig` is consulted by the
  engine internally. The UCI `setoption name UCI_Elo` handler and the
  UI slider both call the same function, so strength is consistent
  across surfaces and the mapping curve can be tuned in one place.
- **`Move` is independent of internal board representation.**
  Moves are described purely by from/to squares and an optional
  promotion. Whether a move is castling/en-passant/capture is decided
  by the `Board` it is applied to. This means the rules stage can pick
  any internal layout (mailbox, 0x88, bitboards) without changing
  callers.
- **Strict layering.**
  `core` does not import from `search`, `uci`, or `ui`.
  `search` does not import from `uci` or `ui`.
  `uci` and `ui` are siblings; neither imports the other.
  These rules are enforced by a unit test (`test_layering`) so they
  cannot quietly drift.

## Layout

```
engines/chainofthought/
├── __init__.py
├── __main__.py                 # `python -m engines.chainofthought [--uci|--ui]`
├── README.md
├── requirements.txt
├── core/                       # chess rules; depends on nothing in-project
│   ├── __init__.py
│   ├── types.py                # Color, PieceType, Piece, Square helpers
│   ├── move.py                 # Move (frozen dataclass, UCI string round-trip)
│   ├── board.py                # Board interface (stubs for now)
│   ├── game.py                 # GameState interface (history, draw rules)
│   └── fen.py                  # FEN parse/serialize (signatures only)
├── search/                     # depends on core
│   ├── __init__.py
│   ├── engine.py               # Engine, SearchLimits, SearchResult
│   ├── evaluation.py           # evaluate(board) -> int (signature only)
│   └── elo.py                  # EloConfig + config_from_elo
├── uci/                        # depends on core + search
│   ├── __init__.py
│   └── protocol.py             # UCIProtocol.run() loop (stub)
├── ui/                         # depends on core + search
│   ├── __init__.py
│   ├── session.py              # Session: state model wrapping GameState + Engine
│   ├── server.py               # ThreadingHTTPServer + JSON API
│   └── static/
│       └── index.html          # frontend (board + controls + JS)
└── tests/
    ├── __init__.py
    ├── conftest.py             # registers --runslow / `slow` marker
    ├── test_smoke.py           # package import + version
    ├── test_interfaces.py      # public surface, value types, layering
    ├── test_board.py           # board state, make/unmake basics
    ├── test_fen.py             # parse/serialize, validation, malformed
    ├── test_movegen.py         # pseudo-legal moves per piece type
    ├── test_legality.py        # check, pins, castling/EP legality, mate
    ├── test_game.py            # GameState, undo, draws, PGN
    ├── test_evaluation.py      # static eval terms & sanity positions
    ├── test_search.py          # search correctness, ID, qsearch, TT
    ├── test_elo.py             # ELO -> config mapping & weakening
    ├── test_uci.py             # UCI protocol commands & threading
    ├── test_ui_session.py      # UI Session (no HTTP)
    ├── test_ui_server.py       # UI HTTP/JSON over a real server
    ├── test_perft.py           # perft battery + invariants (stage 11)
    └── test_hardening.py       # cross-cutting hardening (stage 11)
```

## Stage log

| Stage | Status     | Summary                                                  |
|-------|------------|----------------------------------------------------------|
| 0     | complete   | Project directory + smoke test harness.                  |
| 1     | complete   | Stack chosen, scaffold + interfaces + tests for surface. |
| 2     | complete   | Real `Board`, `CastlingRights`, FEN parse/serialize.     |
| 3     | complete   | Pseudo-legal move generation for all piece types.        |
| 4     | complete   | Make/unmake, legal moves, check/checkmate/stalemate.     |
| 5     | complete   | GameState, undo, draws (3-fold/50-move/material), PGN.   |
| 6     | complete   | Static evaluator: material, PST, mobility, KS, pawns, ctr.|
| 7     | complete   | Negamax + alpha-beta + ID + qsearch + TT; PV diagnostics.|
| 8     | complete   | ELO slider (400..2400): depth, time, noise, blunder mix. |
| 9     | complete   | UCI: uci/isready/ucinewgame/position/go/stop/quit/setoption.|
| 10    | complete   | Browser UI: board, ELO slider, color choice, resign, PGN export. |
| 11    | complete   | Perft suite, hardening tests, terminal-position contract fix. |

## Testing & perft (stage 11)

The always-on suite is **`pytest engines/chainofthought/tests/`**
(currently 623 tests, ~3 min wall-clock). It covers:

- per-module unit tests for `core`, `search`, `uci`, `ui`,
- a perft battery for the six standard reference positions
  (matches the [Chess Programming Wiki numbers](https://www.chessprogramming.org/Perft_Results)
  exactly through depth 3-4 in the always-on suite),
- make/unmake state-restoration invariants walked over the perft tree,
- FEN serialize/parse idempotence walked over the perft tree,
- cross-system hardening (UCI under long position chains, Session
  under rapid resign/new-game/elo cycling, transposition-key
  consistency across move orders, 100-ply self-play FEN consistency,
  concurrent go/stop cycles).

Slow / deep validation (~2 min more) is opt-in:

```bash
pytest engines/chainofthought/tests/ --runslow
```

This adds the deep perft cases (startpos d=5 = 4,865,609 leaves,
kiwipete d=4 = 4,085,603 leaves, etc.). All published values match.

### Stage 11 architecture / error-handling fixes

- **`Engine.search` terminal-position contract.** Previously
  returned `score_cp = -MATE_SCORE` (an internal magic number) when
  called on a mated position. Now returns `mate_in = 0` for mate
  and `score_cp = 0, mate_in = None` for stalemate, with
  `best_move = None` in both cases. The UCI layer was already
  preferring `mate_in` so no behaviour change there.
- **`Move.from_uci("0000")` clearer error.** UCI's null-move
  sentinel is not a `Move` value; it's a protocol-layer concept.
  The parser now rejects it with a message that says so, instead
  of falling through to a confusing "not a square name" error.

### Known limitations

- **Pure-Python perft is slow.** ~100k nodes/sec. Startpos d=6
  (~119M leaves) is not in the suite; it would take ~20 minutes.
  Bitboards or a C extension would fix this but are out of scope.
- **No Zobrist hashing.** Position keys are a tuple of board state.
  Correct (no false collisions), but slow compared to a 64-bit
  Zobrist hash. This bottlenecks the transposition table and is
  the next obvious performance lever.
- **No concurrent search.** The engine search is single-threaded;
  the UI mutex serialises engine moves with state polls. Fine for
  one human player, would not scale to multiple games on one
  process.
- **ELO is uncalibrated.** The 400-2400 slider drives parameters
  that *feel* right but were not rated against a benchmark engine
  pool. Treat the numbers as relative-strength labels, not Elo
  ratings in any official sense.

## Browser UI (stage 10)

`python -m engines.chainofthought` (or `--ui`) starts a tiny
`http.server` on `http://127.0.0.1:8000/` that serves a single-page
chess client. No frontend framework, no build step, no third-party
runtime dependencies -- just stdlib + ~400 lines of vanilla JS.

What you can do in the UI:

- **Pick White or Black** before clicking *New Game*. Picking Black
  triggers an immediate engine move so you face a real opening.
- **Set engine ELO** with the slider (400..2400). Changes apply
  mid-game; the new strength takes effect on the engine's next move.
- **Click a piece** to see its legal destinations as dots
  (or rings for captures). Click a destination to play.
- **Promotion** opens a modal to pick Q/R/B/N. Under-specified UCI
  strings (`e7e8`) auto-promote to queen on the server too, so the
  modal isn't load-bearing for correctness.
- **Resign** ends the game and updates the result.
- **Move list** on the right shows SAN with white/black columns.
- **Engine pane** shows what the engine just played plus depth,
  evaluation (or mate-in-N), nodes, and time.
- **Download PGN** exports the game (mid-game is fine).

Server architecture:

```
engines/chainofthought/ui/
├── session.py        # Session: GameState + Engine + UI state
├── server.py         # ThreadingHTTPServer + JSON + static
└── static/
    └── index.html    # board + controls + JS client
```

`Session` is the entire UI brain. It owns one `GameState` and one
`Engine`, validates user input, and exposes `state_dict()` -- a
single JSON-friendly snapshot the frontend renders. The HTTP layer
in `server.py` is just a thin wire-format wrapper. Both layers are
unit-tested independently (`test_ui_session.py`, `test_ui_server.py`).

JSON API (consumed only by the bundled frontend, but documented):

| Method + path             | Body                | Returns                    |
|---------------------------|---------------------|----------------------------|
| `GET  /`                  | -                   | `index.html`               |
| `GET  /static/<path>`     | -                   | static asset               |
| `GET  /api/state`         | -                   | full session state         |
| `GET  /api/pgn`           | -                   | PGN as `text/plain`        |
| `POST /api/new`           | `{color, elo}`      | new session state          |
| `POST /api/move`          | `{uci}`             | state after user move      |
| `POST /api/engine_move`   | -                   | state after engine move    |
| `POST /api/resign`        | -                   | state with resigned=true   |
| `POST /api/elo`           | `{elo}`             | state with new ELO         |

Errors return JSON `{"error": "..."}` with a 4xx status; the loop
never crashes on bad input.

Threading: `ThreadingHTTPServer` lets state polls run while another
request is mid-search, but a single mutex serialises *session*
access. While the engine is searching (a few seconds at high ELO),
other state-mutating requests queue. Fine for a single-player UI;
if multi-user is ever wanted, the obvious next step is one Session
per cookie.

## UCI (stage 9)

`python -m engines.chainofthought --uci` exposes the engine as a UCI
subprocess that any standard chess GUI (Cute Chess, Arena, Banksia,
lichess-bot) can launch.

Supported commands: `uci`, `isready`, `ucinewgame`, `position
[startpos | fen <FEN>] [moves ...]`, `go [depth | movetime | wtime
btime winc binc | infinite]`, `stop`, `quit`, `setoption name
UCI_Elo value <N>`, `setoption name UCI_LimitStrength value
<bool>`, `debug` (no-op). Anything else is ignored per spec; parse
errors emit `info string ...` for debugging.

Threading: `go` returns immediately and runs the search in a daemon
thread. `isready` replies `readyok` *during* an active search (per
spec). `stop`, `quit`, and `ucinewgame` cooperatively stop and join
the search thread before continuing.

Example session (engine output indented for readability):

```
> uci
    id name Chain-of-Thought Engine 0.0.10
    id author PointChess Team
    option name UCI_Elo type spin default 1500 min 400 max 2400
    option name UCI_LimitStrength type check default true
    uciok
> setoption name UCI_Elo value 1800
> isready
    readyok
> ucinewgame
> position startpos moves e2e4 e7e5
> go depth 3
    info depth 3 score cp 20 nodes 4521 nps 12345 time 366 pv g1f3 b8c6 f1c4
    bestmove g1f3
> quit
```

## ELO slider (stage 8)

`Engine(elo=...)` (and `Engine.set_elo(elo)`) drives strength via a
single integer in `[400, 2400]`. The pure mapping
`search.elo.config_from_elo(elo)` returns four knobs that are all
linearly interpolated in `t = (elo - 400) / 2000`:

| ELO  | depth | movetime ms | noise ±cp | blunder | persona              |
|------|-------|-------------|-----------|---------|----------------------|
| 400  |   1   |     200     |    200    |  0.20   | total beginner       |
| 800  |   2   |    1160     |    160    |  0.16   | casual hobbyist      |
| 1200 |   3   |    2120     |    120    |  0.12   | improving novice     |
| 1500 |   4   |    2840     |     90    |  0.09   | club casual (default)|
| 1800 |   5   |    3560     |     60    |  0.06   | competent club       |
| 2100 |   6   |    4280     |     30    |  0.03   | strong club          |
| 2400 |   7   |    5000     |      0    |  0.00   | engine maximum       |

ELO numbers are slider labels, NOT calibrated ratings. Treat them as
"approximate playing-strength target". See
`engines/chainofthought/search/elo.py` for the full rationale and
tuning notes.

How weakening reaches the move:

1. **Depth & movetime** are *defaults* used only when the caller
   didn't pass `SearchLimits.depth` / `SearchLimits.movetime_ms`.
   UCI/UI users with explicit limits override them.
2. **Eval noise** adds uniform `±noise_cp` to each root move's
   score. A pawn-sized swap can flip the engine's preferred move,
   but a free-piece swing dwarfs the noise so the engine still
   takes obvious material.
3. **Blunder probability** sometimes (`blunder_pct` of moves) picks
   from the top three jittered candidates with weights `[3, 2, 1]`,
   so the chosen move is still recognisably "one of the candidates"
   rather than random.
4. **Forced mate is sacred.** Even at MIN_ELO the engine plays the
   mating move when it sees one; the alternative looks broken, not
   human.

Reproducibility: pass `Engine(elo=..., seed=int)` to fix the
weakening RNG (tests do this). With `seed=None` (default) the
engine uses system entropy so repeated games at the same ELO look
different.

## Setup

From the repository root:

```bash
# one-time install
pip install -r engines/chainofthought/requirements.txt

# run all tests
python -m pytest engines/chainofthought/tests/ -v
```

## Running the program

```bash
python -m engines.chainofthought --uci             # UCI mode (stdin/stdout)
python -m engines.chainofthought --ui              # browser UI on :8000
python -m engines.chainofthought --port 9999       # browser UI on :9999
python -m engines.chainofthought                   # default: --ui on :8000
```

Open `http://127.0.0.1:8000/` in any modern browser to play.
