"""Deterministic chess engine built from an RLM-style recursive decomposition.

The runtime intentionally does not call model APIs. The RLM contribution is the
build pattern: break a move decision into small inspectable evaluators, combine
their traces, then use a bounded search to choose among legal moves.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import chess


INF = 1_000_000
MATE_SCORE = 100_000
DEFAULT_MOVETIME_MS = 75
TIME_CHECK_INTERVAL = 256

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3,
    chess.D3,
    chess.E3,
    chess.F3,
    chess.C4,
    chess.F4,
    chess.C5,
    chess.F5,
    chess.C6,
    chess.D6,
    chess.E6,
    chess.F6,
}


@dataclass(frozen=True)
class SearchLimits:
    """Bounded search controls from UCI or Champion smoke tests."""

    depth: int = 2
    movetime_ms: int | None = DEFAULT_MOVETIME_MS


@dataclass(frozen=True)
class EvaluationSignal:
    """One feature contribution in centipawns from White's perspective."""

    name: str
    score_cp: int
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecursiveEvaluationTrace:
    """Inspectable output of the decomposed evaluator."""

    total_cp: int
    side_to_move_cp: int
    signals: tuple[EvaluationSignal, ...]


@dataclass(frozen=True)
class SearchResult:
    """Search output used by the UCI layer and tests."""

    bestmove: chess.Move | None
    score_cp: int
    depth: int
    nodes: int
    time_ms: int
    diagnostics: dict[str, Any] = field(default_factory=dict)


class SearchTimeout(Exception):
    """Internal control-flow exception for bounded search."""


