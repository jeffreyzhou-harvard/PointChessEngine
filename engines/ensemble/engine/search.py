"""Iterative-deepening alpha-beta search.

Per the contract:
    - negamax + alpha-beta
    - iterative deepening from depth 1..max_depth
    - quiescence (captures+promotions, capped at ply+8)
    - null-move pruning (R=2, skip in check / depth<3 / king+pawns only)
    - transposition table (dict keyed by zobrist) with EXACT/LOWER/UPPER flags
    - killer moves (2 per ply) and history table
    - move ordering: TT, captures (MVV-LVA), killers, history
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from .board import (
    Board, Move,
    EMPTY, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
    WHITE, BLACK,
)
from .evaluate import evaluate
from .movegen import generate_legal, generate_pseudo_legal, generate_captures

INF = 10**9
MATE = 100_000
MATE_THRESHOLD = MATE - 1000

EXACT, LOWER, UPPER = 0, 1, 2
TT_MAX = 1_000_000

PIECE_VALUE = {0: 0, PAWN: 100, KNIGHT: 320, BISHOP: 330, ROOK: 500, QUEEN: 900, KING: 20000}


@dataclass
class SearchLimits:
    max_depth: int = 64
    time_ms: Optional[int] = None
    nodes: Optional[int] = None


@dataclass
class SearchResult:
    best_move: Optional[Move]
    score: int
    depth: int
    nodes: int
    pv: List[Move] = field(default_factory=list)
    scored_moves: List[Tuple[Move, int]] = field(default_factory=list)


class TimeUp(Exception):
    pass


class Searcher:
    def __init__(self, info_callback: Optional[Callable[[dict], None]] = None) -> None:
        self.tt: dict = {}
        self.killers: List[List[Optional[Move]]] = [[None, None] for _ in range(128)]
        # 12 piece-types (P,N,B,R,Q,K white then black) x 120 squares (sq120 indexed for simplicity).
        self.history: List[List[int]] = [[0] * 120 for _ in range(12)]
        self.nodes = 0
        self.stop_flag = None  # set by caller (threading.Event)
        self.deadline: Optional[float] = None
        self.info_callback = info_callback

    # ---------------- internal helpers ----------------
    def _check_stop(self) -> None:
        if self.stop_flag is not None and self.stop_flag.is_set():
            raise TimeUp()
        if self.deadline is not None and (self.nodes & 2047) == 0:
            if time.monotonic() >= self.deadline:
                raise TimeUp()

    def _piece_index(self, piece: int) -> int:
        return (abs(piece) - 1) + (0 if piece > 0 else 6)

    def _record_killer(self, ply: int, move: Move) -> None:
        if move.captured or move.promotion:
            return
        k = self.killers[ply]
        if k[0] != move:
            k[1] = k[0]
            k[0] = move

    def _bump_history(self, move: Move, depth: int) -> None:
        if move.captured or move.promotion:
            return
        idx = self._piece_index(move.piece)
        self.history[idx][move.dst] += depth * depth

    def _score_move(self, move: Move, ply: int, tt_move: Optional[Move]) -> int:
        if tt_move is not None and move == tt_move:
            return 10_000_000
        if move.captured or move.is_ep:
            victim = abs(move.captured) if move.captured else PAWN  # ep captures pawn
            attacker = abs(move.piece)
            return 1_000_000 + PIECE_VALUE[victim] * 10 - attacker
        if move.promotion:
            return 900_000 + PIECE_VALUE[abs(move.promotion)]
        k = self.killers[ply]
        if k[0] == move:
            return 800_000
        if k[1] == move:
            return 700_000
        return self.history[self._piece_index(move.piece)][move.dst]

    def _order_moves(self, moves: List[Move], ply: int, tt_move: Optional[Move]) -> List[Move]:
        return sorted(moves, key=lambda m: -self._score_move(m, ply, tt_move))

    def _has_only_king_and_pawns(self, board: Board, color: int) -> bool:
        for sq in range(21, 99):
            p = board.squares[sq]
            if p == 0 or p == 7:
                continue
            if (p > 0) == (color > 0):
                a = abs(p)
                if a not in (PAWN, KING):
                    return False
        return True

    # ---------------- quiescence ----------------
    def _quiesce(self, board: Board, alpha: int, beta: int, ply: int) -> int:
        self.nodes += 1
        self._check_stop()
        if ply >= 64:
            return evaluate(board)
        stand = evaluate(board)
        if stand >= beta:
            return beta
        if stand > alpha:
            alpha = stand
        # captures + promotions, ordered by MVV-LVA / promo value.
        caps = generate_captures(board)
        # Filter for legality lazily.
        caps.sort(key=lambda m: -(
            (PIECE_VALUE[abs(m.captured)] * 10 - abs(m.piece)) if m.captured
            else (PIECE_VALUE[abs(m.promotion)] if m.promotion else 0)
        ))
        mover = board.side_to_move
        for m in caps:
            board.make_move(m)
            if board.is_square_attacked(board.king_sq[mover], -mover):
                board.unmake_move()
                continue
            score = -self._quiesce(board, -beta, -alpha, ply + 1)
            board.unmake_move()
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    # ---------------- negamax ----------------
    def _negamax(self, board: Board, depth: int, alpha: int, beta: int, ply: int, allow_null: bool = True) -> int:
        self.nodes += 1
        self._check_stop()

        # Repetition / fifty-move-rule draws.
        if board.halfmove_clock >= 100 and ply > 0:
            return 0
        if ply > 0 and self._is_repetition(board):
            return 0

        in_check = board.in_check()
        if in_check:
            depth += 1  # check extension

        if depth <= 0:
            return self._quiesce(board, alpha, beta, ply)

        # TT probe.
        key = board.zobrist_key
        tt_entry = self.tt.get(key)
        tt_move: Optional[Move] = None
        if tt_entry is not None:
            tdepth, tscore, tflag, tmove = tt_entry
            tt_move = tmove
            if tdepth >= depth and ply > 0:
                if tflag == EXACT:
                    return tscore
                elif tflag == LOWER and tscore >= beta:
                    return tscore
                elif tflag == UPPER and tscore <= alpha:
                    return tscore

        # Null-move pruning.
        if (allow_null and not in_check and depth >= 3 and ply > 0
                and not self._has_only_king_and_pawns(board, board.side_to_move)):
            # Make a "pass" by flipping side to move (and clearing ep).
            saved_ep = board.ep_square
            saved_key = board.zobrist_key
            from .board import ZOBRIST_SIDE, ZOBRIST_EP_FILE
            board.side_to_move = -board.side_to_move
            board.zobrist_key ^= ZOBRIST_SIDE
            if saved_ep is not None:
                board.zobrist_key ^= ZOBRIST_EP_FILE[(saved_ep - 21) % 10]
                board.ep_square = None
            try:
                score = -self._negamax(board, depth - 1 - 2, -beta, -beta + 1, ply + 1, allow_null=False)
            finally:
                board.side_to_move = -board.side_to_move
                board.zobrist_key = saved_key
                board.ep_square = saved_ep
            if score >= beta:
                return beta

        # Generate & order legal moves.
        moves = generate_legal(board)
        if not moves:
            if in_check:
                return -MATE + ply  # checkmate
            return 0  # stalemate

        moves = self._order_moves(moves, ply, tt_move)
        best_score = -INF
        best_move: Optional[Move] = None
        orig_alpha = alpha

        for m in moves:
            board.make_move(m)
            score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, allow_null=True)
            board.unmake_move()

            if score > best_score:
                best_score = score
                best_move = m
            if score > alpha:
                alpha = score
            if alpha >= beta:
                self._record_killer(ply, m)
                self._bump_history(m, depth)
                break

        # Store in TT.
        if len(self.tt) >= TT_MAX:
            # Evict an arbitrary entry.
            self.tt.pop(next(iter(self.tt)))
        if best_score <= orig_alpha:
            flag = UPPER
        elif best_score >= beta:
            flag = LOWER
        else:
            flag = EXACT
        self.tt[key] = (depth, best_score, flag, best_move)
        return best_score

    def _is_repetition(self, board: Board) -> bool:
        # Look back through history for a matching key (twofold = treat as draw).
        key = board.zobrist_key
        count = 0
        # halfmove_clock bounds how far we need to look (resets on capture/pawn).
        limit = min(len(board.history), board.halfmove_clock)
        # board.history stores Undo entries; their zobrist_key is the pre-move key.
        for i in range(len(board.history) - 1, len(board.history) - 1 - limit, -1):
            if i < 0: break
            if board.history[i].zobrist_key == key:
                count += 1
                if count >= 1:
                    return True
        return False

    def _extract_pv(self, board: Board, depth: int) -> List[Move]:
        pv: List[Move] = []
        depth_used = 0
        while depth_used < depth:
            entry = self.tt.get(board.zobrist_key)
            if entry is None:
                break
            _, _, _, mv = entry
            if mv is None:
                break
            # Verify legality.
            legal = generate_legal(board)
            if mv not in legal:
                break
            pv.append(mv)
            board.make_move(mv)
            depth_used += 1
        for _ in pv:
            board.unmake_move()
        return pv

    # ---------------- public ----------------
    def search(self, board: Board, limits: SearchLimits, stop_flag=None) -> SearchResult:
        self.nodes = 0
        self.stop_flag = stop_flag
        self.deadline = (time.monotonic() + limits.time_ms / 1000.0) if limits.time_ms else None
        # Reset killers for fresh search.
        self.killers = [[None, None] for _ in range(128)]

        legal = generate_legal(board)
        if not legal:
            return SearchResult(None, 0, 0, 0)

        best_move = legal[0]
        best_score = 0
        best_depth = 0
        scored_moves: List[Tuple[Move, int]] = [(m, 0) for m in legal]

        for depth in range(1, limits.max_depth + 1):
            try:
                # Root search: score all moves so we can return them for ELO sampling.
                alpha, beta = -INF, INF
                this_round: List[Tuple[Move, int]] = []
                ordered = self._order_moves(legal, 0, best_move)
                cur_best = ordered[0]
                cur_score = -INF
                for m in ordered:
                    board.make_move(m)
                    score = -self._negamax(board, depth - 1, -beta, -alpha, 1, allow_null=True)
                    board.unmake_move()
                    this_round.append((m, score))
                    if score > cur_score:
                        cur_score = score
                        cur_best = m
                    if score > alpha:
                        alpha = score
                # Completed depth.
                best_move = cur_best
                best_score = cur_score
                best_depth = depth
                scored_moves = this_round
                # Store root in TT.
                self.tt[board.zobrist_key] = (depth, cur_score, EXACT, cur_best)
                if self.info_callback is not None:
                    self.info_callback({
                        "depth": depth,
                        "score": cur_score,
                        "nodes": self.nodes,
                        "pv": [m.uci() for m in self._extract_pv(board, depth)],
                    })
                if abs(cur_score) > MATE_THRESHOLD:
                    break
            except TimeUp:
                break

        pv = self._extract_pv(board, best_depth) if best_depth else []
        return SearchResult(
            best_move=best_move,
            score=best_score,
            depth=best_depth,
            nodes=self.nodes,
            pv=pv,
            scored_moves=scored_moves,
        )


def search(board: Board, limits: SearchLimits, stop_flag=None,
           info_callback: Optional[Callable[[dict], None]] = None) -> SearchResult:
    s = Searcher(info_callback=info_callback)
    return s.search(board, limits, stop_flag=stop_flag)
