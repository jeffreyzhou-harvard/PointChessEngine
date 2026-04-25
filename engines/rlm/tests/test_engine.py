from __future__ import annotations

import chess

from engines.rlm import RLMChessEngine, SearchLimits


def test_starting_position_has_legal_moves() -> None:
    engine = RLMChessEngine()
    board = chess.Board()

    moves = engine.generate_legal_moves(board)

    assert len(moves) == 20
    assert all(move in board.legal_moves for move in moves)


def test_choose_move_returns_legal_startpos_move() -> None:
    engine = RLMChessEngine()
    board = chess.Board()

    result = engine.choose_move(board, SearchLimits(depth=2, movetime_ms=100))

    assert result.bestmove in board.legal_moves
    assert result.nodes > 0
    assert result.diagnostics["evaluation_style"] == "rlm_recursive_decomposition"


def test_material_advantage_scores_better_for_white() -> None:
    engine = RLMChessEngine()
    equal = chess.Board("8/8/8/8/8/8/8/K6k w - - 0 1")
    white_queen = chess.Board("8/8/8/8/8/8/8/KQ5k w - - 0 1")

    assert engine.evaluate(white_queen).total_cp > engine.evaluate(equal).total_cp


def test_search_does_not_mutate_board() -> None:
    engine = RLMChessEngine()
    board = chess.Board()
    before = board.fen()

    engine.choose_move(board, SearchLimits(depth=2, movetime_ms=100))

    assert board.fen() == before


def test_fixed_depth_is_deterministic() -> None:
    engine = RLMChessEngine()
    board = chess.Board()

    first = engine.choose_move(board, SearchLimits(depth=2, movetime_ms=None))
    second = engine.choose_move(board, SearchLimits(depth=2, movetime_ms=None))

    assert first.bestmove == second.bestmove
