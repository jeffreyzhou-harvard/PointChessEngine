# Architecture

## Layered design

```
+-----------------------------------------------+
|                      ui/                      |   <- HTTP + browser
+-----------------------------+-----------------+
|             uci/            |                 |   <- UCI process
+-----------------------------+                 |
|                  engine/                      |   <- search, eval, ELO
+-----------------------------------------------+
|                   core/                       |   <- rules, board, FEN
+-----------------------------------------------+
```

Strict downward dependency: `ui/` and `uci/` both call `engine/`, which calls
`core/`. `core/` knows nothing about anything above it.

## Module map

| Module                       | Responsibility                                                |
| ---------------------------- | ------------------------------------------------------------- |
| `core/pieces.py`             | `Color`, `PieceType`, `Piece`, FEN <-> piece char tables       |
| `core/square.py`             | Coordinates, algebraic conversion                             |
| `core/move.py`               | `Move` dataclass + UCI string parsing                         |
| `core/fen.py`                | FEN parser / serializer (no `Board` dependency)               |
| `core/movegen.py`            | Pseudo-legal + legal move generation, attack detection        |
| `core/board.py`              | Board state, make/unmake, repetition, draw rules, perft       |
| `core/notation.py`           | SAN + PGN export                                              |
| `engine/psqt.py`             | Piece-square tables + piece value table                       |
| `engine/evaluator.py`        | Static evaluation (material + PSQT + structure + safety)      |
| `engine/transposition.py`    | TT entry & store                                              |
| `engine/strength.py`         | ELO -> `StrengthSettings` mapping                             |
| `engine/reasoning.py`        | Optional Thought/Action/Observation traces of engine choices  |
| `engine/search.py`           | Alpha-beta + iter. deepening + quiescence + ordering          |
| `uci/protocol.py`            | Stateful UCI command dispatcher (threaded search)             |
| `ui/server.py`               | `ThreadingHTTPServer` + JSON API + game session state         |
| `ui/static/*`                | HTML/CSS/JS front-end                                         |
| `__main__.py`                | Entry point: web UI by default, `--uci` switches to UCI mode  |

## Data flow: a single human move

```
browser  ->  POST /api/move {uci}                ui/server.py
              session.play_human_move ----------> core/board.make_move
              session.board_state    ----------> core (legal_moves, fen)
              JSON                   ---------->  browser

browser  ->  POST /api/engine_move
              session.play_engine_move ---------> engine/search.search_and_choose
                                                       ├── core/movegen.legal_moves (per node)
                                                       ├── engine/evaluator.evaluate (leaves)
                                                       ├── engine/transposition.TranspositionTable
                                                       └── engine/reasoning.ReasoningTrace
              core/board.make_move  -----------> apply chosen move
              JSON {state, move, san, reasoning} ->  browser
```

## Concurrency model

- Web UI: one game, one `GameSession`, mutex-protected. Single-tab use.
- UCI: search runs in a worker thread so `stop` from the GUI is responsive.

## Why not bitboards?

In pure Python the per-bit-twiddle overhead negates bitboard speedups. The
mailbox is also dramatically easier to debug. If the engine is ever ported
to Rust/C/PyPy, swapping in bitboards is a localized change confined to
`core/movegen.py` and `core/board.py`.
