"""Move generation tests including perft."""
from engine.board import Board
from engine.movegen import generate_legal


def perft(board: Board, depth: int) -> int:
    if depth == 0:
        return 1
    moves = generate_legal(board)
    if depth == 1:
        return len(moves)
    n = 0
    for m in moves:
        board.make_move(m)
        n += perft(board, depth - 1)
        board.unmake_move()
    return n


def test_perft_initial_d1_d2_d3():
    b = Board.initial()
    assert perft(b, 1) == 20
    assert perft(b, 2) == 400
    assert perft(b, 3) == 8902


def test_perft_initial_d4():
    b = Board.initial()
    assert perft(b, 4) == 197281


def test_perft_kiwipete_d1_d2_d3():
    # Standard "Kiwipete" position.
    fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
    b = Board.from_fen(fen)
    assert perft(b, 1) == 48
    assert perft(b, 2) == 2039
    assert perft(b, 3) == 97862


def test_perft_position3_d1_d4():
    # CPW perft position 3.
    fen = "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"
    b = Board.from_fen(fen)
    assert perft(b, 1) == 14
    assert perft(b, 2) == 191
    assert perft(b, 3) == 2812
    assert perft(b, 4) == 43238


def test_perft_position4_d1_d3():
    # CPW perft position 4 (mirrors).
    fen = "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1"
    b = Board.from_fen(fen)
    assert perft(b, 1) == 6
    assert perft(b, 2) == 264
    assert perft(b, 3) == 9467


def test_castling_generated():
    fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
    b = Board.from_fen(fen)
    moves = [m.uci() for m in generate_legal(b)]
    assert "e1g1" in moves
    assert "e1c1" in moves


def test_no_castle_through_check():
    # Bishop on a6 attacks f1; black on e8 with no rooks — verify white can't castle KS through f1.
    fen = "4k3/8/b7/8/8/8/8/R3K2R w KQ - 0 1"
    b = Board.from_fen(fen)
    moves = [m.uci() for m in generate_legal(b)]
    # Bishop on a6 attacks f1 -> kingside castle illegal (transit f1).
    assert "e1g1" not in moves


def test_promotion_moves():
    fen = "8/P7/8/8/8/8/8/4k2K w - - 0 1"
    b = Board.from_fen(fen)
    moves = [m.uci() for m in generate_legal(b)]
    for promo in "qrbn":
        assert f"a7a8{promo}" in moves


def test_en_passant():
    fen = "rnbqkbnr/pp1ppppp/8/2pP4/8/8/PPP1PPPP/RNBQKBNR w KQkq c6 0 2"
    b = Board.from_fen(fen)
    moves = [m.uci() for m in generate_legal(b)]
    assert "d5c6" in moves
