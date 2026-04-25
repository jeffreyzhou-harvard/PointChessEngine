# Engine design

## Search

`engine/search.py` implements iterative-deepening principal-variation
search. Each iteration calls `_root_search`, which runs negamax with
alpha-beta over the root move list, ordered by the previous iteration's
best move first. Iterative deepening lets us return *some* move
immediately if we run out of time.

### Pruning / extension techniques

| Technique | Where | Trigger |
|---|---|---|
| **Transposition table** | top of `_negamax` | always (depth-preferred replacement) |
| **Null-move pruning** | before generating moves | `depth ≥ 3`, not in check, side has non-pawn material, beta < mate |
| **Late-move reductions (LMR)** | inside the move loop | quiet, non-check, non-PV, after the 4th move |
| **Principal-variation search (PVS)** | inside the move loop | every move after the first uses a null window, re-search if it raises alpha |
| **Quiescence search** | leaves | captures + promotions + (if in check) all moves |
| **Killer moves** | move ordering | per-ply, two slots |
| **History heuristic** | move ordering | quiet moves only |
| **MVV-LVA** | move ordering | captures and en-passants |

### Score conventions

`evaluate()` and `_negamax()` both return centipawn scores from the
side-to-move's perspective. A score `≥ MATE_THRESHOLD` (= 999_000) means
"we mate the opponent in `MATE - score` plies"; symmetric for negative.
We *only* look at the absolute value's distance from `MATE` to derive
the mate count for UCI's `score mate <n>` output.

## Evaluation

`engine/evaluation.py` is a classical tapered eval:

```
score = (mg * phase + eg * (24 - phase)) / 24
```

`phase` is the sum of piece weights `{N,B:1, R:2, Q:4}` over both sides,
clamped to 24 (the starting position). It interpolates smoothly between
middlegame and endgame piece-square tables.

### Terms (in centipawns, white-positive before STM flip)

* **Material + PSTs**: PeSTO mg/eg values and tables
* **Pawn structure**:
  * doubled (-12 cp per extra pawn on the file)
  * isolated (-14 cp per pawn on a no-friendly-neighbor file)
  * passed (+5..100 cp depending on advancement rank)
* **Bishop pair**: +30 cp
* **Rook on (semi-)open file**: +20 cp open, +10 cp semi-open
* **Mobility**: 2 cp per pseudo-legal move (excluding the king)
* **King safety**: -8 cp per missing pawn-shield square in front of the
  king, -3 cp per attacker in the king's 3×3 zone
* **Tempo**: +10 cp for the side to move

### Why PeSTO?

PeSTO's tables are public-domain, fairly strong out of the box, and well
known in the chess-programming community. The Stockfish source we were
asked to study uses far more elaborate tables, but PeSTO gets us within a
few hundred ELO of "real" classical eval with a tiny static cost. It is
a deliberate tradeoff: we get most of eval's strength for almost none of
its complexity.

## Limits

* Single-threaded. The TT is a `dict`; sharing it across threads would
  require a lock or a fixed-size array of slots. We don't bother.
* No NNUE, no aspiration windows, no SEE. SEE in particular would let
  the move orderer prune obviously-bad captures from quiescence.
* No Syzygy / EGTB probing.
