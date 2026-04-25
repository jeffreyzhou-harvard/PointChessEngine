# PointChess ReAct Engine

A complete chess engine built end-to-end with the **ReAct (Reasoning + Acting)
prompting workflow** — every architectural decision was preceded by an
explicit `Thought / Action / Observation` step (see
[`docs/REACT_BUILD_LOG.md`](docs/REACT_BUILD_LOG.md)).

The engine itself can also emit a structured **reasoning trace** for each
move it plays, mirroring the same prompting pattern from build-time into
runtime.

- Pure Python 3.10+, **no external dependencies** for the runtime.
- Browser UI you can play against.
- UCI engine that plugs into Cute Chess, Arena, ChessBase, etc.
- ELO slider 400-2400 with believable weak play.
- Full legal chess rules + perft-tested move generation.

---

## Quick start

```bash
# Web UI (default)
python -m engines.oneshot_react
# -> http://127.0.0.1:8000

# UCI mode (for chess GUIs)
python -m engines.oneshot_react --uci

# Custom host/port
python -m engines.oneshot_react --host 0.0.0.0 --port 9000

# Tests
pip install -r engines/oneshot_react/requirements.txt
python -m pytest engines/oneshot_react/tests/ -v
```

---

## Project structure

```
engines/oneshot_react/
├── README.md
├── requirements.txt           (pytest only - runtime is stdlib)
├── __main__.py                (entry point: web UI / --uci switch)
├── core/                      (rules: pieces, board, movegen, FEN, SAN/PGN)
│   ├── pieces.py
│   ├── square.py
│   ├── move.py
│   ├── fen.py
│   ├── movegen.py
│   ├── board.py
│   └── notation.py
├── engine/                    (search & evaluation)
│   ├── psqt.py                (piece-square tables)
│   ├── evaluator.py
│   ├── transposition.py
│   ├── strength.py            (ELO -> search-parameter mapping)
│   ├── reasoning.py           (ReAct trace of engine decisions)
│   └── search.py              (alpha-beta + ID + quiescence + TT)
├── uci/
│   └── protocol.py            (UCI command dispatcher)
├── ui/                        (browser UI)
│   ├── server.py              (stdlib HTTP + JSON API)
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── app.js
├── tests/                     (55 tests: rules, perft, engine, UCI, SAN/PGN)
├── samples/positions.txt      (FEN test cases)
└── docs/
    ├── ARCHITECTURE.md
    └── REACT_BUILD_LOG.md
```

---

## What's implemented

### Chess rules (`core/`)

- All piece movement, including pinned-piece restrictions.
- Castling on both sides with full legality (not through / out of / into check;
  rook captures revoke rights).
- En passant (with proper undo and repetition-key handling).
- Pawn promotion (Q/R/B/N).
- Check, checkmate, stalemate detection.
- Threefold repetition, fifty-move rule, insufficient material.
- FEN import/export, SAN, PGN export with full game replay.
- Move history with `unmake_move` for unbounded undo.
- Perft-tested move generation.

### Engine (`engine/`)

- **Alpha-beta** search with iterative deepening (root -> 1 -> 2 -> ...).
- **Quiescence search** on captures + promotions to avoid the horizon effect.
- **Transposition table** with EXACT/LOWER/UPPER bound flags.
- **Move ordering**: TT-move, MVV-LVA captures, promotions, killer moves, history.
- **Evaluation**: material, piece-square tables (separate king PST for
  midgame/endgame), bishop pair, mobility, doubled/isolated/passed pawns,
  king pawn shield, center control.
- **Reasoning trace**: each engine move can produce a Thought/Action/Observation
  log explaining what was searched, what the candidates were, and whether the
  ELO setting forced a sub-optimal pick.

### ELO slider (400-2400)

Five parameters interpolate piecewise-linearly across the slider:

| Bracket   | Depth | Movetime    | Eval noise | Blunder % | Pool |
| --------- | ----- | ----------- | ---------- | --------- | ---- |
| 400-800   | 1-2   | 0.3-0.8 s   | ±250-120cp | 28-14 %   | 5    |
| 800-1200  | 2-3   | 0.8-1.5 s   | ±120-60cp  | 14-6 %    | 4    |
| 1200-1600 | 3-4   | 1.5-3.0 s   | ±60-25cp   | 6-2 %     | 3    |
| 1600-2000 | 4-5   | 3.0-5.0 s   | ±25-10cp   | 2-0.5 %   | 2    |
| 2000-2400 | 5-7   | 5.0-8.0 s   | 0cp        | ~0 %      | 1    |

**How weak play stays human-ish**: the engine still searches; on a "blunder
roll" it picks weighted-randomly from the **2nd-5th best** moves rather than
a uniformly-random move. Combined with leaf-level eval noise this produces
plausible mistakes — no silly ?? moves, just inferior plans.

Tunable in [`engine/strength.py`](engine/strength.py).

### UCI (`uci/`)

Implements the GUI-facing subset:

