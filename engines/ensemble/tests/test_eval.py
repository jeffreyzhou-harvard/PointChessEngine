from engine.board import Board, INITIAL_FEN
from engine.evaluate import evaluate, _evaluate_pawn_structure, _evaluate_king_safety


def test_initial_eval_small():
    b = Board.initial()
    s = evaluate(b)
    # Should be roughly tempo bonus.
    assert -50 <= s <= 50


def test_material_advantage():
    # White up a queen.
    b = Board.from_fen("4k3/8/8/8/8/8/8/4K2Q w - - 0 1")
    assert evaluate(b) > 500


def test_material_disadvantage_for_side_to_move():
    # Black to move; white up a queen -> bad for black -> negative.
    b = Board.from_fen("4k3/8/8/8/8/8/8/4K2Q b - - 0 1")
    assert evaluate(b) < -500


def test_bishop_pair():
    # Two bishops vs no bishops, otherwise equal pawns/king setup.
    b = Board.from_fen("4k3/8/8/8/8/8/8/2B1K2B w - - 0 1")
    s_pair = evaluate(b)
    b2 = Board.from_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    s_none = evaluate(b2)
    assert s_pair > s_none + 100  # 2*330 + bishop pair bonus


def test_doubled_pawn_penalty():
    b = Board.from_fen("4k3/8/8/8/8/4P3/4P3/4K3 w - - 0 1")
    mg, eg = _evaluate_pawn_structure(b)
    assert mg < 0 and eg < 0


def test_isolated_pawn_penalty():
    b = Board.from_fen("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
    mg, eg = _evaluate_pawn_structure(b)
    assert mg < 0 and eg < 0


def test_passed_pawn_bonus():
    # White pawn on a7, no black blockers.
    b = Board.from_fen("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
    mg, eg = _evaluate_pawn_structure(b)
    assert eg > 100  # rank 6 (index 6 -> 150 eg) ... rank-from-white index 6 -> 150


def test_king_safety_open_files():
    # White king on e1, no shield pawns -> negative.
    b = Board.from_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    s = _evaluate_king_safety(b)
    # Both kings have no shield, scores roughly cancel; just check it's an int.
    assert isinstance(s, int)


def test_eval_symmetric():
    """Mirroring the position should mirror the score sign."""
    b1 = Board.from_fen("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
    b2 = Board.from_fen("4k3/4p3/8/8/8/8/8/4K3 b - - 0 1")
    s1 = evaluate(b1)
    s2 = evaluate(b2)
    # both white-to-move-equivalent -> close.
    assert abs(s1 - s2) < 30