class RLMChessEngine:
    """Small legal chess engine with recursive, traceable evaluation signals."""

    def __init__(self, default_depth: int = 2) -> None:
        self.default_depth = default_depth
        self.nodes = 0

    def generate_legal_moves(self, board: chess.Board) -> list[chess.Move]:
        return list(board.legal_moves)

    def evaluate(self, board: chess.Board) -> RecursiveEvaluationTrace:
        if board.is_checkmate():
            side_score = -MATE_SCORE
            white_score = side_score if board.turn == chess.WHITE else -side_score
            return RecursiveEvaluationTrace(
                total_cp=white_score,
                side_to_move_cp=side_score,
                signals=(EvaluationSignal("terminal_checkmate", white_score),),
            )
        if board.is_stalemate() or board.is_insufficient_material():
            return RecursiveEvaluationTrace(
                total_cp=0,
                side_to_move_cp=0,
                signals=(EvaluationSignal("terminal_draw", 0),),
            )

        signals = (
            self._material_signal(board),
            self._mobility_signal(board),
            self._center_signal(board),
            self._pawn_structure_signal(board),
            self._king_safety_signal(board),
            self._tactical_access_signal(board),
        )
        white_score = sum(signal.score_cp for signal in signals)
        side_score = white_score if board.turn == chess.WHITE else -white_score
        return RecursiveEvaluationTrace(total_cp=white_score, side_to_move_cp=side_score, signals=signals)

    def choose_move(self, board: chess.Board, limits: SearchLimits | None = None) -> SearchResult:
        limits = limits or SearchLimits(depth=self.default_depth)
        started = time.monotonic()
        legal_moves = self.generate_legal_moves(board)
        if not legal_moves:
            return SearchResult(
                bestmove=None,
                score_cp=self.evaluate(board).side_to_move_cp,
                depth=0,
                nodes=0,
                time_ms=0,
                diagnostics={"reason": "terminal_position"},
            )

        self.nodes = 0
        max_depth = max(1, min(int(limits.depth or self.default_depth), 4))
        deadline = None
        if limits.movetime_ms is not None:
            budget_seconds = max(0.01, limits.movetime_ms / 1000.0)
            deadline = started + budget_seconds * 0.92

        best_move = self._ordered_moves(board)[0]
        best_score = -INF
        completed_depth = 0
        principal_variation = [best_move.uci()]

        for depth in range(1, max_depth + 1):
            try:
                score, move = self._search_root(board, depth, deadline)
            except SearchTimeout:
                break
            if move is not None:
                best_move = move
                best_score = score
                completed_depth = depth
                principal_variation = [move.uci()]

        if completed_depth == 0:
            best_score = self._score_move_heuristic(board, best_move)

        elapsed_ms = int((time.monotonic() - started) * 1000)
        return SearchResult(
            bestmove=best_move,
            score_cp=int(best_score),
            depth=completed_depth,
            nodes=self.nodes,
            time_ms=elapsed_ms,
            diagnostics={
                "evaluation_style": "rlm_recursive_decomposition",
                "pv": principal_variation,
                "deadline_used": deadline is not None,
            },
        )

    def _search_root(
        self, board: chess.Board, depth: int, deadline: float | None
    ) -> tuple[int, chess.Move | None]:
        alpha = -INF
        beta = INF
        best_score = -INF
        best_move: chess.Move | None = None
        for move in self._ordered_moves(board):
            self._check_time(deadline)
            board.push(move)
            try:
                score = -self._negamax(board, depth - 1, -beta, -alpha, deadline, 1)
            finally:
                board.pop()
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, best_score)
        return best_score, best_move

    def _negamax(
        self,
        board: chess.Board,
        depth: int,
        alpha: int,
        beta: int,
        deadline: float | None,
        ply: int,
    ) -> int:
        self.nodes += 1
        if self.nodes % TIME_CHECK_INTERVAL == 0:
            self._check_time(deadline)

        if board.is_checkmate():
            return -MATE_SCORE + ply
        if board.is_stalemate() or board.is_insufficient_material():
            return 0
        if depth <= 0:
            return self.evaluate(board).side_to_move_cp

        best = -INF
        for move in self._ordered_moves(board):
            board.push(move)
            try:
                score = -self._negamax(board, depth - 1, -beta, -alpha, deadline, ply + 1)
            finally:
                board.pop()
            best = max(best, score)
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        return best

    def _ordered_moves(self, board: chess.Board) -> list[chess.Move]:
        return sorted(board.legal_moves, key=lambda move: self._score_move_heuristic(board, move), reverse=True)

    def _score_move_heuristic(self, board: chess.Board, move: chess.Move) -> int:
        score = 0
        if move.promotion:
            score += PIECE_VALUES.get(move.promotion, 0) + 700
        if board.gives_check(move):
            score += 600
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            if victim is None and board.is_en_passant(move):
                victim_value = PIECE_VALUES[chess.PAWN]
            else:
                victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
            attacker = board.piece_at(move.from_square)
            attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
            score += 10 * victim_value - attacker_value + 300
        if move.to_square in CENTER:
            score += 45
        elif move.to_square in EXTENDED_CENTER:
            score += 15
        return score

    def _check_time(self, deadline: float | None) -> None:
        if deadline is not None and time.monotonic() >= deadline:
            raise SearchTimeout

    def _material_signal(self, board: chess.Board) -> EvaluationSignal:
        score = 0
        detail: dict[str, int] = {}
        for piece_type, value in PIECE_VALUES.items():
            white_count = len(board.pieces(piece_type, chess.WHITE))
            black_count = len(board.pieces(piece_type, chess.BLACK))
            score += (white_count - black_count) * value
            detail[chess.piece_name(piece_type)] = white_count - black_count
        return EvaluationSignal("material", score, detail)

    def _mobility_signal(self, board: chess.Board) -> EvaluationSignal:
        white = self._legal_count_for(board, chess.WHITE)
        black = self._legal_count_for(board, chess.BLACK)
        return EvaluationSignal("mobility", (white - black) * 3, {"white": white, "black": black})

    def _center_signal(self, board: chess.Board) -> EvaluationSignal:
        score = 0
        for square in CENTER:
            piece = board.piece_at(square)
            if piece:
                score += 25 if piece.color == chess.WHITE else -25
        for square in EXTENDED_CENTER:
            piece = board.piece_at(square)
            if piece:
                score += 8 if piece.color == chess.WHITE else -8
        return EvaluationSignal("center_control", score)

    def _pawn_structure_signal(self, board: chess.Board) -> EvaluationSignal:
        white = self._pawn_structure_for(board, chess.WHITE)
        black = self._pawn_structure_for(board, chess.BLACK)
        return EvaluationSignal("pawn_structure", white - black, {"white": white, "black": black})

    def _king_safety_signal(self, board: chess.Board) -> EvaluationSignal:
        white = self._king_safety_for(board, chess.WHITE)
        black = self._king_safety_for(board, chess.BLACK)
        return EvaluationSignal("king_safety", white - black, {"white": white, "black": black})

    def _tactical_access_signal(self, board: chess.Board) -> EvaluationSignal:
        white = self._tactical_access_for(board, chess.WHITE)
        black = self._tactical_access_for(board, chess.BLACK)
        return EvaluationSignal("tactical_access", white - black, {"white": white, "black": black})

    def _legal_count_for(self, board: chess.Board, color: chess.Color) -> int:
        probe = board.copy(stack=False)
        probe.turn = color
        return probe.legal_moves.count()

    def _pawn_structure_for(self, board: chess.Board, color: chess.Color) -> int:
        own_pawns = board.pieces(chess.PAWN, color)
        enemy_pawns = board.pieces(chess.PAWN, not color)
        score = 0
        files = [chess.square_file(square) for square in own_pawns]
        occupied_files = set(files)
        for file_index in range(8):
            count = files.count(file_index)
            if count > 1:
                score -= 14 * (count - 1)

        for square in own_pawns:
            file_index = chess.square_file(square)
            rank_index = chess.square_rank(square)
            adjacent_files = [f for f in (file_index - 1, file_index + 1) if 0 <= f <= 7]
            if not any(f in occupied_files for f in adjacent_files):
                score -= 8
            if self._is_passed_pawn(square, color, enemy_pawns):
                advancement = rank_index if color == chess.WHITE else 7 - rank_index
                score += 12 + advancement * 4
        return score

    def _is_passed_pawn(self, square: chess.Square, color: chess.Color, enemy_pawns: chess.SquareSet) -> bool:
        file_index = chess.square_file(square)
        rank_index = chess.square_rank(square)
        direction = 1 if color == chess.WHITE else -1
        for file_candidate in (file_index - 1, file_index, file_index + 1):
            if not 0 <= file_candidate <= 7:
                continue
            rank_candidate = rank_index + direction
            while 0 <= rank_candidate <= 7:
                if chess.square(file_candidate, rank_candidate) in enemy_pawns:
                    return False
                rank_candidate += direction
        return True

    def _king_safety_for(self, board: chess.Board, color: chess.Color) -> int:
        king_square = board.king(color)
        if king_square is None:
            return -MATE_SCORE
        score = 0
        enemy_attackers = board.attackers(not color, king_square)
        score -= 18 * len(enemy_attackers)

        file_index = chess.square_file(king_square)
        rank_index = chess.square_rank(king_square)
        shield_rank = rank_index + (1 if color == chess.WHITE else -1)
        if 0 <= shield_rank <= 7:
            for shield_file in (file_index - 1, file_index, file_index + 1):
                if 0 <= shield_file <= 7:
                    piece = board.piece_at(chess.square(shield_file, shield_rank))
                    if piece == chess.Piece(chess.PAWN, color):
                        score += 10
        return score

    def _tactical_access_for(self, board: chess.Board, color: chess.Color) -> int:
        probe = board.copy(stack=False)
        probe.turn = color
        score = 0
        for move in probe.legal_moves:
            if probe.gives_check(move):
                score += 12
            if probe.is_capture(move):
                score += 6
            if move.promotion:
                score += 20
        return score
