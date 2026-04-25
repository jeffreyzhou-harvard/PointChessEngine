"""Evaluation tests."""

from engine.board import Board
from engine.evaluate import evaluate, _material_pst_score


def test_starting_position_eval_near_zero():
    b = Board.starting_position()
    score = evaluate(b)
    # Starting position should be near-symmetric
    assert abs(score) < 50


def test_extra_queen_for_white_is_positive():
    b = Board.from_fen("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
    # White to move, has a queen advantage
    s = evaluate(b)
    assert s > 800


def test_extra_queen_for_black_is_negative_for_white_to_move():
    b = Board.from_fen("3qk3/8/8/8/8/8/8/4K3 w - - 0 1")
    s = evaluate(b)
    assert s < -800


def test_eval_symmetric_under_color_flip_for_material():
    # Mirror the position; the side-to-move-perspective score should be ~equal.
    fen_w = "4k3/8/8/8/8/3N4/8/4K3 w - - 0 1"
    fen_b = "4k3/8/3n4/8/8/8/8/4K3 b - - 0 1"
    sw = evaluate(Board.from_fen(fen_w))
    sb = evaluate(Board.from_fen(fen_b))
    assert abs(sw - sb) < 20


def test_bishop_pair_bonus():
    # White has bishop pair, black does not
    fen = "4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1"
    b = Board.from_fen(fen)
    mg, eg, phase = _material_pst_score(b)
    s = evaluate(b)
    # roughly material+pst plus +30..+50 bishop pair
    assert s > 600


def test_passed_pawn_bonus():
    # White passed pawn on a7 vs no opposing pawns near it
    fen = "4k3/P7/8/8/8/8/8/4K3 w - - 0 1"
    b = Board.from_fen(fen)
    s = evaluate(b)
    # Should be quite positive (advanced passed pawn + endgame king PST)
    assert s > 100
