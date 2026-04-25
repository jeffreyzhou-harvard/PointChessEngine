"""Search.

Iterative-deepening negamax with alpha-beta, transposition table,
quiescence search, null-move pruning, and late-move reductions. Returns
both a best move and a SearchInfo with PV / score / depth / nodes / nps,
which the UCI layer formats into `info` lines.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import chess

from .evaluation import evaluate
from .ordering import MoveOrderer, MAX_PLY
from .tt import EXACT, LOWER, UPPER, TranspositionTable

INF = 10_000_000
MATE = 1_000_000
MATE_THRESHOLD = MATE - 1000  # scores above this represent a mate distance


@dataclass
class SearchLimits:
    max_depth: int = 64
    max_time_ms: Optional[int] = None
    nodes: Optional[int] = None
    infinite: bool = False


@dataclass
class SearchInfo:
    depth: int = 0
    seldepth: int = 0
    score_cp: int = 0
    mate_in: Optional[int] = None  # plies signed; positive = we mate
    nodes: int = 0
    time_ms: int = 0
    pv: List[chess.Move] = field(default_factory=list)
    best_move: Optional[chess.Move] = None
    multipv: List["SearchInfo"] = field(default_factory=list)


class _StopSearch(Exception):
    pass


class Searcher:
    """Single-threaded principal-variation search."""

    def __init__(self, tt: TranspositionTable):
        self.tt = tt
        self.orderer = MoveOrderer()
        self._stop = False
        self._deadline: Optional[float] = None
        self._nodes = 0
        self._seldepth = 0
        self._limits = SearchLimits()
        self._info_callback: Optional[Callable[[SearchInfo], None]] = None
        self._root_moves: Optional[List[chess.Move]] = None

    # --- public ------------------------------------------------------

    def request_stop(self) -> None:
        self._stop = True

    def search(self, board: chess.Board, limits: SearchLimits,
               *, info_callback: Optional[Callable[[SearchInfo], None]] = None,
               multipv: int = 1) -> SearchInfo:
        """Top-level iterative deepening search.

        Returns a SearchInfo for the principal line. If `multipv > 1`, the
        result's `multipv` field is filled with the top-N lines from the
        last completed iteration.
        """
        self._stop = False
        self._nodes = 0
        self._seldepth = 0
        self._limits = limits
        self._info_callback = info_callback

        if limits.max_time_ms is not None:
            self._deadline = time.monotonic() + (limits.max_time_ms / 1000.0)
        else:
            self._deadline = None

        self.orderer.reset()

        legal = list(board.legal_moves)
        if not legal:
            info = SearchInfo()
            info.score_cp = -MATE if board.is_check() else 0
            return info

        # Initial root move list, ordered by static heuristics.
        root_moves = self.orderer.order(board, legal, 0, None)

        best_info = SearchInfo()
        best_info.best_move = root_moves[0]

        max_depth = max(1, min(limits.max_depth, MAX_PLY - 1))
        start = time.monotonic()

        for depth in range(1, max_depth + 1):
            try:
                if multipv == 1:
                    info = self._root_search(board, depth, root_moves)
                    info.depth = depth
                    info.time_ms = int((time.monotonic() - start) * 1000)
                    info.nodes = self._nodes
                    info.seldepth = self._seldepth
                    best_info = info
                    if info.best_move is not None:
                        # Re-order: best move first next iteration.
                        root_moves = [info.best_move] + [
                            m for m in root_moves if m != info.best_move]
                    if info_callback:
                        info_callback(info)
                    if info.mate_in is not None and info.mate_in > 0:
                        break
                else:
                    multi = self._root_search_multipv(board, depth, root_moves, multipv)
                    if multi:
                        # The first one is the principal.
                        principal = multi[0]
                        principal.depth = depth
                        principal.time_ms = int((time.monotonic() - start) * 1000)
                        principal.nodes = self._nodes
                        principal.seldepth = self._seldepth
                        principal.multipv = multi
                        best_info = principal
                        if principal.best_move is not None:
                            root_moves = [principal.best_move] + [
                                m for m in root_moves if m != principal.best_move]
                        if info_callback:
                            info_callback(principal)
            except _StopSearch:
                break

            if self._time_up():
                break

        return best_info

    # --- root --------------------------------------------------------

    def _root_search(self, board: chess.Board, depth: int,
                     root_moves: List[chess.Move]) -> SearchInfo:
        alpha, beta = -INF, INF
        best_score = -INF
        best_move = root_moves[0]
        best_pv: List[chess.Move] = [best_move]

        for move in root_moves:
            board.push(move)
            try:
                child_pv: List[chess.Move] = []
                score = -self._negamax(board, depth - 1, 1,
                                       -beta, -alpha, child_pv, allow_null=True)
            finally:
                board.pop()
            if score > best_score:
                best_score = score
                best_move = move
                best_pv = [move] + child_pv
                if score > alpha:
                    alpha = score

        info = SearchInfo()
        info.score_cp = best_score
        if abs(best_score) >= MATE_THRESHOLD:
            mate_plies = MATE - abs(best_score)
            info.mate_in = (mate_plies + 1) // 2 * (1 if best_score > 0 else -1)
        info.best_move = best_move
        info.pv = best_pv
        return info

    def _root_search_multipv(self, board: chess.Board, depth: int,
                             root_moves: List[chess.Move],
                             multipv: int) -> List[SearchInfo]:
        """Slow but simple MultiPV: sort root moves by full search score."""
        scored: List[SearchInfo] = []
        for move in root_moves:
            board.push(move)
            try:
                child_pv: List[chess.Move] = []
                score = -self._negamax(board, depth - 1, 1,
                                       -INF, INF, child_pv, allow_null=True)
            finally:
                board.pop()
            info = SearchInfo()
            info.score_cp = score
            info.best_move = move
            info.pv = [move] + child_pv
            if abs(score) >= MATE_THRESHOLD:
                mate_plies = MATE - abs(score)
                info.mate_in = (mate_plies + 1) // 2 * (1 if score > 0 else -1)
            scored.append(info)
        scored.sort(key=lambda i: i.score_cp, reverse=True)
        return scored[:multipv]

    # --- negamax -----------------------------------------------------

    def _negamax(self, board: chess.Board, depth: int, ply: int,
                 alpha: int, beta: int, pv_out: List[chess.Move],
                 allow_null: bool) -> int:
        self._nodes += 1
        if self._nodes & 1023 == 0:
            self._maybe_stop()

        if ply > self._seldepth:
            self._seldepth = ply

        # Repetition / 50-move draw — adjudicate before TT probe.
        if ply > 0 and (board.is_repetition(2)
                        or board.is_fifty_moves()
                        or board.is_insufficient_material()):
            return 0

        # Leaf -> quiescence.
        if depth <= 0:
            return self._quiescence(board, ply, alpha, beta)

        in_check = board.is_check()

        # TT probe.
        key = self.tt.hash_for(board)
        tt_entry = self.tt.probe(key)
        tt_move: Optional[chess.Move] = None
        if tt_entry is not None:
            tt_value, tt_depth, tt_flag, tt_move = tt_entry
            if tt_depth >= depth and ply > 0:
                if tt_flag == EXACT:
                    return tt_value
                if tt_flag == LOWER and tt_value >= beta:
                    return tt_value
                if tt_flag == UPPER and tt_value <= alpha:
                    return tt_value

        # Null-move pruning. Skip near roots, when in check, or in
        # late-endgame zugzwang territory (too few non-pawns for STM).
        if (allow_null and not in_check and depth >= 3 and ply > 0
                and self._has_non_pawn_material(board, board.turn)
                and beta < MATE_THRESHOLD):
            r = 2 + (depth // 4)
            board.push(chess.Move.null())
            try:
                child_pv: List[chess.Move] = []
                score = -self._negamax(board, depth - 1 - r, ply + 1,
                                       -beta, -beta + 1, child_pv,
                                       allow_null=False)
            finally:
                board.pop()
            if score >= beta:
                return beta

        legal = list(board.legal_moves)
        if not legal:
            # Mate or stalemate.
            if in_check:
                return -MATE + ply
            return 0

        ordered = self.orderer.order(board, legal, ply, tt_move)

        best_score = -INF
        best_move: Optional[chess.Move] = None
        original_alpha = alpha
        moves_searched = 0

        for move in ordered:
            is_capture_or_promo = (board.is_capture(move) or move.promotion is not None)
            gives_check = board.gives_check(move)

            board.push(move)
            try:
                child_pv: List[chess.Move] = []

                # Late-move reductions.
                reduction = 0
                if (depth >= 3 and moves_searched >= 4 and not in_check
                        and not is_capture_or_promo and not gives_check):
                    reduction = 1
                    if moves_searched >= 8:
                        reduction = 2

                if moves_searched == 0:
                    score = -self._negamax(board, depth - 1, ply + 1,
                                           -beta, -alpha, child_pv,
                                           allow_null=True)
                else:
                    # PVS: null-window + reduction.
                    score = -self._negamax(board, depth - 1 - reduction, ply + 1,
                                           -alpha - 1, -alpha, child_pv,
                                           allow_null=True)
                    if alpha < score < beta:
                        # Re-search with full window and full depth.
                        child_pv = []
                        score = -self._negamax(board, depth - 1, ply + 1,
                                               -beta, -alpha, child_pv,
                                               allow_null=True)
                    elif reduction and score > alpha:
                        # Re-search at full depth without reduction.
                        child_pv = []
                        score = -self._negamax(board, depth - 1, ply + 1,
                                               -alpha - 1, -alpha, child_pv,
                                               allow_null=True)
                        if alpha < score < beta:
                            child_pv = []
                            score = -self._negamax(board, depth - 1, ply + 1,
                                                   -beta, -alpha, child_pv,
                                                   allow_null=True)
            finally:
                board.pop()

            moves_searched += 1

            if score > best_score:
                best_score = score
                best_move = move
                if score > alpha:
                    alpha = score
                    pv_out[:] = [move] + child_pv

            if alpha >= beta:
                if not is_capture_or_promo:
                    self.orderer.record_killer(ply, move)
                    self.orderer.record_history(move, depth)
                break

        # Store TT entry.
        if best_score <= original_alpha:
            flag = UPPER
        elif best_score >= beta:
            flag = LOWER
        else:
            flag = EXACT
        self.tt.store(key, depth, best_score, flag, best_move)

        return best_score

    def _quiescence(self, board: chess.Board, ply: int,
                    alpha: int, beta: int) -> int:
        self._nodes += 1
        if self._nodes & 1023 == 0:
            self._maybe_stop()
        if ply > self._seldepth:
            self._seldepth = ply

        if board.is_insufficient_material():
            return 0

        in_check = board.is_check()
        if not in_check:
            stand_pat = evaluate(board)
            if stand_pat >= beta:
                return beta
            if stand_pat > alpha:
                alpha = stand_pat
        else:
            stand_pat = -INF  # forced to play any legal move

        # Generate captures (and all moves if in check).
        moves = []
        if in_check:
            moves = list(board.legal_moves)
        else:
            for m in board.legal_moves:
                if board.is_capture(m) or m.promotion is not None:
                    moves.append(m)

        ordered = self.orderer.order(board, moves, ply, None)

        for move in ordered:
            board.push(move)
            try:
                score = -self._quiescence(board, ply + 1, -beta, -alpha)
            finally:
                board.pop()
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        if in_check and not moves:
            # Checkmate.
            return -MATE + ply

        return alpha

    # --- helpers -----------------------------------------------------

    def _maybe_stop(self) -> None:
        if self._stop:
            raise _StopSearch
        if self._time_up():
            raise _StopSearch
        if self._limits.nodes is not None and self._nodes >= self._limits.nodes:
            raise _StopSearch

    def _time_up(self) -> bool:
        return (self._deadline is not None
                and time.monotonic() >= self._deadline)

    @staticmethod
    def _has_non_pawn_material(board: chess.Board, color: chess.Color) -> bool:
        for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            if board.pieces_mask(pt, color):
                return True
        return False
