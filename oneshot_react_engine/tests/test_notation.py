"""SAN and PGN tests."""

from oneshot_react_engine.core import Board, Move
from oneshot_react_engine.core.notation import board_to_pgn, move_to_san


def test_san_simple_pawn_move():
    b = Board()
    assert move_to_san(b, Move.from_uci("e2e4")) == "e4"


def test_san_knight_move():
    b = Board()
    assert move_to_san(b, Move.from_uci("g1f3")) == "Nf3"


def test_san_capture():
    b = Board()
    for m in ["e2e4", "d7d5"]:
        b.make_move(Move.from_uci(m))
    assert move_to_san(b, Move.from_uci("e4d5")) == "exd5"


def test_san_castling():
    b = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    assert move_to_san(b, Move.from_uci("e1g1")) == "O-O"
    assert move_to_san(b, Move.from_uci("e1c1")) == "O-O-O"


def test_san_check_marker():
    b = Board("4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1")
    assert move_to_san(b, Move.from_uci("e2e7")).endswith("+")


def test_san_mate_marker():
    b = Board("6k1/5ppp/8/8/8/8/8/4K2Q w - - 0 1")
    assert move_to_san(b, Move.from_uci("h1a8")).endswith("#")


def test_san_promotion():
    # Black king parked off any line from a8; promotion should not produce a check marker.
    b = Board("8/P7/7k/8/8/8/8/2K5 w - - 0 1")
    assert move_to_san(b, Move.from_uci("a7a8q")) == "a8=Q"


def test_san_promotion_with_check():
    # a8=Q+ when the new queen attacks the enemy king along the 8th rank.
    b = Board("8/P7/8/8/8/8/8/k6K w - - 0 1")
    assert move_to_san(b, Move.from_uci("a7a8q")) == "a8=Q+"


def test_pgn_export_contains_moves():
    b = Board()
    for m in ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]:
        b.make_move(Move.from_uci(m))
    pgn = board_to_pgn(b)
    assert "[White " in pgn
    assert "1. e4 e5 2. Nf3 Nc6 3. Bb5" in pgn
