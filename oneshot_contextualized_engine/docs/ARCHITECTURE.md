# Architecture

This is a deliberately small codebase. There are four packages and they
form a strict dependency DAG:

```
   tests ──────────────┐
                       ▼
   uci  ─────────►  engine  ◄───── web
                       │
                       └──► python-chess (external)
```

* `engine/` is **pure**: it never reads stdin, opens a socket, or touches
  the filesystem. Everything in here is unit-testable in isolation.
* `uci/` is the only place we speak the UCI wire protocol. It runs the
  search in a worker thread so `stop` and `isready` are responsive while
  searching.
* `web/` is the only place we speak HTTP. It depends on `engine.engine.Engine`
  and `engine.game.Game`; it knows nothing about UCI.
* `tests/` import from `engine/` and `uci/` only — never from `web/`.

## Module map

| Module | Lines (approx) | What lives here |
|---|---|---|
| `engine/game.py` | ~110 | Wrapper around `chess.Board` adding history, undo, PGN export, status text. |
| `engine/evaluation.py` | ~270 | Tapered eval: PeSTO PSTs + material, mobility, king safety, pawn structure, bishop pair, rook on (semi-)open file, side-to-move tempo. |
| `engine/tt.py` | ~55 | Transposition table; depth-preferred replacement; capacity-bounded eviction. |
| `engine/ordering.py` | ~80 | TT-move > promotions > MVV-LVA > killers > history. |
| `engine/search.py` | ~280 | ID negamax + α-β + PVS + LMR + null-move + quiescence. Public `Searcher.search()` returns a `SearchInfo`. |
| `engine/elo.py` | ~95 | Tabulated `(ELO -> StrengthConfig)` mapping with linear interpolation. |
| `engine/opening_book.py` | ~75 | Hand-rolled book of common openings, keyed by Zobrist hash. |
| `engine/engine.py` | ~110 | High-level facade: book → search → MultiPV pick with noise/blunder. |
| `uci/protocol.py` | ~210 | UCI command loop, options, `go` time-management, search-thread management. |
| `web/server.py` | ~140 | Flask app + REST endpoints. Single-game in-process state. |
| `web/static/app.js`, `style.css`, `templates/index.html` | ~250 | Click-to-move UI, no external CDN. |
| `tests/*` | ~280 | perft, rules, search, UCI, ELO. |

## Why python-chess?

The supplied context lists `python-chess` first, and the prompt tells us
to "integrate cleanly rather than duplicate" reusable infrastructure.
Move generation is the hard part of a chess engine to get right:
[Perft Results](https://www.chessprogramming.org/Perft_Results) catches
even subtle move-gen bugs by node-counting deep trees, and writing your
own bug-free generator is a multi-week project.

We use python-chess for:

* **`chess.Board`** — pseudo-legal and legal move generation, in-check
  detection, FEN/SAN/UCI parsing, repetition and 50-move detection,
  insufficient-material detection.
* **`chess.polyglot.zobrist_hash`** — TT key.
* **`chess.pgn`** — PGN export.

Everything else is hand-rolled in this repo.

## Threading

`uci/protocol.py` runs the search on a daemon worker thread. The main
thread stays in a blocking `for line in stdin` loop so `stop` (which
calls `engine.stop()` to flip a flag the searcher polls every 1024 nodes)
and `isready` (which is a no-op write) cannot be starved.

The web server uses Flask's threaded development server. Multiple HTTP
requests can arrive concurrently, but `Engine.choose_move` takes a lock
so two `move` requests can never enter the searcher at the same time.

## Extension hooks

* **Polyglot books**: replace `engine.opening_book.lookup` with a wrapper
  around `chess.polyglot.MemoryMappedReader`; no caller change.
* **Endgame tablebases**: drop a Syzygy probe at the top of
  `Searcher._negamax` for ≤6-piece positions.
* **Stronger eval**: swap PeSTO PSTs for NNUE; the rest of search is
  unaffected because eval is queried only through `engine.evaluation.evaluate`.
