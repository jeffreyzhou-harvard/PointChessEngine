"""Stage 4: legal move generation, make/unmake, check / mate / stalemate.

Coverage focuses on the tricky cases the prompt called out:
    - pinned pieces (absolute pin to king)
    - castling: out of check, through check, into check
    - en-passant legality, including the discovered-check edge case
    - checkmate detection
    - stalemate detection

Plus enough make/unmake correctness tests to be confident that the
legality filter (which depends on make/unmake round-trip) is reliable.
"""

from __future__ import annotations

import pytest

from chainofthought_engine.core import Board, Color, Piece, PieceType
from chainofthought_engine.core.move import Move
from chainofthought_engine.core.movegen import is_square_attacked
from chainofthought_engine.core.types import square_from_algebraic as sq


def uci_set(moves):
    return {m.uci() for m in moves}


def from_sq(moves, square):
    return [m for m in moves if m.from_sq == square]


# ---------------------------------------------------------------------------
# attack detection sanity
# ---------------------------------------------------------------------------


class TestIsSquareAttacked:
    def test_starting_position_white_attacks_e3_via_pawn(self):
        b = Board.starting_position()
        # f2 and d2 pawns each attack e3.
        assert is_square_attacked(b, sq("e3"), Color.WHITE)

    def test_starting_position_black_does_not_attack_e3(self):
        b = Board.starting_position()
        assert not is_square_attacked(b, sq("e3"), Color.BLACK)

    def test_knight_attacks(self):
        b = Board.from_fen("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1")
        # Nd4 attacks 8 L-squares including b3, b5, c6, e6, f5, f3, e2, c2.
        for s in ("b3", "b5", "c6", "e6", "f5", "f3", "e2", "c2"):
            assert is_square_attacked(b, sq(s), Color.WHITE)
        assert not is_square_attacked(b, sq("d5"), Color.WHITE)

    def test_rook_attack_blocked_by_intervening_piece(self):
        # White rook a1, white pawn a4: rook does not attack a5.
        b = Board.from_fen("4k3/8/8/8/P7/8/8/R3K3 w - - 0 1")
        assert is_square_attacked(b, sq("a3"), Color.WHITE)
        assert is_square_attacked(b, sq("a4"), Color.WHITE)
        assert not is_square_attacked(b, sq("a5"), Color.WHITE)

    def test_pawn_attacker_direction(self):
        # White pawn on d4 attacks c5 and e5 (forward diagonals only).
        b = Board.from_fen("4k3/8/8/8/3P4/8/8/4K3 w - - 0 1")
        assert is_square_attacked(b, sq("c5"), Color.WHITE)
        assert is_square_attacked(b, sq("e5"), Color.WHITE)
        assert not is_square_attacked(b, sq("c3"), Color.WHITE)


# ---------------------------------------------------------------------------
# make / unmake round-trip
# ---------------------------------------------------------------------------


