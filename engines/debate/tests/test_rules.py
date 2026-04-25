"""Rules / movegen tests including perft."""

import pytest

from engine.board import Board, STARTING_FEN, move_from_uci, square_name
from engine.movegen import (
    generate_legal_moves, generate_pseudo_legal_moves,
    is_square_attacked, perft, in_check,
)


def test_starting_fen_roundtrip():
    b = Board.starting_position()
    assert b.to_fen() == STARTING_FEN


def test_starting_legal_moves_count():
    b = Board.starting_position()
    moves = generate_legal_moves(b, b.side_to_move)
    assert len(moves) == 20


def test_perft_starting():
    b = Board.starting_position()
    assert perft(b, 1) == 20
    assert perft(b, 2) == 400
    assert perft(b, 3) == 8902
    assert perft(b, 4) == 197281


def test_perft_kiwipete_depth_2():
    fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
    b = Board.from_fen(fen)
    # known values: depth 1 = 48, depth 2 = 2039, depth 3 = 97862
    assert perft(b, 1) == 48
    assert perft(b, 2) == 2039


def test_perft_position_3():
    """Position 3 from chessprogramming.org perft suite (endgame with EP)."""
    fen = "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"
    b = Board.from_fen(fen)
    assert perft(b, 1) == 14
    assert perft(b, 2) == 191
    assert perft(b, 3) == 2812


def test_perft_position_4():
    fen = "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1"
    b = Board.from_fen(fen)
    assert perft(b, 1) == 6
    assert perft(b, 2) == 264


def test_castling_through_check_blocked():
    # White king on e1, rook on h1, black rook on f8 attacks f1.
    fen = "4k2r/8/8/8/8/8/8/4K2R w Kk - 0 1"
    b = Board.from_fen(fen)
    moves = generate_legal_moves(b, 0)
    # Black rook on h8 is on its home, but kingside castle for white should be legal
    # because the squares aren't attacked by any black piece.
    assert any(m.from_sq == 4 and m.to_sq == 6 for m in moves)

    # Now place a rook on f8 attacking f1 -> kingside castle illegal
    fen2 = "5rk1/8/8/8/8/8/8/4K2R w K - 0 1"
    b2 = Board.from_fen(fen2)
    moves2 = generate_legal_moves(b2, 0)
    assert not any(m.from_sq == 4 and m.to_sq == 6 for m in moves2)


def test_en_passant_capture_legal():
    # White pawn on e5, black just played d7-d5 -> ep target d6
    fen = "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1"
    b = Board.from_fen(fen)
    moves = generate_legal_moves(b, 0)
    ep = [m for m in moves if (m.flags & 2)]
    assert len(ep) == 1
    assert square_name(ep[0].to_sq) == "d6"
    b.make_move(ep[0])
    # black pawn should have been removed
    assert b.squares[36] == 0  # e5 empty (1 from rank 5*8+4=36)? actually 4*8+3 = 35 was d5
    # d5 = file 3, rank 4 -> 35
    assert b.squares[35] == 0


def test_en_passant_discovered_check_illegal():
    # Position where ep capture would expose own king to a discovered check.
    # White king on e1, white pawn on e5, black pawn on d5, black rook on a5.
    # Capturing en passant exd6 removes both pawns from rank 5, exposing white king.
    # Wait, white king is on e1; rook on a5 attacks rank 5 not e1.
    # Use the classic: white king on h5, black rook on a5, white pawn on e5,
    # black pawn just moved d7-d5 -> ep target d6.
    # If white plays exd6 ep, both pawns leave rank 5 -> rook checks h5.
    fen = "4k3/8/8/r3pP1K/8/8/8/8 b - - 0 1"
    # Black to move plays d7-d5? Easier: set up directly with ep square.
    fen = "4k3/8/8/r2pP2K/8/8/8/8 w - d6 0 1"
    b = Board.from_fen(fen)
    moves = generate_legal_moves(b, 0)
    # Should NOT contain exd6 ep since it's illegal.
    ep_moves = [m for m in moves if (m.flags & 2)]
    assert len(ep_moves) == 0


def test_promotion_generates_four_choices():
    fen = "4k3/P7/8/8/8/8/8/4K3 w - - 0 1"
    b = Board.from_fen(fen)
    moves = generate_legal_moves(b, 0)
    promos = [m for m in moves if m.promo]
    assert len(promos) == 4


def test_make_unmake_restores_state():
    b = Board.starting_position()
    fen0 = b.to_fen()
    key0 = b.zobrist_key
    moves = generate_legal_moves(b, 0)
    for m in moves:
        b.make_move(m)
        b.unmake_move()
        assert b.to_fen() == fen0
        assert b.zobrist_key == key0


def test_make_unmake_deep():
    b = Board.from_fen("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
    fen0 = b.to_fen()
    key0 = b.zobrist_key
    import random
    rng = random.Random(42)
    for _ in range(50):
        moves = generate_legal_moves(b, b.side_to_move)
        if not moves:
            break
        m = rng.choice(moves)
        b.make_move(m)
    while b.history:
        b.unmake_move()
    assert b.to_fen() == fen0
    assert b.zobrist_key == key0


def test_attack_detection_basic():
    b = Board.from_fen("4k3/8/8/8/3q4/8/8/4K3 b - - 0 1")
    # black queen on d4 attacks e5? d4 = file 3 rank 3 -> idx 27
    # e5 = file 4 rank 4 -> 36; from d4 e5 is diag yes
    assert is_square_attacked(b, 36, 1)  # e5 attacked by black


def test_in_check_detection():
    # White king on e1, black queen on e8 -> white in check on open file
    fen = "4q3/8/8/8/8/8/8/4K3 w - - 0 1"
    b = Board.from_fen(fen)
    assert in_check(b, 0)


def test_uci_move_parsing():
    b = Board.starting_position()
    m = move_from_uci(b, "e2e4")
    assert m is not None
    assert m.flags & 8  # double pawn push
