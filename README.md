# PointChess Engine

A complete chess engine with browser-based UI, UCI protocol support, and adjustable ELO strength (400-2400).

## Quick Start

```bash
# Start the web UI
python -m oneshot_nocontext_engine

# Open http://localhost:8000 in your browser

# Or run in UCI mode (for chess GUIs like Arena, CuteChess, etc.)
python -m oneshot_nocontext_engine --uci
```

No external dependencies required — pure Python 3.

## Architecture

```
oneshot_nocontext_engine/
├── core/               # Chess rules & board representation
│   ├── types.py        # Color, PieceType, Piece, Move, Square
│   └── board.py        # Board state, legal move generation, FEN/PGN
├── search/             # Engine search & evaluation
│   ├── evaluation.py   # Position evaluation (material, PST, structure)
│   ├── engine.py       # Alpha-beta search with iterative deepening
│   └── elo.py          # ELO-to-engine-parameters mapping
├── uci/                # UCI protocol layer
│   └── protocol.py     # UCI command handling
├── ui/                 # Browser-based interface
│   ├── server.py       # HTTP server & JSON API
│   └── static/         # HTML/CSS/JS frontend
├── tests/              # Automated test suite
└── __main__.py         # Entry point
```

## Engine Design

### Search
- **Minimax with alpha-beta pruning** — standard game tree search
- **Iterative deepening** — searches depth 1, 2, 3... up to the limit, using the best move from shallower searches to improve move ordering
- **Quiescence search** — extends search on capture sequences to avoid the horizon effect
- **Transposition table** — caches evaluated positions to avoid redundant work
- **Move ordering** — TT move first, then captures (MVV-LVA), promotions, killer moves

### Evaluation
- **Material balance** — standard piece values (P=100, N=320, B=330, R=500, Q=900)
- **Piece-square tables** — positional bonuses for each piece type, with separate king tables for middlegame vs endgame
- **Pawn structure** — penalties for doubled/isolated pawns, bonuses for passed pawns
- **Mobility** — number of squares available to pieces
- **King safety** — pawn shield bonus in the middlegame
- **Bishop pair** — 30cp bonus for having both bishops

## ELO Scaling

The ELO slider (400-2400) maps to four engine parameters:

| ELO Range | Depth | Eval Noise | Blunder % | Time/Move |
|-----------|-------|------------|-----------|-----------|
| 400-800   | 1-2   | ±200cp     | 25-12%    | 0.5-1.0s  |
| 800-1200  | 2-3   | ±100cp     | 12-6%     | 1.0-2.0s  |
| 1200-1600 | 3-4   | ±50cp      | 6-2%      | 2.0-4.0s  |
| 1600-2000 | 4-5   | ±20cp      | 2-0.5%    | 4.0-7.0s  |
| 2000-2400 | 5-7   | ~0cp       | ~0%       | 7.0-10.0s |

**How blunders work:** Instead of picking random moves, the engine evaluates the top 5 moves and picks from the 2nd-5th best, weighted toward better options. This produces human-like mistakes rather than absurd blunders.

Parameters interpolate linearly within brackets. See `oneshot_nocontext_engine/search/elo.py` for the exact formulas.

## UCI Support

The engine implements the UCI protocol and can be loaded into any UCI-compatible GUI:

```
uci              → identifies engine, lists options
isready          → synchronization
ucinewgame       → clears transposition table
position         → set position (startpos/FEN + moves)
go               → search (supports depth, movetime, wtime/btime)
stop             → stop searching
quit             → exit
setoption        → set Skill Level or UCI_Elo (400-2400)
```

Example UCI session:
```
> uci
id name PointChess
id author PointChess Team
option name Skill Level type spin default 1500 min 400 max 2400
uciok
> isready
readyok
> position startpos moves e2e4 e7e5
> go depth 5
info depth 5 nodes 12345 time 234 nps 52778 score cp 25
bestmove d2d4
```

## Web UI Features

- Click-to-move with legal move indicators
- Choose side (white/black)
- Adjustable engine ELO slider
- Move list display
- Check/checkmate/stalemate detection
- Pawn promotion dialog
- Undo moves
- Resign
- Export PGN
- Responsive design

## Testing

```bash
# Run all tests
python -m pytest oneshot_nocontext_engine/tests/ -v

# Run specific test files
python -m pytest oneshot_nocontext_engine/tests/test_board.py -v   # Move generation, special rules
python -m pytest oneshot_nocontext_engine/tests/test_engine.py -v   # Search, evaluation, ELO
python -m pytest oneshot_nocontext_engine/tests/test_uci.py -v      # UCI protocol
```

The test suite includes:
- FEN parsing and roundtrip
- Legal move generation (starting position = 20 moves)
- Special moves: en passant, castling (both sides), promotion
- Castling restrictions (through check, in check, rights lost)
- Check, checkmate, stalemate detection
- Insufficient material, fifty-move rule
- Move undo (including special moves)
- **Perft tests** — verifying move generation against known node counts:
  - Starting position: depth 1=20, depth 2=400, depth 3=8902
  - Kiwipete position: depth 1=48, depth 2=2039
- SAN and PGN generation
- Engine search (mate-in-1, captures, no blunders)
- ELO settings validation
- UCI command handling

## Known Limitations

- **Performance:** Pure Python is ~100x slower than C/C++ engines. Search depth is limited to ~5-7 plies in reasonable time. At maximum ELO the engine plays at roughly 1600-1800 human strength.
- **Opening book:** No opening book — the engine calculates from scratch every move.
- **Endgame tablebases:** Not supported — endgame play relies solely on evaluation.
- **Threefold repetition:** Detected but the engine doesn't actively avoid/seek draws.
- **Time management:** Basic time allocation (2% of remaining time); no pondering.

## Sample Positions

Test the engine with these FEN strings:

```
# Scholar's mate setup (White to play Qxf7#)
r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4

# Mate in 1 (Qh7#)
6k1/5ppp/8/8/8/8/8/4K2Q w - - 0 1

# Complex middlegame (Kiwipete)
r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1

# Endgame: King + Rook vs King
8/8/8/8/8/4k3/8/R3K3 w - - 0 1
```