class TestMakeUnmakeRoundTrip:
    def test_normal_pawn_push(self):
        b = Board.starting_position()
        original_fen = b.fen()
        b.make_move(Move.from_uci("e2e4"))
        assert b.fen() == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        assert b.move_history_length == 1
        b.unmake_move()
        assert b.fen() == original_fen
        assert b.move_history_length == 0

    def test_capture(self):
        b = Board.from_fen("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1")
        original_fen = b.fen()
        b.make_move(Move.from_uci("e4d5"))
        # Halfmove clock resets on capture; black pawn gone.
        assert b.piece_at(sq("d5")) == Piece(Color.WHITE, PieceType.PAWN)
        assert b.piece_at(sq("e4")) is None
        assert b.halfmove_clock == 0
        b.unmake_move()
        assert b.fen() == original_fen

    def test_castling_kingside(self):
        b = Board.from_fen("4k3/8/8/8/8/8/8/4K2R w K - 0 1")
        original_fen = b.fen()
        b.make_move(Move.from_uci("e1g1"))
        assert b.piece_at(sq("g1")) == Piece(Color.WHITE, PieceType.KING)
        assert b.piece_at(sq("f1")) == Piece(Color.WHITE, PieceType.ROOK)
        assert b.piece_at(sq("e1")) is None
        assert b.piece_at(sq("h1")) is None
        # Castling rights gone for white.
        assert not b.castling_rights.white_kingside
        assert not b.castling_rights.white_queenside
        b.unmake_move()
        assert b.fen() == original_fen

    def test_castling_queenside(self):
        b = Board.from_fen("4k3/8/8/8/8/8/8/R3K3 w Q - 0 1")
        original_fen = b.fen()
        b.make_move(Move.from_uci("e1c1"))
        assert b.piece_at(sq("c1")) == Piece(Color.WHITE, PieceType.KING)
        assert b.piece_at(sq("d1")) == Piece(Color.WHITE, PieceType.ROOK)
        assert b.piece_at(sq("a1")) is None
        b.unmake_move()
        assert b.fen() == original_fen

    def test_en_passant_capture(self):
        # White d5 takes black c5 ep on c6 (after black just played c7-c5).
        b = Board.from_fen("4k3/8/8/2pP4/8/8/8/4K3 w - c6 0 1")
        original_fen = b.fen()
        b.make_move(Move.from_uci("d5c6"))
        assert b.piece_at(sq("c6")) == Piece(Color.WHITE, PieceType.PAWN)
        assert b.piece_at(sq("d5")) is None
        assert b.piece_at(sq("c5")) is None  # captured pawn removed from c5
        b.unmake_move()
        assert b.fen() == original_fen

    def test_promotion(self):
        b = Board.from_fen("7k/4P3/8/8/8/8/8/4K3 w - - 0 1")
        original_fen = b.fen()
        b.make_move(Move.from_uci("e7e8q"))
        assert b.piece_at(sq("e8")) == Piece(Color.WHITE, PieceType.QUEEN)
        assert b.piece_at(sq("e7")) is None
        b.unmake_move()
        assert b.fen() == original_fen
        # The pawn must come back as a PAWN, not a queen.
        assert b.piece_at(sq("e7")) == Piece(Color.WHITE, PieceType.PAWN)

    def test_promotion_capture(self):
        b = Board.from_fen("r6k/1P6/8/8/8/8/8/4K3 w - - 0 1")
        original_fen = b.fen()
        b.make_move(Move.from_uci("b7a8q"))
        assert b.piece_at(sq("a8")) == Piece(Color.WHITE, PieceType.QUEEN)
        b.unmake_move()
        assert b.fen() == original_fen

    def test_castling_rights_drop_when_rook_captured_in_corner(self):
        # White bishop captures black rook on h8: black loses K-side right.
        b = Board.from_fen("4k2r/6B1/8/8/8/8/8/4K3 w k - 0 1")
        b.make_move(Move.from_uci("g7h8"))
        assert not b.castling_rights.black_kingside

    def test_fullmove_increments_after_black(self):
        b = Board.from_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        b.make_move(Move.from_uci("e2e4"))
        assert b.fullmove_number == 1
        b.make_move(Move.from_uci("e7e5"))
        assert b.fullmove_number == 2

    def test_unmake_with_empty_history_raises(self):
        with pytest.raises(IndexError):
            Board.starting_position().unmake_move()

    def test_long_round_trip(self):
        b = Board.starting_position()
        original_fen = b.fen()
        moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"]
        for m in moves:
            b.make_move(Move.from_uci(m))
        for _ in moves:
            b.unmake_move()
        assert b.fen() == original_fen
        assert b.move_history_length == 0


# ---------------------------------------------------------------------------
# pinned pieces
# ---------------------------------------------------------------------------


class TestPinnedPieces:
    def test_rook_pinned_to_king_on_file(self):
        # White rook on e2 pinned to e1 king by black queen on e8.
        # Legal Re2 moves: only along the e-file (e3-e7, plus capture e8).
        # Pseudo-legal Re2 moves: file moves + horizontal moves.
        b = Board.from_fen("4q3/k7/8/8/8/8/4R3/4K3 w - - 0 1")

        pseudo = uci_set(from_sq(b.pseudo_legal_moves(), sq("e2")))
        legal = uci_set(from_sq(b.legal_moves(), sq("e2")))

        # Horizontal rook moves are pseudo-legal but not legal.
        for off_file in ("a2", "b2", "c2", "d2", "f2", "g2", "h2"):
            assert f"e2{off_file}" in pseudo
            assert f"e2{off_file}" not in legal

        # File moves remain legal.
        for to in ("e3", "e4", "e5", "e6", "e7", "e8"):
            assert f"e2{to}" in legal

    def test_bishop_pinned_diagonally(self):
        # White bishop on d2 pinned to e1 king by black bishop on a5.
        # Pin diagonal: a5-b4-c3-d2-e1. Legal bishop moves: only along
        # that diagonal (c3, b4, a5 capture).
        b = Board.from_fen("4k3/8/8/b7/8/8/3B4/4K3 w - - 0 1")

        legal_d2 = uci_set(from_sq(b.legal_moves(), sq("d2")))

        # Stays on the pin diagonal:
        assert legal_d2 == {"d2c3", "d2b4", "d2a5"}

    def test_pinned_knight_has_no_legal_moves(self):
        # A pinned knight cannot move at all (its move would always
        # break the pin since knight jumps off-line).
        # White knight on e2 pinned by black rook on e8 to white king on e1.
        b = Board.from_fen("4r3/k7/8/8/8/8/4N3/4K3 w - - 0 1")

        legal_e2 = uci_set(from_sq(b.legal_moves(), sq("e2")))
        assert legal_e2 == set()

    def test_only_legal_moves_in_check_block_or_capture_or_run(self):
        # White king in check from black rook on e8. Only legal options:
        # block on e2..e7 (no white piece can; nothing else here), capture
        # the rook (no white piece can reach e8), or move the king off
        # the e-file. The white king can step to d1, d2, f1, f2 (none
        # attacked by the rook).
        b = Board.from_fen("4r3/k7/8/8/8/8/8/4K3 w - - 0 1")
        legal = uci_set(b.legal_moves())
        assert legal == {"e1d1", "e1d2", "e1f1", "e1f2"}


