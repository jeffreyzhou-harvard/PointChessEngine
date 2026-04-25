"""Engine search.

The single contract that UCI and the UI both consume. Anything that
respects ``SearchLimits`` and returns a ``SearchResult`` can stand in
for ``Engine``.

Search flow
-----------

1. **Iterative deepening.** ``search`` runs negamax at depth 1, 2, 3,
   ... up to the limit. The result of each completed depth is kept,
   so if time runs out mid-depth we still return the best move from
   the deepest *completed* iteration. This also primes the TT and
   PV for ordering at the next depth.

2. **Negamax with alpha-beta.** A single recursive function;
   negation handles the side flip. Ordered legal moves are tried in
   turn; a beta cutoff bails out as soon as we can prove the move
   is too good for the opponent to allow.

3. **Move ordering.** At each non-leaf node we order moves so that
   alpha-beta has the best chance to prune:
     - first: the principal variation / TT best move (if any)
     - then: captures sorted by MVV-LVA
       (most valuable victim, least valuable attacker)
     - then: promotions
     - then: quiet moves (insertion order)

4. **Quiescence search.** At horizon (depth == 0) we don't evaluate
   immediately; instead we play out captures and promotions until
   the position is "quiet". This avoids the horizon effect (e.g.
   capturing a defended pawn just before the depth runs out and
   missing the recapture). When in check, quiescence searches ALL
   legal moves rather than just captures.

5. **Transposition table.** A simple always-replace dict keyed on
   ``Board.position_key()``. Each entry stores depth, score, the
   best move found, and a flag (EXACT / LOWER / UPPER bound). On
   re-visiting a position that was searched at >= the current
   depth, we reuse the score (subject to bound semantics) and
   always use the stored move first for ordering.

6. **Time / stop management.** An internal ``_TimeUp`` exception
   lets the search bail out cleanly mid-tree. The iterative
   deepening loop catches it and returns the best result from the
   last depth that finished.

Mate scoring convention
-----------------------

A "mate in N plies from this node" returns ``MATE_VALUE - ply``
in negamax convention; the side to move losing such a position
returns ``-MATE_VALUE + ply``. Subtracting the ply makes shallower
mates score higher in absolute value, so the engine always picks
the FASTEST mate.

The reverse mapping (score -> mate-in-moves used in
``SearchResult.mate_in``) is in ``_score_to_mate_in``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import IntEnum
from time import perf_counter
from typing import Optional

from ..core.board import Board
from ..core.move import Move
from ..core.types import Color, PieceType
from .elo import MAX_ELO, MIN_ELO, EloConfig, config_from_elo
from .evaluation import MATE_SCORE, evaluate


# Anything in the [MATE_THRESHOLD, MATE_SCORE] band is treated as a
# mate score; the gap covers reasonable search depths well.
_MATE_THRESHOLD = MATE_SCORE - 1000

# How often (in node visits) to check the time / stop flag. Lower
# values give more responsive stops at the cost of overhead.
_TIME_CHECK_INTERVAL = 256


# ---------------------------------------------------------------------------
# limits / result types (public)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SearchLimits:
    """A subset of UCI ``go`` arguments. See module docstring of stage 1."""

    depth: Optional[int] = None
    movetime_ms: Optional[int] = None
    wtime_ms: Optional[int] = None
    btime_ms: Optional[int] = None
    winc_ms: Optional[int] = None
    binc_ms: Optional[int] = None
    infinite: bool = False

    def is_unbounded(self) -> bool:
        return (
            self.depth is None
            and self.movetime_ms is None
            and self.wtime_ms is None
            and self.btime_ms is None
            and not self.infinite
        )


@dataclass(frozen=True, slots=True)
class SearchResult:
    """What the engine returns at the end of a search.

    ``best_move`` is ``None`` only when the position has no legal
    moves at all (mate or stalemate); UCI/UI callers should special-
    case that and not feed ``None`` back into ``Board.make_move``.
    """

    best_move: Optional[Move] = None
    score_cp: Optional[int] = None      # centipawns from side-to-move's POV
    mate_in: Optional[int] = None       # +N: we mate in N moves; -N: we are mated
    depth: int = 0
    nodes: int = 0
    time_ms: int = 0
    pv: tuple[Move, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# transposition table
# ---------------------------------------------------------------------------


class _TTFlag(IntEnum):
    EXACT = 0
    LOWER = 1     # score is a lower bound (caused a beta cutoff)
    UPPER = 2     # score is an upper bound (alpha was never raised)


@dataclass(slots=True)
class _TTEntry:
    depth: int
    score: int
    flag: _TTFlag
    best_move: Optional[Move]


class _TranspositionTable:
    """Always-replace dict keyed on position_key.

    A real engine uses a fixed-size hash with replacement policy,
    but for stage 7 a plain dict is correct and simple. ``new_game``
    on the engine clears it.
    """

    __slots__ = ("_data",)

    def __init__(self) -> None:
        self._data: dict[tuple, _TTEntry] = {}

    def lookup(self, board: Board) -> Optional[_TTEntry]:
        return self._data.get(board.position_key())

    def store(
        self,
        board: Board,
        depth: int,
        score: int,
        flag: _TTFlag,
        best_move: Optional[Move],
    ) -> None:
        self._data[board.position_key()] = _TTEntry(depth, score, flag, best_move)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)


# ---------------------------------------------------------------------------
# internal: time control & stop
# ---------------------------------------------------------------------------


class _TimeUp(Exception):
    """Raised by the search to bail out of the current iteration."""


class _Deadline:
    """A monotonic deadline plus a stop-flag holder.

    The engine checks ``Deadline.expired_or_stopped()`` periodically
    and raises ``_TimeUp`` when it returns True. A deadline of None
    means "no time limit"; ``_stop_flag`` is a 1-element list so
    callers can flip it after construction.
    """

    __slots__ = ("_until", "_stop_flag")

    def __init__(self, budget_ms: Optional[int], stop_flag: list[bool]) -> None:
        if budget_ms is None or budget_ms <= 0:
            self._until = None
        else:
            self._until = perf_counter() + budget_ms / 1000.0
        self._stop_flag = stop_flag

    def expired_or_stopped(self) -> bool:
        if self._stop_flag and self._stop_flag[0]:
            return True
        if self._until is not None and perf_counter() >= self._until:
            return True
        return False


# ---------------------------------------------------------------------------
# move ordering
# ---------------------------------------------------------------------------

# Static piece values used purely for MVV-LVA ordering. Kept independent
# of evaluation weights because move ordering doesn't need to be tunable.
_ORDER_PIECE_VALUE = {
    PieceType.PAWN: 100,
    PieceType.KNIGHT: 320,
    PieceType.BISHOP: 330,
    PieceType.ROOK: 500,
    PieceType.QUEEN: 900,
    PieceType.KING: 20_000,
}


def _is_capture(board: Board, move: Move) -> bool:
    """True if ``move`` captures (including en-passant)."""
    if board.piece_at(move.to_sq) is not None:
        return True
    piece = board.piece_at(move.from_sq)
    if (
        piece is not None
        and piece.type is PieceType.PAWN
        and move.to_sq == board.ep_square
    ):
        return True
    return False


def _capture_score(board: Board, move: Move) -> int:
    """MVV - LVA for ordering captures (higher = try first).

    Uses victim*8 - attacker so the queen-takes-pawn (low) scores
    below a pawn-takes-queen (high), as desired.
    """
    attacker = board.piece_at(move.from_sq)
    victim = board.piece_at(move.to_sq)
    if victim is None:
        # En-passant: the captured piece is a pawn.
        victim_v = _ORDER_PIECE_VALUE[PieceType.PAWN]
    else:
        victim_v = _ORDER_PIECE_VALUE[victim.type]
    attacker_v = _ORDER_PIECE_VALUE[attacker.type] if attacker else 0
    return victim_v * 8 - attacker_v


def _order_moves(
    board: Board, moves: list[Move], tt_move: Optional[Move]
) -> list[Move]:
    """TT move first, then captures (MVV-LVA), then promotions, then quiet."""
    if not moves:
        return moves

    captures: list[tuple[int, Move]] = []
    promotions: list[Move] = []
    quiet: list[Move] = []
    tt_first: list[Move] = []

    for m in moves:
        if tt_move is not None and m == tt_move:
            tt_first.append(m)
            continue
        if _is_capture(board, m):
            captures.append((_capture_score(board, m), m))
        elif m.promotion is not None:
            promotions.append(m)
        else:
            quiet.append(m)

    captures.sort(key=lambda x: -x[0])
    return tt_first + [m for _, m in captures] + promotions + quiet


def _order_qmoves(board: Board, moves: list[Move]) -> list[Move]:
    """Same as ``_order_moves`` but expects only tactical moves."""
    captures: list[tuple[int, Move]] = []
    promotions: list[Move] = []
    other: list[Move] = []  # only when in check; legal evasion non-captures
    for m in moves:
        if _is_capture(board, m):
            captures.append((_capture_score(board, m), m))
        elif m.promotion is not None:
            promotions.append(m)
        else:
            other.append(m)
    captures.sort(key=lambda x: -x[0])
    return [m for _, m in captures] + promotions + other


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class Engine:
    """Negamax + alpha-beta + iterative deepening + quiescence + TT,
    with an ELO-driven strength model layered on top.

    Parameters
    ----------
    elo:
        Slider value in ``[MIN_ELO, MAX_ELO]``; clamped silently.
        Drives the per-move config via :func:`config_from_elo`.
    seed:
        Optional RNG seed for the ELO weakening (eval noise + blunder
        selection). ``None`` (the default) uses system entropy, so
        repeated games at the same ELO look different. Pass an int to
        get reproducible weakening; tests do this.
    """

    def __init__(
        self, elo: int = 1500, seed: Optional[int] = None
    ) -> None:
        self._elo = max(MIN_ELO, min(MAX_ELO, int(elo)))
        self._tt = _TranspositionTable()
        self._stop_flag: list[bool] = [False]
        # Per-search counters (reset on each ``search`` call).
        self._nodes = 0
        self._deadline: Optional[_Deadline] = None
        # RNG used solely for ELO weakening (noise + blunder).
        # Search itself is deterministic; the RNG never enters the tree.
        self._seed = seed
        self._random = random.Random(seed)

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------

    @property
    def elo(self) -> int:
        return self._elo

    def set_elo(self, elo: int) -> None:
        """Set strength. Inputs outside ``[MIN_ELO, MAX_ELO]`` are clamped."""
        self._elo = max(MIN_ELO, min(MAX_ELO, int(elo)))

    def set_seed(self, seed: Optional[int]) -> None:
        """Reseed the weakening RNG. ``None`` = system entropy."""
        self._seed = seed
        self._random = random.Random(seed)

    def config(self) -> EloConfig:
        """The :class:`EloConfig` currently driving move selection."""
        return config_from_elo(self._elo)

    def new_game(self) -> None:
        """Drop transposition table & reset RNG. Called between games."""
        self._tt.clear()
        # Reset RNG to original seed so each new game starts identically
        # under a fixed seed. Has no effect when seed=None.
        self._random = random.Random(self._seed)

    # ------------------------------------------------------------------
    # public search
    # ------------------------------------------------------------------

    def search(self, board: Board, limits: SearchLimits) -> SearchResult:
        """Search ``board`` under ``limits`` and return the chosen move.

        Resolution rules:
          - **Limits.** Caller's explicit ``depth`` / ``movetime_ms`` /
            clock fields override the ELO-derived defaults. When no
            limit is given, ``EloConfig.max_depth`` and
            ``EloConfig.movetime_ms`` provide them.
          - **Move selection.** After search completes, the chosen move
            is the negamax-best move *unless* ELO weakening is active
            (``eval_noise_cp > 0`` or ``blunder_pct > 0``), in which
            case :meth:`_apply_elo_weakening` may pick a slightly worse
            top-3 candidate. Forced mates always play the mating move.
          - **No legal moves.** Returns a SearchResult with
            ``best_move=None`` and score 0 (stalemate) or ``-MATE_SCORE``
            (checkmate).
        """
        self._stop_flag[0] = False
        self._nodes = 0
        self._tt.clear()  # fresh TT per search keeps it deterministic

        legal = board.legal_moves()
        if not legal:
            # Surface terminal positions through the same channel as
            # in-tree mates: ``mate_in=0`` means "we are mated right
            # now" (no move can save it); stalemate is a bare
            # ``score_cp=0`` with no move. ``best_move`` is ``None``
            # in both cases so callers can detect the terminal state
            # without inspecting the score.
            if board.is_check():
                return SearchResult(
                    best_move=None, score_cp=None, mate_in=0,
                    depth=0, nodes=0,
                )
            return SearchResult(
                best_move=None, score_cp=0, mate_in=None,
                depth=0, nodes=0,
            )

        cfg = config_from_elo(self._elo)
        weakening_active = (
            cfg.eval_noise_cp > 0 or cfg.blunder_pct > 0
        )

        budget_ms = self._allocate_time(board.turn, limits, cfg)
        self._deadline = _Deadline(budget_ms, self._stop_flag)

        if limits.depth is not None:
            max_depth = limits.depth
        else:
            max_depth = cfg.max_depth

        start = perf_counter()
        # Track the deepest iteration that finished. ``last_scored``
        # holds (move, score) for every root move at that depth, which
        # ELO weakening needs.
        last_scored: list[tuple[Move, int]] = [(legal[0], 0)]
        last_best_score = 0
        last_best_move = legal[0]
        last_depth = 0

        for depth in range(1, max_depth + 1):
            try:
                scored, root_score, root_move = self._root_search(
                    board, depth, full_window=weakening_active
                )
            except _TimeUp:
                break
            last_scored = scored
            last_best_score = root_score
            last_best_move = root_move
            last_depth = depth
            # Found a forced mate -- no point searching deeper.
            if abs(root_score) >= _MATE_THRESHOLD:
                break

        elapsed_ms = int((perf_counter() - start) * 1000)

        chosen_move, chosen_score = self._apply_elo_weakening(
            last_scored, last_best_move, last_best_score, cfg
        )

        # PV starts from the move the engine actually plays. If we
        # blundered off the principal variation, the PV after that
        # single ply comes from the TT for whatever the chosen move
        # leads into.
        if chosen_move == last_best_move:
            pv = self._extract_pv(board, last_depth)
        else:
            pv = [chosen_move]
            board.make_move(chosen_move)
            try:
                pv.extend(self._extract_pv(board, max(0, last_depth - 1)))
            finally:
                board.unmake_move()

        mate_in = self._score_to_mate_in(chosen_score)
        return SearchResult(
            best_move=chosen_move,
            score_cp=None if mate_in is not None else chosen_score,
            mate_in=mate_in,
            depth=last_depth,
            nodes=self._nodes,
            time_ms=elapsed_ms,
            pv=tuple(pv),
        )

    def stop(self) -> None:
        """Cooperative stop. Safe to call from any thread."""
        self._stop_flag[0] = True

    # ------------------------------------------------------------------
    # root search
    # ------------------------------------------------------------------

    def _root_search(
        self, board: Board, depth: int, full_window: bool = False
    ) -> tuple[list[tuple[Move, int]], int, Move]:
        """Run negamax at the root.

        Returns ``(scored, best_score, best_move)`` where ``scored`` is
        ``[(move, score), ...]`` for every root move in search order.

        Two modes:

        - ``full_window=False`` (default): use alpha-beta at the root
          for the standard speed boost. Non-best moves return their
          *upper bound* on the true score, which is fine because the
          engine only ever plays the best move at full strength.

        - ``full_window=True``: search every root move with the full
          ``[-MATE_SCORE-1, +MATE_SCORE+1]`` window so the returned
          score is exact. ELO weakening NEEDS this, otherwise the
          "pick a top-3 move" blunder degenerates to random because
          all non-best scores collapse to ``alpha = best_score``.
          Internal nodes still use alpha-beta either way; only root
          cutoffs are sacrificed. Branching factor ~30 at root means
          the slowdown is tolerable, especially because weakening
          implies a low ELO and therefore a shallow depth cap.
        """
        INF = MATE_SCORE + 1

        tt_entry = self._tt.lookup(board)
        tt_move = tt_entry.best_move if tt_entry is not None else None

        legal = board.legal_moves()
        ordered = _order_moves(board, legal, tt_move)

        scored: list[tuple[Move, int]] = []
        best_score = -INF
        best_move = ordered[0]
        alpha = -INF
        beta = INF

        for move in ordered:
            board.make_move(move)
            try:
                if full_window:
                    score = -self._negamax(board, depth - 1, -INF, INF, ply=1)
                else:
                    score = -self._negamax(
                        board, depth - 1, -beta, -alpha, ply=1
                    )
            finally:
                board.unmake_move()

            scored.append((move, score))
            if score > best_score:
                best_score = score
                best_move = move
            if not full_window and score > alpha:
                alpha = score

        self._tt.store(board, depth, best_score, _TTFlag.EXACT, best_move)
        return scored, best_score, best_move

    # ------------------------------------------------------------------
    # ELO weakening
    # ------------------------------------------------------------------

    def _apply_elo_weakening(
        self,
        scored: list[tuple[Move, int]],
        best_move: Move,
        best_score: int,
        cfg: EloConfig,
    ) -> tuple[Move, int]:
        """Pick the move the engine actually plays.

        Strict rules:

          1. **Don't sabotage forced mates.** If the engine has found
             mate, play the mating move regardless of ELO. This is the
             one paternalistic rule -- a "weak" engine that misses
             mate-in-1 feels broken, not human.
          2. **No-op at full strength.** When both noise and blunder
             are zero, return the negamax-best move untouched. The
             search is already deterministic; weakening must be too.
          3. **Apply jitter, then maybe blunder.** Per move, add
             uniform noise in ``[-eval_noise_cp, +eval_noise_cp]``.
             Re-sort by jittered score. With probability
             ``blunder_pct``, sample one of the top 3 with weights
             ``[3, 2, 1]`` (so the best is still most likely);
             otherwise pick the new top.

        Returns ``(chosen_move, chosen_score)`` where ``chosen_score``
        is the move's true (unjittered) search score.
        """
        if best_score >= _MATE_THRESHOLD:
            return best_move, best_score
        if cfg.eval_noise_cp == 0 and cfg.blunder_pct <= 0:
            return best_move, best_score
        if not scored:
            return best_move, best_score

        rng = self._random

        if cfg.eval_noise_cp > 0:
            n = cfg.eval_noise_cp
            jittered: list[tuple[int, Move]] = [
                (s + rng.randint(-n, n), m) for m, s in scored
            ]
        else:
            jittered = [(s, m) for m, s in scored]
        jittered.sort(key=lambda x: -x[0])

        if cfg.blunder_pct > 0 and rng.random() < cfg.blunder_pct:
            top_k = jittered[: min(3, len(jittered))]
            weights = [3, 2, 1][: len(top_k)]
            picked_move = rng.choices(top_k, weights=weights, k=1)[0][1]
        else:
            picked_move = jittered[0][1]

        # Recover the chosen move's true (unjittered) score.
        chosen_score = next(s for m, s in scored if m == picked_move)
        return picked_move, chosen_score

    # ------------------------------------------------------------------
    # negamax with alpha-beta
    # ------------------------------------------------------------------

    def _negamax(
        self, board: Board, depth: int, alpha: int, beta: int, ply: int
    ) -> int:
        self._nodes += 1
        if self._nodes % _TIME_CHECK_INTERVAL == 0:
            if self._deadline is not None and self._deadline.expired_or_stopped():
                raise _TimeUp()

        # Draw by insufficient material: equal to a draw score regardless
        # of search depth. (Stalemate/checkmate fall out of the no-moves
        # branch below.)
        if board.is_insufficient_material():
            return 0

        original_alpha = alpha

        # TT probe.
        tt_entry = self._tt.lookup(board)
        tt_move: Optional[Move] = None
        if tt_entry is not None:
            tt_move = tt_entry.best_move
            if tt_entry.depth >= depth:
                if tt_entry.flag is _TTFlag.EXACT:
                    return tt_entry.score
                if (
                    tt_entry.flag is _TTFlag.LOWER
                    and tt_entry.score >= beta
                ):
                    return tt_entry.score
                if (
                    tt_entry.flag is _TTFlag.UPPER
                    and tt_entry.score <= alpha
                ):
                    return tt_entry.score

        if depth <= 0:
            return self._quiescence(board, alpha, beta, ply)

        legal = board.legal_moves()
        if not legal:
            if board.is_check():
                return -MATE_SCORE + ply       # mated; prefer slower mates
            return 0                           # stalemate

        ordered = _order_moves(board, legal, tt_move)
        best_score = -MATE_SCORE - 1
        best_move: Optional[Move] = None

        for move in ordered:
            board.make_move(move)
            try:
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            finally:
                board.unmake_move()

            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break  # beta cutoff

        # Determine TT flag.
        if best_score <= original_alpha:
            flag = _TTFlag.UPPER
        elif best_score >= beta:
            flag = _TTFlag.LOWER
        else:
            flag = _TTFlag.EXACT
        self._tt.store(board, depth, best_score, flag, best_move)

        return best_score

    # ------------------------------------------------------------------
    # quiescence search
    # ------------------------------------------------------------------

    def _quiescence(
        self, board: Board, alpha: int, beta: int, ply: int
    ) -> int:
        """Search captures (and promotions) only, plus all moves when
        in check. Stand-pat lets us bail out early when the static
        eval is already good enough.
        """
        self._nodes += 1
        if self._nodes % _TIME_CHECK_INTERVAL == 0:
            if self._deadline is not None and self._deadline.expired_or_stopped():
                raise _TimeUp()

        if board.is_insufficient_material():
            return 0

        in_check = board.is_check()

        # Stand-pat: only safe when not in check (otherwise we'd be
        # claiming "I'm fine" while actually being in check).
        if not in_check:
            stand_pat = evaluate(board)
            if stand_pat >= beta:
                return stand_pat
            if stand_pat > alpha:
                alpha = stand_pat

        legal = board.legal_moves()
        if not legal:
            if in_check:
                return -MATE_SCORE + ply
            return 0

        if in_check:
            # All evasions are fair game.
            moves = legal
        else:
            # Only captures and promotions (the "noisy" moves).
            moves = [
                m for m in legal
                if _is_capture(board, m) or m.promotion is not None
            ]
            if not moves:
                # Position is quiet; the stand-pat above is our score.
                return alpha

        for move in _order_qmoves(board, moves):
            board.make_move(move)
            try:
                score = -self._quiescence(board, -beta, -alpha, ply + 1)
            finally:
                board.unmake_move()
            if score >= beta:
                return score
            if score > alpha:
                alpha = score

        return alpha

    # ------------------------------------------------------------------
    # PV extraction (from TT)
    # ------------------------------------------------------------------

    def _extract_pv(self, board: Board, max_len: int) -> list[Move]:
        """Walk the TT from the root, collecting best moves until we
        run out of entries or the stored move is no longer legal
        (the latter shouldn't happen but is a cheap safety net).
        """
        pv: list[Move] = []
        played = 0
        try:
            for _ in range(max_len):
                entry = self._tt.lookup(board)
                if entry is None or entry.best_move is None:
                    break
                if entry.best_move not in board.legal_moves():
                    break
                pv.append(entry.best_move)
                board.make_move(entry.best_move)
                played += 1
        finally:
            for _ in range(played):
                board.unmake_move()
        return pv

    # ------------------------------------------------------------------
    # time allocation
    # ------------------------------------------------------------------

    def _allocate_time(
        self, our_color: Color, limits: SearchLimits, cfg: EloConfig
    ) -> Optional[int]:
        """Pick a time budget in milliseconds.

        Priority:
          1. ``limits.movetime_ms``
          2. ``limits.wtime_ms``/``btime_ms`` (with increment), via
             a simple fraction-of-remaining-time heuristic
          3. ``cfg.movetime_ms`` (ELO-derived default), but only when
             the caller didn't ask for an explicit depth or
             ``infinite`` (those imply caller-managed time).
          4. None (no wall-clock cap)
        """
        if limits.movetime_ms is not None and limits.movetime_ms > 0:
            return limits.movetime_ms
        if our_color is Color.WHITE:
            t, inc = limits.wtime_ms, limits.winc_ms
        else:
            t, inc = limits.btime_ms, limits.binc_ms
        if t is not None and t > 0:
            return max(1, t // 30) + (inc or 0)
        if limits.depth is None and not limits.infinite:
            return cfg.movetime_ms
        return None

    # ------------------------------------------------------------------
    # mate-score conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _score_to_mate_in(score: int) -> Optional[int]:
        """Translate a negamax score back into a "mate in N moves" int.

        Positive return: the side to move can mate in N.
        Negative return: the side to move is mated in |N|.
        Returns None when the score is not a mate score.
        """
        if score >= _MATE_THRESHOLD:
            ply = MATE_SCORE - score
            return (ply + 1) // 2
        if score <= -_MATE_THRESHOLD:
            ply = MATE_SCORE + score
            return -((ply + 1) // 2)
        return None
