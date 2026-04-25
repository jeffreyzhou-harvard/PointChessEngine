"""Move ordering.

Good move ordering is what makes alpha-beta cheap. We score moves with:

    1.  the TT best move (if any)        -> +1_000_000
    2.  promotions                       -> +900_000 + promo piece value
    3.  captures, scored MVV-LVA         -> +100_000 + (10*victim - attacker)
    4.  killer moves at this ply         -> +90_000 / +80_000
    5.  history-heuristic (quiet moves)  -> raw history score, capped

Ply-indexed killer slots and a (from, to) -> int history map are owned by a
`MoveOrderer` instance; the searcher creates one per search.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

import chess

PIECE_ORDER_VALUE = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000,
}

MAX_PLY = 128


class MoveOrderer:
    __slots__ = ("killers", "history")

    def __init__(self) -> None:
        self.killers: List[List[Optional[chess.Move]]] = [
            [None, None] for _ in range(MAX_PLY)
        ]
        self.history: dict = {}  # (from_sq, to_sq) -> int

    def reset(self) -> None:
        for slot in self.killers:
            slot[0] = slot[1] = None
        self.history.clear()

    # ---------- API used by search ---------------------------------------

    def record_killer(self, ply: int, move: chess.Move) -> None:
        if ply >= MAX_PLY:
            return
        slot = self.killers[ply]
        if slot[0] != move:
            slot[1] = slot[0]
            slot[0] = move

    def record_history(self, move: chess.Move, depth: int) -> None:
        key = (move.from_square, move.to_square)
        self.history[key] = self.history.get(key, 0) + depth * depth

    def score(self, board: chess.Board, move: chess.Move,
              ply: int, tt_move: Optional[chess.Move]) -> int:
        if tt_move is not None and move == tt_move:
            return 1_000_000

        if move.promotion:
            return 900_000 + PIECE_ORDER_VALUE.get(move.promotion, 0)

        # Captures (including en passant).
        if board.is_capture(move):
            victim = board.piece_type_at(move.to_square)
            if victim is None:  # en passant
                victim = chess.PAWN
            attacker = board.piece_type_at(move.from_square) or chess.PAWN
            return (100_000
                    + 10 * PIECE_ORDER_VALUE[victim]
                    - PIECE_ORDER_VALUE[attacker])

        if ply < MAX_PLY:
            killer = self.killers[ply]
            if move == killer[0]:
                return 90_000
            if move == killer[1]:
                return 80_000

        return self.history.get((move.from_square, move.to_square), 0)

    def order(self, board: chess.Board, moves: Iterable[chess.Move],
              ply: int, tt_move: Optional[chess.Move]) -> List[chess.Move]:
        scored = [(self.score(board, m, ply, tt_move), m) for m in moves]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored]
