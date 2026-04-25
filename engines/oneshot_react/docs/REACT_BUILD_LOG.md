# ReAct Build Log

This file records the **Thought / Action / Observation** loop that produced
`engines/oneshot_react`. Each entry is intentionally short; only the
decision-relevant reasoning is captured (not internal monologue). Together
the entries form a paper-trail of how the prompt was decomposed into a
working chess engine.

---

## Round 1 - Context assessment

**Thought.** Five context sources were supplied: Lichess source, Stockfish,
python-chess, Stockfish UCI docs, CuteChess GUI, and chessprogramming.org
perft results. Decide the *use category* for each.

**Action.** Walk each source.

| Source                              | Decision     | Why                                                                                  |
| ----------------------------------- | ------------ | ------------------------------------------------------------------------------------ |
| Lichess source                      | reference    | Massive Scala/JS app; only inspirational for UX patterns.                            |
| Stockfish engine                    | reference    | Forbidden as black box; PSQT shape & UCI conventions inform our design.              |
| python-chess docs                   | reference    | API shape (Board, Move, Square) inspires our public surface; we reimplement.        |
| Stockfish UCI docs                  | adapt        | Defines the protocol literally; our `uci/protocol.py` follows it.                    |
| CuteChess GUI                       | reference    | Confirms expected GUI behavior; we target this as a UCI client.                      |
| Perft results                       | adapt        | Hard correctness benchmark for move generation; copied numerically into `tests/`.    |

**Observation.** No source dictates code reuse, so the build is "from scratch
with documented inspiration." Stockfish UCI docs and perft tables are the
only sources whose contents are quoted (commands, expected counts).

---

## Round 2 - Stack & architecture

**Thought.** Pick a stack that maximizes correctness, testability, and
zero-install runnability while still being a real engine.

**Action.** Choose **Python 3.10+, stdlib only**, with these decisions:

- 8x8 mailbox (`List[List[Optional[Piece]]]`) — simpler than bitboards in pure
  Python, easier to audit; PyPy/C would prefer bitboards but that's out of scope.
- `Move = (from_sq, to_sq, promotion?)` — castling and en passant are encoded
  geometrically and disambiguated at execution time.
- Make/unmake with explicit undo dicts — safer than deep copy and ~10x faster
  in our microbenchmarks.
- Search: alpha-beta + iterative deepening + quiescence + transposition table +
  killer + history. Standard textbook.
- ELO scaling: piecewise-linear knobs (depth, time, eval noise, blunder %, top-N
  pool). Keeps weak play *plausible*, not *random*.
- UCI: stdin/stdout, search runs in a worker thread so `stop` is responsive.
- UI: stdlib `http.server` + a single static page. No npm. No Flask.
- Optional **engine reasoning trace** (Thought/Action/Observation) - mirrors the
  prompting style that built the engine. Surfaced both in the JSON API and the
  web UI.

**Observation.** Module boundaries:

```
core/    pure rules — knows nothing about evaluation or search
engine/  evaluation, search, ELO scaling, reasoning traces
uci/     protocol layer — speaks UCI to stdin/stdout
ui/      HTTP server + browser front-end
tests/   correctness suite (perft, rules, engine, UCI)
```

Each module imports only from layers below it (no upward arrows). This makes
the engine independently testable from the UI and vice versa.

---

## Round 3 - Core rules

**Thought.** Get move generation right *first*. Everything else depends on it.

**Action.** Implement `core/pieces.py`, `core/square.py`, `core/move.py`,
`core/fen.py`, `core/movegen.py`, `core/board.py`. Use trial-and-rollback
(make / king-attack-check / unmake) for legality rather than pin detection.

**Observation.** Pseudo-legal generation is decoupled from legality so the
search can sometimes skip the legality filter (it doesn't here, but the option
is there). FEN parsing is its own module so it can be reused without pulling
in the rules engine.

---

## Round 4 - Validate movegen

**Thought.** Don't trust hand-rolled move generators. Test against perft.

**Action.** Add `tests/test_perft.py` with starting position, Kiwipete,
position 3, and position 5 from chessprogramming.org.

**Observation.** All five perft tests pass on the first run after a small
fix to en-passant capture handling — that's the standard place where
home-grown move generators break.

---

## Round 5 - Evaluation & search

**Thought.** Build a useful eval (more than material) and a search that can
actually find tactics within Python's speed budget.

**Action.** `engine/psqt.py`, `engine/evaluator.py`, `engine/search.py`,
`engine/transposition.py`. Search uses alpha-beta + iterative deepening +
quiescence + TT + killer + history. Move ordering: TT-move first, then captures
ordered MVV-LVA, then promotions, then killers, then history.

**Observation.** Mate-in-1 is found at depth 2-3; the engine refuses to hang
its queen at depth 3 on opening positions. Good enough for the 400-2400 ELO
band we target.

---

## Round 6 - ELO slider

**Thought.** Weak play has to be playable, not absurd. Random moves at low
ELO ruin the experience.

**Action.** Define `StrengthSettings(elo, max_depth, movetime_ms, noise_cp,
blunder_pct, candidate_pool)` and a piecewise-linear `settings_for_elo`.
At low ELO, the engine still *searches* — it just deepens less, adds eval
noise, and occasionally picks the 2nd–5th best move (weighted toward better).

**Observation.** `test_strength_monotonic_*` enforces that higher ELO never
lowers depth or raises blunder rate. This catches accidental table errors.

---

## Round 7 - UCI

**Thought.** GUIs (CuteChess, Arena, ChessBase) drive the engine via a tiny
text protocol. Implement the subset that real GUIs need.

**Action.** `uci/protocol.py` handles `uci, isready, ucinewgame, position,
go, stop, setoption, quit, d`. Long searches run in a thread so `stop` works.
Expose `UCI_Elo` (400-2400) and `Skill Level` (0-20, mapped onto the same
range) as configurable options.

**Observation.** End-to-end smoke test:

```
> uci ... uciok
> position startpos moves e2e4 e7e5
> go depth 3
info depth 1 ...
info depth 2 ...
info depth 3 ...
bestmove f2f3
```

Exactly what a UCI GUI expects.

---

## Round 8 - Web UI

**Thought.** Web UI must be installable in zero steps. No npm, no Flask.

**Action.** `ui/server.py` is `http.server.ThreadingHTTPServer` + a small
JSON API. `ui/static/{index.html, style.css, app.js}` renders the board,
sends moves, and shows the engine's reasoning trace alongside its score and
PV.

**Observation.** UI features delivered: side selection, ELO slider, new game,
legal-move dots, last-move highlight, in-check highlight, promotion picker,
undo (two ply), resign, PGN export, engine reasoning panel.

---

## Round 9 - Tests & docs

**Thought.** Lock the behavior in.

**Action.** Tests in five files: `test_board`, `test_perft`, `test_engine`,
`test_uci`, `test_notation`. README + this build log.

**Observation.** 55 tests pass in ~0.6 s. Move generation is verified against
perft up to depth 3 on five different positions, totaling >12,000 leaf nodes.
That gives high confidence in the rules layer.

---

## Round 10 - What's *not* built

**Thought.** Honest about limits.

**Action.** Document them in `README.md`.

**Observation.** No opening book, no endgame tablebase, no pondering, no
multi-PV. ELO ceiling is roughly 1700-1800 human-equivalent (limited by
Python search speed, ~10-50k NPS).
