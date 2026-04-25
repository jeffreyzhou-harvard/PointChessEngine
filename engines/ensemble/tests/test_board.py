from engine.board import Board, INITIAL_FEN, WHITE, BLACK
from engine.squares import algebraic_to_120, sq120_to_algebraic, MAILBOX64


def test_initial_fen_roundtrip():
    b = Board.initial()
    assert b.to_fen() == INITIAL_FEN


def test_fen_various():
    fens = [
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "8/8/8/8/8/8/8/4k2K w - - 0 1",
    ]
    for f in fens:
        b = Board.from_fen(f)
        assert b.to_fen() == f, (f, b.to_fen())


def test_squares_roundtrip():
    for s in ["a1", "h1", "a8", "h8", "e4", "d5"]:
        i = algebraic_to_120(s)
        assert sq120_to_algebraic(i) == s


def test_king_sq_cache():
    b = Board.initial()
    assert sq120_to_algebraic(b.king_sq[WHITE]) == "e1"
    assert sq120_to_algebraic(b.king_sq[BLACK]) == "e8"


def test_attack_basic():
    b = Board.initial()
    # No piece attacks d4 from white initially.
    assert b.is_square_attacked(algebraic_to_120("e3"), WHITE)  # pawn d2 or f2 attacks e3
    assert not b.is_square_attacked(algebraic_to_120("e4"), WHITE)


def test_zobrist_changes_on_move():
    from engine.movegen import generate_legal
    b = Board.initial()
    k0 = b.zobrist_key
    legal = generate_legal(b)
    m = next(m for m in legal if m.uci() == "e2e4")
    b.make_move(m)
    assert b.zobrist_key != k0
    b.unmake_move()
    assert b.zobrist_key == k0
    assert b.to_fen() == INITIAL_FEN