# ---------------------------------------------------------------------------
# castling legality
# ---------------------------------------------------------------------------


class TestCastlingLegality:
    def test_cannot_castle_out_of_check(self):
        # Black bishop on a5 attacks e1 (a5-b4-c3-d2-e1). King is in check.
        b = Board.from_fen("4k3/8/8/b7/8/8/8/R3K2R w KQ - 0 1")
        legal = uci_set(b.legal_moves())
        assert "e1g1" not in legal
        assert "e1c1" not in legal

    def test_cannot_castle_through_check_kingside(self):
        # Black rook on f8 attacks f1 -- king transits through check.
        b = Board.from_fen("4k1r1/8/8/8/8/8/8/4K2R w K - 0 1")
        legal = uci_set(b.legal_moves())
        assert "e1g1" not in legal
        # Pseudo-legal generator still emits it.
        assert "e1g1" in uci_set(b.pseudo_legal_moves())

    def test_cannot_castle_into_check_kingside(self):
        # Black rook on g8 attacks g1 -- king lands on attacked square.
        b = Board.from_fen("4k1r1/8/8/8/8/8/8/4K2R w K - 0 1")
        # Same FEN as previous; either f1 or g1 attack is enough.
        # Build a stricter case: rook on g8 only.
        b2 = Board.from_fen("6r1/4k3/8/8/8/8/8/4K2R w K - 0 1")
        legal = uci_set(b2.legal_moves())
        assert "e1g1" not in legal

    def test_cannot_castle_through_check_queenside(self):
        # Black rook on d8 attacks d1 -- king transits through check.
        b = Board.from_fen("3rk3/8/8/8/8/8/8/R3K3 w Q - 0 1")
        legal = uci_set(b.legal_moves())
        assert "e1c1" not in legal

    def test_can_castle_queenside_when_only_b1_attacked(self):
        # Black rook on b8 attacks b1, but the king transits d1 and lands
        # on c1. b1 is irrelevant to castling legality.
        b = Board.from_fen("1r2k3/8/8/8/8/8/8/R3K3 w Q - 0 1")
        legal = uci_set(b.legal_moves())
        assert "e1c1" in legal

    def test_castle_remains_legal_when_path_safe(self):
        # No attackers; king-side castling should be legal.
        b = Board.from_fen("4k3/8/8/8/8/8/8/4K2R w K - 0 1")
        assert "e1g1" in uci_set(b.legal_moves())

    def test_black_castling_legality_mirrors_white(self):
        # Through check: white rook on f1 attacks f8.
        b = Board.from_fen("4k2r/8/8/8/8/8/8/4KR2 b k - 0 1")
        assert "e8g8" not in uci_set(b.legal_moves())


# ---------------------------------------------------------------------------
# en-passant legality (incl. discovered check)
# ---------------------------------------------------------------------------


class TestEnPassantLegality:
    def test_normal_ep_is_legal(self):
        # No exposure: standard ep capture.
        b = Board.from_fen("4k3/8/8/2pP4/8/8/8/4K3 w - c6 0 1")
        legal = uci_set(b.legal_moves())
        assert "d5c6" in legal

    def test_ep_exposes_king_on_rank_is_illegal(self):
        # The classical pin-via-en-passant edge case.
        # Position: white king a5, white pawn b5, black pawn c5
        # (just played c7-c5, ep target c6), black rook h5,
        # black king h8. Playing bxc6 ep would empty rank 5 between
        # the white king and the black rook -> discovered check.
        b = Board.from_fen("7k/8/8/KPp4r/8/8/8/8 w - c6 0 1")

        # The pseudo-legal generator MUST emit b5c6 (it doesn't know
        # about discovered checks).
        pseudo = uci_set(b.pseudo_legal_moves())
        assert "b5c6" in pseudo

        # The legality filter MUST drop it.
        legal = uci_set(b.legal_moves())
        assert "b5c6" not in legal

    def test_ep_does_not_expose_king_when_blocker_remains(self):
        # Same shape but with another black piece between rook and king
        # so removing the captured pawn does NOT expose the king.
        b = Board.from_fen("7k/8/8/KPp1n2r/8/8/8/8 w - c6 0 1")
        legal = uci_set(b.legal_moves())
        assert "b5c6" in legal


