# Contextualized Chess Engine

A complete, modular chess engine with full UCI support, an ELO strength
slider, and a browser-based human-vs-engine UI. Built as a *context-augmented*
one-shot from the prompt in `../README.md`, this implementation deliberately
leans on the supplied references where they save effort (rules correctness,
UCI conventions) and writes the rest from scratch (search, evaluation, ELO
scaling, UI).

> Sister project: see `../oneshot_nocontext_engine/` for the same task built
> *without* any external context — useful as an A/B comparison.

## Quick start

```bash
cd oneshot_contextualized_engine
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Web UI (human vs engine)
python3 run_web.py            # then open http://127.0.0.1:5000

# UCI engine (drop into CuteChess, Arena, Lichess BotLi, etc.)
python3 run_uci.py

# Tests
python3 -m pytest tests/      # or:  python3 -m unittest discover tests
```

## Architecture

```
oneshot_contextualized_engine/
├── engine/                # Pure chess logic (no I/O)
│   ├── game.py            #   game manager: history, FEN, PGN, undo, repetition
│   ├── evaluation.py      #   PeSTO tapered eval + king-safety/mobility/pawns
│   ├── tt.py              #   Zobrist-keyed transposition table
│   ├── ordering.py        #   MVV-LVA, killer moves, history heuristic
│   ├── search.py          #   negamax + α-β + ID + quiescence + null-move + LMR
│   ├── elo.py             #   ELO -> (depth, time, noise, blunder, skill) map
│   ├── opening_book.py    #   tiny built-in book of known openings
│   └── engine.py          #   high-level Engine facade
├── uci/
│   └── protocol.py        # UCI protocol layer (separate process loop)
├── web/
│   ├── server.py          # Flask app: REST + static page
│   ├── templates/index.html
│   └── static/{app.js, style.css}
├── tests/
│   ├── test_perft.py      # perft sanity (Kiwipete, pos3, pos4) at low depth
│   ├── test_rules.py      # FEN / castling / EP / promotion / mate / stalemate
│   ├── test_search.py     # mate-in-N, no-illegal-moves, TT correctness
│   ├── test_uci.py        # UCI command round-trips
│   └── test_elo.py        # ELO mapping monotonicity
├── docs/
│   ├── ARCHITECTURE.md    # module-by-module deep dive
│   ├── ENGINE.md          # search & eval design notes
│   └── ELO.md             # ELO mapping rationale & how to tune
├── samples/positions.txt  # benchmark FENs
├── run_uci.py
├── run_web.py
└── requirements.txt
```

The four boundaries (`engine`, `uci`, `web`, `tests`) never reach across each
other. The UCI and web layers both depend on `engine.engine.Engine`; nothing
in `engine/` knows what a socket or stdin is.

## Engine design (short version)

Search: iterative deepening negamax with alpha-beta, transposition table
(Zobrist hash from python-chess), MVV-LVA capture ordering, killer-move and
history heuristics, principal-variation move first, null-move pruning,
late-move reductions, and a quiescence search with stand-pat and capture-only
expansion. See [docs/ENGINE.md](docs/ENGINE.md).

Evaluation: PeSTO-style tapered evaluation (mg/eg blended by remaining
non-pawn material) with bonuses for mobility, king-zone attackers, doubled
and isolated pawns, passed pawns, bishop pair, and rook on (semi-)open file.
PSTs are the public PeSTO tables. See [docs/ENGINE.md](docs/ENGINE.md).

ELO scaling: a single function `engine.elo.config_from_elo(elo)` maps ELO ∈
[400, 2400] into a `StrengthConfig` (max search depth, move-time budget,
skill-weighted MultiPV pick, evaluation noise in centipawns, per-move blunder
probability, and a flag for using the opening book). The mapping is monotonic
and tabulated, so it is easy to retune without touching search code. See
[docs/ELO.md](docs/ELO.md).

UCI: `uci/protocol.py` is a self-contained loop that speaks UCI on
stdin/stdout. It supports `uci`, `isready`, `ucinewgame`, `position`,
`go` (with `depth`, `movetime`, `wtime`/`btime`/`winc`/`binc`/`movestogo`,
`infinite`), `stop`, and `quit`, and exposes the options `Hash`,
`UCI_LimitStrength`, `UCI_Elo`, `Skill Level`, `MoveOverhead`, and `MultiPV`.

Web UI: a single-page Flask app with a click-to-move 8×8 board rendered as
CSS-grid Unicode glyphs (no external CDN required). Side selector, ELO
slider, resign button, status pane, move list, FEN display, PGN download.

## How the supplied context shaped this build

| Source | What it gave us | Where it shows up |
|---|---|---|
| **python-chess** docs | Battle-tested move generation, FEN/PGN, repetition, Zobrist hashing, SAN. | `engine/game.py`, `engine/tt.py`, all `tests/*` use `chess.Board` as ground truth. |
| **Stockfish source/wiki** | UCI command set + option names; PVS/TT/quiescence/LMR conventions; PeSTO PSTs. | `uci/protocol.py` option list, `engine/search.py` shape, `engine/evaluation.py` tables. |
| **Stockfish UCI docs** | Exact behavior of `go`, time control fields, `UCI_LimitStrength`/`UCI_Elo`/`Skill Level`. | `uci/protocol.py`, `engine/elo.py`. |
| **CuteChess** | Tournament-grade UCI client → reference for *what a strict UCI host expects*. | UCI loop is line-buffered, never blocks `isready`, replies even mid-search. |
| **Lichess source** | Inspiration for the simple board UI and the legal-moves API. | `web/server.py`'s `/api/legal_moves`, `static/app.js` click-to-move flow. |
| **Perft results** | Exact node counts for known positions used as move-gen sanity tests. | `tests/test_perft.py` (Kiwipete, position 3, 4, 5, 6 at low depths). |

What is *reused*: `python-chess` is imported directly. We do not reimplement
move generation, FEN parsing, repetition detection, or the Zobrist hash.

What is *wrapped*: `engine/game.py` is a thin façade around `chess.Board` to
add convenience (PGN export with headers, undo, sample-position loading).

What is *implemented from scratch*: everything in `engine/search.py`,
`engine/evaluation.py`, `engine/tt.py`, `engine/ordering.py`,
`engine/elo.py`, the entire `uci/` package, and the entire `web/` UI.

## Known limitations

* Single-threaded search. `Threads` UCI option is accepted but ignored
  (declared `min=max=1` so GUIs do not offer a choice).
* No NNUE, no SIMD, no bitboard hand-rolling — peak strength is ~2200 ELO on
  modest hardware at 1s/move.
* The opening book is hand-rolled and tiny (a few mainlines deep). Polyglot
  `.bin` loading is not implemented (would be a nice extension).
* Tablebase probing is not implemented.
* PGN export does not include clock comments.
* Web UI is intentionally minimal (no piece animation, no premove).

## Sample positions

See [`samples/positions.txt`](samples/positions.txt) for benchmark FENs
(starting position, Kiwipete, endgames, mate-in-N puzzles).

## License & attribution

This project is MIT-licensed. PeSTO PST values are public-domain by their
author Ronald Friederich. Move generation, FEN/PGN, and Zobrist hashing
come from `python-chess` (GPL-3.0) — used as a library dependency only.
