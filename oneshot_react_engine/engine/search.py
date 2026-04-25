"""Alpha-beta search with iterative deepening, quiescence, TT, and move ordering.

Public surface:

    Engine(strength: StrengthSettings) - configurable engine
    Engine.search(board, on_info=None)  -> SearchResult
    Engine.choose_move(board)           -> Move

``choose_move`` is the high-level call used by the UCI layer and the web UI:
it runs the search and then applies the strength-controlled blunder/noise
policy to optionally pick something other than the best move (for sub-2400 ELO).
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from ..core.board import Board
from ..core.move import Move
from ..core.pieces import Color, PieceType
from .evaluator import evaluate
from .psqt import PIECE_VALUES
from .reasoning import ReasoningTrace
from .strength import StrengthSettings, settings_for_elo
from .transposition import EXACT, LOWER, UPPER, TTEntry, TranspositionTable


MATE_SCORE = 100_000
INF = 10_000_000


@dataclass
class SearchInfo:
    depth: int
    nodes: int
    elapsed_ms: int
    score_cp: int
    pv: List[Move]
    nps: int


@dataclass
class SearchResult:
    best_move: Optional[Move]
    score_cp: int
    depth_reached: int
    nodes: int
    elapsed_ms: int
    pv: List[Move] = field(default_factory=list)
    candidates: List[Tuple[Move, int]] = field(default_factory=list)
    reasoning: Optional[ReasoningTrace] = None


class TimeUp(Exception):
    """Raised internally to abort search when the soft time budget is exceeded."""


class Engine:
    def __init__(
        self,
        strength: Optional[StrengthSettings] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.strength = strength or settings_for_elo(2000)
        self.tt = TranspositionTable()
        self.rng = rng or random.Random()
        self.killers: List[List[Optional[Move]]] = [[None, None] for _ in range(64)]
        self.history: dict = {}
        self.nodes = 0
        self._deadline: Optional[float] = None
        self._stop_requested = False

    # ---- Public configuration --------------------------------------------------

    def set_strength(self, strength: StrengthSettings) -> None:
        self.strength = strength

    def set_elo(self, elo: int) -> None:
        self.strength = settings_for_elo(elo)

    def reset(self) -> None:
        self.tt.clear()
        self.killers = [[None, None] for _ in range(64)]
        self.history = {}

    def request_stop(self) -> None:
        self._stop_requested = True

    # ---- Top-level entry points ------------------------------------------------

    def choose_move(
        self,
        board: Board,
        movetime_ms: Optional[int] = None,
        max_depth: Optional[int] = None,
        record_reasoning: bool = False,
    ) -> Move:
        """Convenience wrapper: search and return the chosen move."""
        result = self.search_and_choose(
            board,
            movetime_ms=movetime_ms,
            max_depth=max_depth,
            record_reasoning=record_reasoning,
        )
        if result.best_move is None:
            raise RuntimeError("no legal moves available")
        return result.best_move

    def search_and_choose(
        self,
        board: Board,
        movetime_ms: Optional[int] = None,
        max_depth: Optional[int] = None,
        on_info: Optional[Callable[[SearchInfo], None]] = None,
        record_reasoning: bool = False,
    ) -> SearchResult:
        """Run a full search and apply the strength policy in one call.

        ``best_move`` on the returned ``SearchResult`` is the move the engine
        will actually play (may differ from the search's optimal move when
        ``blunder_pct > 0``).
        """
        result = self.search(
            board,
            movetime_ms=movetime_ms,
            max_depth=max_depth,
            on_info=on_info,
            record_reasoning=record_reasoning,
        )
        if result.best_move is None:
            return result

        if (
            self.strength.blunder_pct > 0
            and self.strength.candidate_pool > 1
            and len(result.candidates) > 1
            and self.rng.random() * 100 < self.strength.blunder_pct
        ):
            pool = result.candidates[1 : 1 + (self.strength.candidate_pool - 1)]
            weights = [max(1, 5 - i) for i in range(len(pool))]
            picked, _ = self.rng.choices(pool, weights=weights, k=1)[0]
            if result.reasoning is not None:
                result.reasoning.add(
                    thought="Strength setting allows a sub-optimal choice this move.",
                    action=f"Roll blunder ({self.strength.blunder_pct:.1f}% chance) -> picked {picked.uci()}",
                    observation=f"Diverging from best move {result.best_move.uci()} for ELO realism.",
                )
                result.reasoning.final_move = picked.uci()
            result.best_move = picked
        return result

    def search(
        self,
        board: Board,
        movetime_ms: Optional[int] = None,
        max_depth: Optional[int] = None,
        on_info: Optional[Callable[[SearchInfo], None]] = None,
        record_reasoning: bool = False,
    ) -> SearchResult:
        """Run iterative-deepening alpha-beta and return the best move found."""
        self._stop_requested = False
        self.nodes = 0
        depth_cap = max_depth if max_depth is not None else self.strength.max_depth
        budget_ms = movetime_ms if movetime_ms is not None else self.strength.movetime_ms
        if budget_ms and budget_ms > 0:
            self._deadline = time.monotonic() + budget_ms / 1000.0
        else:
            self._deadline = None

        start = time.monotonic()
        trace = ReasoningTrace() if record_reasoning else None
        if trace is not None:
            trace.add(
                thought="Decide a move from the current position.",
                action=f"Run iterative deepening up to depth {depth_cap}, time budget {budget_ms}ms.",
                observation=f"Engine strength = ELO {self.strength.elo}.",
            )

        legal = board.legal_moves()
        if not legal:
            return SearchResult(None, 0, 0, 0, 0, [], [], trace)

        best_move = legal[0]
        best_score = -INF
        depth_reached = 0
        pv_at_depth: List[Move] = [best_move]
        last_candidates: List[Tuple[Move, int]] = []

        try:
            for depth in range(1, depth_cap + 1):
                ordered = self._order_root_moves(board, legal, best_move)
                cur_best = ordered[0]
                cur_score = -INF
                alpha, beta = -INF, INF
                candidate_scores: List[Tuple[Move, int]] = []

                for move in ordered:
                    undo = board._make_move_internal(move)
                    score = -self._alpha_beta(board, depth - 1, -beta, -alpha, ply=1)
                    board._unmake_move_internal(move, undo)

                    candidate_scores.append((move, score))

                    if score > cur_score:
                        cur_score = score
                        cur_best = move
                    if score > alpha:
                        alpha = score

                # If we got here, this depth completed.
                best_move = cur_best
                best_score = cur_score
                depth_reached = depth
                last_candidates = sorted(candidate_scores, key=lambda x: -x[1])
                pv_at_depth = self._extract_pv(board, depth)

                elapsed = max(1, int((time.monotonic() - start) * 1000))
                nps = int(self.nodes * 1000 / elapsed) if elapsed else 0
                if on_info is not None:
                    on_info(
                        SearchInfo(
                            depth=depth,
                            nodes=self.nodes,
                            elapsed_ms=elapsed,
                            score_cp=best_score,
                            pv=pv_at_depth,
                            nps=nps,
                        )
                    )

                if abs(best_score) >= MATE_SCORE - 100:
                    break  # found a mate, stop deepening
                if self._stop_requested or self._time_up():
                    break

        except TimeUp:
            pass

        # Apply leaf noise after the fact (only affects move ordering / blunder pool,
        # not the principal score reported to UCI).
        if self.strength.noise_cp > 0 and last_candidates:
            jittered = [
                (m, s + int(self.rng.gauss(0, self.strength.noise_cp)))
                for m, s in last_candidates
            ]
            last_candidates = sorted(jittered, key=lambda x: -x[1])
            best_move = last_candidates[0][0]
            best_score = last_candidates[0][1]

        elapsed = max(1, int((time.monotonic() - start) * 1000))
        if trace is not None:
            top = ", ".join(
                f"{m.uci()}={s}cp" for m, s in last_candidates[:4]
            ) or "(none)"
            trace.add(
                thought="Compare candidate move evaluations from the search.",
                action=f"Sort candidates by score: {top}",
                observation=f"Top candidate so far: {best_move.uci()} ({best_score}cp).",
            )
            trace.final_move = best_move.uci()
            trace.final_score_cp = best_score

        return SearchResult(
            best_move=best_move,
            score_cp=best_score,
            depth_reached=depth_reached,
            nodes=self.nodes,
            elapsed_ms=elapsed,
            pv=pv_at_depth,
            candidates=last_candidates,
            reasoning=trace,
        )

    # ---- Internals -------------------------------------------------------------

    def _time_up(self) -> bool:
        return self._deadline is not None and time.monotonic() >= self._deadline

    def _alpha_beta(self, board: Board, depth: int, alpha: int, beta: int, ply: int) -> int:
        self.nodes += 1
        if self._stop_requested or self._time_up():
            raise TimeUp

        # Repetition / 50-move at non-root ply count as draw
        if ply > 0:
            if board.halfmove_clock >= 100:
                return 0
            if board.is_threefold_repetition():
                return 0
            if board.is_insufficient_material():
                return 0

        key = board._position_key()
        tt_hit = self.tt.get(key)
        tt_move: Optional[Move] = None
        if tt_hit is not None:
            tt_move = tt_hit.best_move
            if tt_hit.depth >= depth and ply > 0:
                if tt_hit.flag == EXACT:
                    return tt_hit.score
                if tt_hit.flag == LOWER and tt_hit.score >= beta:
                    return tt_hit.score
                if tt_hit.flag == UPPER and tt_hit.score <= alpha:
                    return tt_hit.score

        if depth <= 0:
            return self._quiesce(board, alpha, beta, ply)

        legal = board.legal_moves()
        if not legal:
            if board.is_in_check(board.turn):
                return -MATE_SCORE + ply
            return 0

        moves = self._order_moves(board, legal, tt_move, ply)

        original_alpha = alpha
        best_score = -INF
        best_move: Optional[Move] = None

        for move in moves:
            undo = board._make_move_internal(move)
            score = -self._alpha_beta(board, depth - 1, -beta, -alpha, ply + 1)
            board._unmake_move_internal(move, undo)

            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                # Beta cutoff -> killer + history bonuses for non-captures
                captured = board.squares[move.to_sq.row][move.to_sq.col]
                if captured is None and move.promotion is None:
                    if self.killers[ply][0] != move:
                        self.killers[ply][1] = self.killers[ply][0]
                        self.killers[ply][0] = move
                    self.history[move] = self.history.get(move, 0) + depth * depth
                break

        flag = EXACT
        if best_score <= original_alpha:
            flag = UPPER
        elif best_score >= beta:
            flag = LOWER
        self.tt.put(key, TTEntry(depth, best_score, flag, best_move))

        return best_score

    def _quiesce(self, board: Board, alpha: int, beta: int, ply: int) -> int:
        if self._stop_requested or self._time_up():
            raise TimeUp

        self.nodes += 1
        stand_pat = evaluate(board)
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        # Only consider captures (and promotions) in quiescence
        captures = []
        for m in board.legal_moves():
            target = board.squares[m.to_sq.row][m.to_sq.col]
            is_capture = target is not None or (
                board.piece_at(m.from_sq) is not None
                and board.piece_at(m.from_sq).piece_type == PieceType.PAWN
                and m.to_sq == board.en_passant
            )
            if is_capture or m.promotion is not None:
                captures.append(m)

        captures.sort(key=lambda m: -self._mvv_lva(board, m))

        for move in captures:
            undo = board._make_move_internal(move)
            score = -self._quiesce(board, -beta, -alpha, ply + 1)
            board._unmake_move_internal(move, undo)
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    # ---- Move ordering ---------------------------------------------------------

    def _order_root_moves(
        self, board: Board, legal: List[Move], pv_first: Optional[Move]
    ) -> List[Move]:
        return self._order_moves(board, legal, pv_first, ply=0)

    def _order_moves(
        self,
        board: Board,
        moves: List[Move],
        tt_move: Optional[Move],
        ply: int,
    ) -> List[Move]:
        killers = self.killers[ply] if ply < len(self.killers) else [None, None]

        def score(m: Move) -> int:
            if tt_move is not None and m == tt_move:
                return 1_000_000
            target = board.squares[m.to_sq.row][m.to_sq.col]
            if target is not None:
                return 100_000 + self._mvv_lva(board, m)
            if m.promotion is not None:
                return 90_000 + PIECE_VALUES.get(m.promotion, 0)
            if killers[0] == m:
                return 80_000
            if killers[1] == m:
                return 70_000
            return self.history.get(m, 0)

        return sorted(moves, key=score, reverse=True)

    def _mvv_lva(self, board: Board, m: Move) -> int:
        target = board.squares[m.to_sq.row][m.to_sq.col]
        attacker = board.squares[m.from_sq.row][m.from_sq.col]
        if target is None and attacker is not None and attacker.piece_type == PieceType.PAWN and m.to_sq == board.en_passant:
            return 10 * PIECE_VALUES[PieceType.PAWN] - PIECE_VALUES[PieceType.PAWN]
        if target is None or attacker is None:
            return 0
        return 10 * PIECE_VALUES[target.piece_type] - PIECE_VALUES[attacker.piece_type]

    def _extract_pv(self, board: Board, max_depth: int) -> List[Move]:
        pv: List[Move] = []
        stack: List[Tuple[Move, dict]] = []
        for _ in range(max_depth):
            entry = self.tt.get(board._position_key())
            if entry is None or entry.best_move is None:
                break
            move = entry.best_move
            if move not in board.legal_moves():
                break
            undo = board._make_move_internal(move)
            stack.append((move, undo))
            pv.append(move)
        for move, undo in reversed(stack):
            board._unmake_move_internal(move, undo)
        return pv
