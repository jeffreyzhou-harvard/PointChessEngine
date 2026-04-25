"""Board, FEN, and move execution tests."""

from oneshot_react_engine.core import Board, Move, STARTING_FEN
from oneshot_react_engine.core.fen import board_to_fen, parse_fen
from oneshot_react_engine.core.pieces import Color, PieceType


def test_starting_position_legal_moves():
    b = Board()
    assert len(b.legal_moves()) == 20


def test_fen_roundtrip_starting():
    b = Board()
    assert b.to_fen() == STARTING_FEN


def test_fen_roundtrip_kiwipete():
    fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
    b = Board(fen)
    assert b.to_fen() == fen


def test_fen_roundtrip_with_en_passant():
    fen = "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3"
    b = Board(fen)
    assert b.to_fen() == fen


def test_make_unmake_restores_state():
    b = Board()
    fen_before = b.to_fen()
    moves = b.legal_moves()
    b.make_move(moves[0])
    b.unmake_move()
    assert b.to_fen() == fen_before


def test_make_move_rejects_illegal():
    b = Board()
    bad = Move.from_uci("e2e5")  # pawn can't jump 3
    assert b.make_move(bad) is False


def test_pawn_promotion_to_queen():
    b = Board("8/P7/8/8/8/8/8/k6K w - - 0 1")
    move = Move.from_uci("a7a8q")
    assert b.make_move(move)
    p = b.piece_at(move.to_sq)
    assert p is not None
    assert p.piece_type == PieceType.QUEEN
    assert p.color == Color.WHITE


def test_en_passant_capture_and_undo():
    b = Board("rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3")
    ep_move = Move.from_uci("e5d6")
    assert ep_move in b.legal_moves()
    assert b.make_move(ep_move)
    # The black pawn that double-pushed should be gone
    assert b.piece_at(Move.from_uci("d5d5").from_sq) is None
    b.unmake_move()
    # Restored
    assert b.to_fen() == "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3"


def test_castling_kingside():
    b = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    move = Move.from_uci("e1g1")
    assert move in b.legal_moves()
    b.make_move(move)
    assert b.piece_at(Move.from_uci("g1g1").from_sq).piece_type == PieceType.KING
    assert b.piece_at(Move.from_uci("f1f1").from_sq).piece_type == PieceType.ROOK


def test_castling_queenside():
    b = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    move = Move.from_uci("e1c1")
    assert move in b.legal_moves()
    b.make_move(move)
    assert b.piece_at(Move.from_uci("c1c1").from_sq).piece_type == PieceType.KING
    assert b.piece_at(Move.from_uci("d1d1").from_sq).piece_type == PieceType.ROOK


def test_castling_disallowed_through_check():
    # Black rook on e8 attacks e1; king can't castle through e1 (start) anyway,
    # but let's place an attacker on f1 path:
    b = Board("4k3/5q2/8/8/8/8/8/R3K2R w KQ - 0 1")
    # Black queen on f7 attacks f-file? No - put it on f3 to attack f1:
    b = Board("4k3/8/8/8/8/5q2/8/R3K2R w KQ - 0 1")
    legal = [m.uci() for m in b.legal_moves()]
    assert "e1g1" not in legal


def test_castling_rights_lost_on_rook_move():
    b = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    b.make_move(Move.from_uci("h1h2"))
    fen = b.to_fen().split()
    assert "K" not in fen[2]
    assert "Q" in fen[2]


def test_checkmate_fools_mate():
    b = Board()
    for m in ["f2f3", "e7e5", "g2g4", "d8h4"]:
        assert b.make_move(Move.from_uci(m))
    assert b.is_checkmate()
    over, reason = b.is_game_over()
    assert over
    assert "Black wins" in reason


def test_stalemate_position():
    b = Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert b.is_stalemate()
    assert not b.is_checkmate()
    assert b.is_draw()


def test_insufficient_material():
    assert Board("8/8/8/4k3/8/4K3/8/8 w - - 0 1").is_insufficient_material()
    assert Board("8/8/8/4k3/8/4KN2/8/8 w - - 0 1").is_insufficient_material()
    assert Board("8/8/8/4k3/8/4KB2/8/8 w - - 0 1").is_insufficient_material()
    # K + N + N vs K is technically insufficient too, but our rule only catches
    # the simpler cases; ensure at least the basic ones.
    assert not Board(STARTING_FEN).is_insufficient_material()


def test_fifty_move_rule():
    b = Board("4k3/8/4K3/8/8/8/8/R7 w - - 99 50")
    b.make_move(Move.from_uci("a1a2"))
    assert b.is_fifty_move_rule()


def test_threefold_repetition():
    b = Board()
    moves = ["g1f3", "g8f6", "f3g1", "f6g8"] * 2 + ["g1f3", "g8f6"]
    for m in moves:
        b.make_move(Move.from_uci(m))
    assert b.is_threefold_repetition()