# ---------------------------------------------------------------------------
# check, checkmate, stalemate
# ---------------------------------------------------------------------------


class TestCheckDetection:
    def test_starting_position_not_in_check(self):
        b = Board.starting_position()
        assert not b.is_check()

    def test_simple_check(self):
        # Black queen on e2 checks white king on e1.
        b = Board.from_fen("4k3/8/8/8/8/8/4q3/4K3 w - - 0 1")
        assert b.is_check()

    def test_blocked_attack_is_not_check(self):
        # Black queen on e8, white pawn on e2 in front of king on e1.
        b = Board.from_fen("4q3/8/8/8/8/8/4P3/4K3 w - - 0 1")
        assert not b.is_check()


class TestCheckmate:
    def test_back_rank_mate(self):
        # Black king g8, white rook a8 (just played Ra8#). King escape
        # squares f8/h8 attacked by rook; f7/g7/h7 blocked by black pawns.
        b = Board.from_fen("R5k1/5ppp/8/8/8/8/8/6K1 b - - 0 1")
        assert b.is_check()
        assert b.is_checkmate()
        assert not b.is_stalemate()
        assert b.legal_moves() == []

    def test_fools_mate(self):
        # 1.f3 e5 2.g4 Qh4# -- white to move, white in checkmate.
        b = Board.from_fen(
            "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
        )
        assert b.is_check()
        assert b.is_checkmate()

    def test_check_but_not_mate(self):
        # White king can step away.
        b = Board.from_fen("4k3/8/8/8/8/8/4q3/4K3 w - - 0 1")
        assert b.is_check()
        assert not b.is_checkmate()

    def test_smothered_mate(self):
        # Classic smothered mate pattern.
        b = Board.from_fen("6rk/6pp/8/8/8/8/8/3N3K w - - 0 1")
        # White Nf7 / Nh7 pattern: I'll set up the actual mate.
        # Position after 1...Nf2# with king cornered and own pieces blocking.
        # Use a simpler smothered mate FEN:
        b = Board.from_fen("6rk/5Npp/8/8/8/8/8/7K b - - 0 1")
        assert b.is_check()
        assert b.is_checkmate()


class TestStalemate:
    def test_classic_stalemate(self):
        # Black king h8, white king f6, white queen g6.
        # Black king has no legal squares, but is NOT in check.
        b = Board.from_fen("7k/8/5KQ1/8/8/8/8/8 b - - 0 1")
        assert not b.is_check()
        assert b.is_stalemate()
        assert not b.is_checkmate()
        assert b.legal_moves() == []

    def test_pinned_pawn_stalemate(self):
        # Stalemate where the pin filter is what makes it stalemate.
        #
        #   Black king h8, black pawn g7.
        #   White queen a1: pins g7 along the a1-h8 diagonal.
        #   White pawn g6: blocks pushes AND attacks h7.
        #   White knight h6: attacks g8 AND is the pawn's only
        #                    pseudo-legal capture target (g7xh6),
        #                    which the pin must drop.
        #   White king e1: off-stage.
        #
        # Pseudo-legal black moves: Kg8, Kh7, g7xh6. All three are
        # filtered out by the legality filter:
        #   Kg8 attacked by Nh6, Kh7 attacked by pg6, g7xh6 is pinned.
        b = Board.from_fen("7k/6p1/6PN/8/8/8/8/Q3K3 b - - 0 1")
        assert not b.is_check()
        # Sanity: the pin-only move is pseudo-legal but not legal.
        assert "g7h6" in uci_set(b.pseudo_legal_moves())
        assert "g7h6" not in uci_set(b.legal_moves())
        assert b.is_stalemate()
        assert b.legal_moves() == []


# ---------------------------------------------------------------------------
# legal vs pseudo-legal counts on canonical positions
# ---------------------------------------------------------------------------


class TestLegalVsPseudoLegalCounts:
    def test_starting_position_20_legal(self):
        # No pinned pieces, no checks; legal == pseudo-legal == 20.
        b = Board.starting_position()
        assert len(b.pseudo_legal_moves()) == 20
        assert len(b.legal_moves()) == 20

    def test_kiwipete_legal_count_is_48(self):
        # Standard perft(1) for Kiwipete is 48.
        b = Board.from_fen(
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        )
        assert len(b.legal_moves()) == 48
