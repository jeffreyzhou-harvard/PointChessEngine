"""Chess engine with alpha-beta search, iterative deepening, and transposition table.

Search features:
- Minimax with alpha-beta pruning
- Iterative deepening
- Quiescence search (captures only)
- Transposition table with Zobrist-style hashing
- Move ordering: captures first, then killer moves, then PST
- ELO-based strength adjustment
"""

import random
import time
from typing import Optional, List, Tuple, Dict
from engines.oneshot_nocontext.core.board import Board
from engines.oneshot_nocontext.core.types import Color, PieceType, Piece, Move, Square
from .evaluation import evaluate, PIECE_VALUES
from .elo import EloSettings


# Transposition table entry types
TT_EXACT = 0
TT_ALPHA = 1  # upper bound
TT_BETA = 2   # lower bound

MATE_SCORE = 100000
MAX_QUIESCENCE_DEPTH = 8


class TTEntry:
    __slots__ = ['key', 'depth', 'score', 'flag', 'best_move']

    def __init__(self, key: str, depth: int, score: int, flag: int, best_move: Optional[Move]):
        self.key = key
        self.depth = depth
        self.score = score
        self.flag = flag
        self.best_move = best_move


class Engine:
    def __init__(self, elo: int = 1500):
        self.settings = EloSettings.from_elo(elo)
        self.tt: Dict[str, TTEntry] = {}
        self.tt_max_size = 1_000_000
        self.nodes_searched = 0
        self.stop_search = False
        self.start_time = 0.0
        self.time_limit = 0.0
        # Killer moves: moves that caused beta cutoffs at each depth
        self.killers: List[List[Optional[Move]]] = [[None, None] for _ in range(64)]

    def set_elo(self, elo: int):
        self.settings = EloSettings.from_elo(elo)

    def clear(self):
        """Clear transposition table and killer moves."""
        self.tt.clear()
        self.killers = [[None, None] for _ in range(64)]

    def search(self, board: Board, max_depth: Optional[int] = None,
               time_limit: Optional[float] = None) -> Tuple[Optional[Move], int]:
        """Find the best move using iterative deepening alpha-beta.

        Returns (best_move, score).
        """
        self.nodes_searched = 0
        self.stop_search = False
        self.start_time = time.time()

        depth = max_depth if max_depth is not None else self.settings.max_depth
        self.time_limit = time_limit if time_limit is not None else self.settings.time_limit

        legal_moves = board.legal_moves()
        if not legal_moves:
            return None, 0

        if len(legal_moves) == 1:
            return legal_moves[0], 0

        best_move = legal_moves[0]
        best_score = -MATE_SCORE

        # Iterative deepening
        for d in range(1, depth + 1):
            if self.stop_search:
                break

            move, score = self._search_root(board, d, legal_moves)
            if not self.stop_search and move is not None:
                best_move = move
                best_score = score

            # Check time
            elapsed = time.time() - self.start_time
            if elapsed > self.time_limit * 0.7:
                break

        # Apply ELO-based randomization
        best_move = self._apply_elo_adjustments(board, best_move, legal_moves)

        return best_move, best_score

    def _search_root(self, board: Board, depth: int,
                     legal_moves: List[Move]) -> Tuple[Optional[Move], int]:
        """Search from root position."""
        best_move = None
        best_score = -MATE_SCORE
        alpha = -MATE_SCORE
        beta = MATE_SCORE

        ordered = self._order_moves(board, legal_moves, 0)

        for move in ordered:
            board.make_move(move)
            score = -self._alpha_beta(board, depth - 1, -beta, -alpha, 1)
            board.unmake_move()

            if self.stop_search:
                break

            if score > best_score:
                best_score = score
                best_move = move
                if score > alpha:
                    alpha = score

        return best_move, best_score

    def _alpha_beta(self, board: Board, depth: int, alpha: int, beta: int,
                    ply: int) -> int:
        """Alpha-beta search with transposition table."""
        self.nodes_searched += 1

        # Time check every 4096 nodes
        if self.nodes_searched & 4095 == 0:
            if time.time() - self.start_time > self.time_limit:
                self.stop_search = True
                return 0

        if self.stop_search:
            return 0

        # Check for game-ending positions
        over, reason = board.is_game_over()
        if over:
            if board.is_checkmate():
                return -MATE_SCORE + ply  # being checkmated is bad
            return 0  # draw

        if depth <= 0:
            return self._quiescence(board, alpha, beta, 0)

        # Transposition table lookup
        pos_key = board.to_fen()
        tt_entry = self.tt.get(pos_key)
        tt_move = None
        if tt_entry and tt_entry.depth >= depth:
            if tt_entry.flag == TT_EXACT:
                return tt_entry.score
            elif tt_entry.flag == TT_ALPHA and tt_entry.score <= alpha:
                return alpha
            elif tt_entry.flag == TT_BETA and tt_entry.score >= beta:
                return beta
            tt_move = tt_entry.best_move

        legal_moves = board.legal_moves()
        if not legal_moves:
            if board.is_in_check(board.turn):
                return -MATE_SCORE + ply
            return 0

        # Move ordering
        ordered = self._order_moves(board, legal_moves, ply, tt_move)

        best_score = -MATE_SCORE
        best_move = ordered[0]
        original_alpha = alpha

        for move in ordered:
            board.make_move(move)
            score = -self._alpha_beta(board, depth - 1, -beta, -alpha, ply + 1)
            board.unmake_move()

            if self.stop_search:
                return 0

            if score > best_score:
                best_score = score
                best_move = move

            if score > alpha:
                alpha = score

            if alpha >= beta:
                # Store killer move
                if board.piece_at(move.to_sq) is None:  # quiet move
                    if ply < 64:
                        self.killers[ply][1] = self.killers[ply][0]
                        self.killers[ply][0] = move
                break

        # Store in transposition table
        if len(self.tt) < self.tt_max_size:
            if best_score <= original_alpha:
                flag = TT_ALPHA
            elif best_score >= beta:
                flag = TT_BETA
            else:
                flag = TT_EXACT
            self.tt[pos_key] = TTEntry(pos_key, depth, best_score, flag, best_move)

        return best_score

    def _quiescence(self, board: Board, alpha: int, beta: int, depth: int) -> int:
        """Quiescence search - only consider captures to avoid horizon effect."""
        self.nodes_searched += 1

        stand_pat = evaluate(board)
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        if depth >= MAX_QUIESCENCE_DEPTH:
            return stand_pat

        # Generate only capture moves
        captures = []
        for move in board.legal_moves():
            if board.piece_at(move.to_sq) is not None or move.promotion is not None:
                captures.append(move)
            elif (board.piece_at(move.from_sq) and
                  board.piece_at(move.from_sq).piece_type == PieceType.PAWN and
                  move.to_sq == board.en_passant):
                captures.append(move)

        # Order captures by MVV-LVA
        captures.sort(key=lambda m: self._mvv_lva(board, m), reverse=True)

        for move in captures:
            board.make_move(move)
            score = -self._quiescence(board, -beta, -alpha, depth + 1)
            board.unmake_move()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    def _mvv_lva(self, board: Board, move: Move) -> int:
        """Most Valuable Victim - Least Valuable Attacker scoring."""
        victim = board.piece_at(move.to_sq)
        attacker = board.piece_at(move.from_sq)
        if victim is None:
            return 0
        victim_val = PIECE_VALUES.get(victim.piece_type, 0)
        attacker_val = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
        return victim_val * 10 - attacker_val

    def _order_moves(self, board: Board, moves: List[Move], ply: int,
                     tt_move: Optional[Move] = None) -> List[Move]:
        """Order moves for better alpha-beta pruning."""
        scored = []
        for move in moves:
            score = 0

            # TT move first
            if tt_move and move == tt_move:
                score = 100000
            # Captures (MVV-LVA)
            elif board.piece_at(move.to_sq) is not None:
                score = 50000 + self._mvv_lva(board, move)
            # Promotions
            elif move.promotion:
                score = 40000 + (PIECE_VALUES.get(move.promotion, 0) if move.promotion else 0)
            # Killer moves
            elif ply < 64:
                if move == self.killers[ply][0]:
                    score = 30000
                elif move == self.killers[ply][1]:
                    score = 29000
            scored.append((score, move))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored]

    def _apply_elo_adjustments(self, board: Board, best_move: Move,
                               legal_moves: List[Move]) -> Move:
        """Apply ELO-based randomization to make the engine play weaker.

        Instead of random blunders, we pick from evaluated alternatives
        weighted by their score, producing more human-like mistakes.
        """
        settings = self.settings

        if settings.elo >= 2400 or len(legal_moves) <= 1:
            return best_move

        # Add evaluation noise: re-evaluate top moves with noise
        if settings.eval_noise > 0 or settings.blunder_chance > 0:
            # Score all legal moves quickly (depth 1)
            scored_moves = []
            for move in legal_moves:
                board.make_move(move)
                score = -evaluate(board)
                # Add noise
                if settings.eval_noise > 0:
                    noise = random.gauss(0, settings.eval_noise)
                    score += int(noise)
                board.unmake_move()
                scored_moves.append((score, move))

            scored_moves.sort(key=lambda x: x[0], reverse=True)

            # Blunder check: maybe pick a non-best move
            if random.random() < settings.blunder_chance and len(scored_moves) > 1:
                # Pick from 2nd-5th best moves, weighted toward better ones
                candidates = scored_moves[1:min(5, len(scored_moves))]
                if candidates:
                    weights = [max(1, 1000 + s) for s, _ in candidates]
                    total = sum(weights)
                    r = random.random() * total
                    cumulative = 0
                    for w, (s, m) in zip(weights, candidates):
                        cumulative += w
                        if r <= cumulative:
                            return m
                    return candidates[-1][1]

            # Even without blundering, noise may change the best move
            if scored_moves:
                return scored_moves[0][1]

        return best_move

    def get_info(self) -> dict:
        """Return search statistics."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        nps = int(self.nodes_searched / elapsed) if elapsed > 0 else 0
        return {
            'nodes': self.nodes_searched,
            'time_ms': int(elapsed * 1000),
            'nps': nps,
        }