```
uci         id name PointChess ReAct
            id author PointChess ReAct Team
            option name UCI_Elo type spin default 1500 min 400 max 2400
            option name Skill Level type spin default 10 min 0 max 20
            option name Hash type spin default 16 min 1 max 1024
            uciok
isready                          -> readyok
ucinewgame                       (clears TT, resets board)
position startpos|fen ...        with optional `moves m1 m2 ...`
go {movetime,depth,wtime,btime,winc,binc,infinite}
                                 -> info ... lines + bestmove ...
stop                             (interrupts search thread)
setoption name UCI_Elo value N
setoption name Skill Level value N    (0..20 mapped onto 400..2400)
quit
```

### Web UI (`ui/`)

Single-page HTML/CSS/JS. Features:

- Click-to-move with green dots for legal targets and red rings for captures.
- Auto-flip board if you choose to play Black.
- Pawn promotion modal.
- Last-move highlight, in-check highlight.
- ELO slider (live; no need to start a new game).
- Move list with engine moves color-tinted.
- Engine info panel: played move, best move (if different), eval (cp), depth,
  nodes, NPS, PV, and the engine's **reasoning trace** for that move.
- New game / undo (two ply) / resign / export PGN.

---

## Run instructions

### As a web app

```bash
python -m engines.oneshot_react
# Open http://127.0.0.1:8000 in your browser.
```

### As a UCI engine

```bash
python -m engines.oneshot_react --uci
```

To install into Cute Chess: *Engine Manager -> New ->* command =
`python -m engines.oneshot_react --uci`, working directory = the repo root.
Set `UCI_Elo` from the engine options dialog.

### Tests

```bash
pip install -r engines/oneshot_react/requirements.txt
python -m pytest engines/oneshot_react/tests/ -v
```

The suite covers:

- Move generation against four perft positions (starting, Kiwipete, "Position
  3", "Position 5") up to depth 3 — >12k leaf nodes verified.
- Special moves: castling (both sides, blocked / through-check / rights-loss),
  en passant capture & undo, all four promotion targets.
- Game-end detection: Fool's Mate, stalemate, threefold repetition,
  fifty-move rule, insufficient material.
- Engine: mate-in-1 detection, free-capture spotting, no-blunder smoke,
  ELO monotonicity (depth never decreases, blunder rate never increases as
  ELO rises).
- UCI: handshake, options, position parsing (startpos and fen forms), `go
  movetime` / `go depth`, `setoption UCI_Elo` / `Skill Level`.
- SAN/PGN: pawn moves, captures, castling, check / mate suffixes,
  promotions, full PGN export.

55 tests run in well under a second.

---

## Sample positions

See `samples/positions.txt`. A few highlights:

```
# Mate in 1: White to play (Qa8#).
6k1/5ppp/8/8/8/8/8/4K2Q w - - 0 1

# Kiwipete (tactical middlegame, perft benchmark):
r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1

# K + R vs K endgame:
8/8/8/8/8/4k3/8/R3K3 w - - 0 1
```

---

## How each context source influenced the build

| Context source                      | Use category | Where it shows up                                                   |
| ----------------------------------- | ------------ | ------------------------------------------------------------------- |
| Lichess source (lichess.org)        | reference    | UI affordances (legal-move dots, promotion modal, side-flip).       |
| Stockfish (official-stockfish)      | reference    | UCI command grammar; PSQT shape; iterative-deepening structure.     |
| python-chess docs                   | reference    | Public API ergonomics (`Board`, `Move`, `Square`); we reimplement.  |
| Stockfish UCI & Commands docs       | adapt        | Literal protocol grammar in `uci/protocol.py`.                      |
| CuteChess GUI                       | reference    | Confirmed compatibility target for the UCI process.                 |
| Perft results (chessprogramming.org)| adapt        | Numerical expectations in `tests/test_perft.py`.                    |

**Built from scratch:** everything in `core/`, `engine/`, `ui/`, and the
ReAct reasoning trace concept itself.
**Adapted:** UCI command names/semantics; perft expected node counts.
**Wrapped/integrated:** none — no third-party engine code is loaded.
**Inspired by:** UI patterns from Lichess; PSQT values follow the spirit
of the "Simplified Evaluation Function" (Tomasz Michniewski).

---

## Tradeoffs & known limitations

- **Speed**: Pure Python is ~50-100x slower than a C engine. Effective
  search depth is 4-7 in reasonable time, capping practical strength at
  roughly 1700-1800 human-equivalent at the highest ELO setting.
- **No opening book** — the engine calculates from scratch every move.
- **No endgame tablebases** — endgames rely solely on evaluation.
- **No pondering / multi-PV / `ponder` UCI option.**
- **Time management is basic** — ~2.5 % of remaining time + 50 % of the
  increment per move. No safety margin tuning.
- **Threefold-repetition** is detected but the engine doesn't actively seek
  or avoid draws based on contempt.
- **Single-process web UI**: one game at a time, not multi-user.

These are conscious choices to keep the codebase readable in one sitting.
The architecture is clean enough that any of them could be plugged in
without changing other layers.
