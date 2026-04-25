"""Stage 3: pseudo-legal move generation.

Pseudo-legal means: piece-rules + occupancy obeyed, NOT filtered for
own-king-in-check. So a king move into check, an en-passant that
exposes the king on the rank, or a castle through an attacked square
SHOULD all appear in this stage's output. Those will be filtered out
by the legality filter in stage 4.

Tests are organized one class per piece type plus a few cross-cutting
tests (initial position count, pseudo-legal-only moves).
"""

from __future__ import annotations

import pytest

from engines.chainofthought.core import Board, CastlingRights, Color, Piece, PieceType
from engines.chainofthought.core.move import Move
from engines.chainofthought.core.movegen import (
    PROMOTION_PIECES,
    generate_pseudo_legal_moves,
    generate_pseudo_legal_moves_for_square,
)
from engines.chainofthought.core.types import square_from_algebraic as sq


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def uci_set(moves):
    return {m.uci() for m in moves}


def from_sq(moves, square):
    return [m for m in moves if m.from_sq == square]


# ---------------------------------------------------------------------------
# initial position
# ---------------------------------------------------------------------------


class TestInitialPosition:
    def test_count_is_20(self):
        # 16 pawn moves (each pawn: single + double push) + 4 knight moves.
        b = Board.starting_position()
        moves = generate_pseudo_legal_moves(b)
        assert len(moves) == 20

    def test_white_pawn_moves(self):
        b = Board.starting_position()
        e2 = sq("e2")
        e2_moves = uci_set(from_sq(generate_pseudo_legal_moves(b), e2))
        assert e2_moves == {"e2e3", "e2e4"}

    def test_white_knight_moves(self):
        b = Board.starting_position()
        b1 = sq("b1")
        b1_moves = uci_set(from_sq(generate_pseudo_legal_moves(b), b1))
        assert b1_moves == {"b1a3", "b1c3"}

    def test_no_castling_or_promotion_or_ep_in_initial(self):
        b = Board.starting_position()
        moves = generate_pseudo_legal_moves(b)
        for m in moves:
            assert m.promotion is None
            # No king moves at all from start
            assert b.piece_at(m.from_sq).type is not PieceType.KING

    def test_black_to_move_count(self):
        # Same shape, mirrored
        b = Board.from_fen(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1"
        )
        moves = generate_pseudo_legal_moves(b)
        assert len(moves) == 20


# ---------------------------------------------------------------------------
# pawns
# ---------------------------------------------------------------------------


class TestPawn:
    def test_white_single_and_double_push(self):
        b = Board.from_fen("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e2")))
        assert moves == {"e2e3", "e2e4"}

    def test_white_no_double_when_not_on_starting_rank(self):
        b = Board.from_fen("4k3/8/8/8/8/4P3/8/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e3")))
        assert moves == {"e3e4"}

    def test_white_blocked_completely(self):
        b = Board.from_fen("4k3/8/8/8/8/4n3/4P3/4K3 w - - 0 1")
        # Knight on e3 blocks both push squares; no captures available.
        assert uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e2"))) == set()

    def test_white_double_blocked_only(self):
        # Single push e3 is open, but e4 is blocked - no double push.
        b = Board.from_fen("4k3/8/8/8/4n3/8/4P3/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e2")))
        assert moves == {"e2e3"}

    def test_white_captures_both_diagonals(self):
        # Two black pieces to capture diagonally; pawn also pushes.
        b = Board.from_fen("4k3/8/8/8/3p1p2/4P3/8/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e3")))
        assert moves == {"e3e4", "e3d4", "e3f4"}

    def test_white_no_capture_on_friendly(self):
        b = Board.from_fen("4k3/8/8/8/3P1P2/4P3/8/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e3")))
        assert moves == {"e3e4"}

    def test_pawn_does_not_wrap_files(self):
        # White pawn on a2: only b3 is a valid capture target, never h3.
        b = Board.from_fen("4k3/8/8/8/8/1n6/P7/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("a2")))
        assert moves == {"a2a3", "a2a4", "a2b3"}

        b = Board.from_fen("4k3/8/8/8/8/6n1/7P/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("h2")))
        assert moves == {"h2h3", "h2h4", "h2g3"}

    def test_black_pawn(self):
        b = Board.from_fen("4k3/4p3/8/8/8/8/8/4K3 b - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e7")))
        assert moves == {"e7e6", "e7e5"}

    def test_black_pawn_capture(self):
        b = Board.from_fen("4k3/4p3/3P1P2/8/8/8/8/4K3 b - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e7")))
        # e7 is on starting rank; e6 push always available, e5 double push too.
        assert moves == {"e7e6", "e7e5", "e7d6", "e7f6"}


class TestPromotion:
    def test_white_promotion_push_yields_four_moves(self):
        # Black king on h8 (off the e-file), so e8 is empty.
        b = Board.from_fen("7k/4P3/8/8/8/8/8/4K3 w - - 0 1")
        moves = from_sq(generate_pseudo_legal_moves(b), sq("e7"))
        promos = [m for m in moves if m.to_sq == sq("e8")]
        assert len(promos) == 4
        assert {m.promotion for m in promos} == set(PROMOTION_PIECES)

    def test_white_promotion_capture(self):
        # Pawn can promote-push to b8 OR promote-capture on a8 OR c8.
        b = Board.from_fen("r1r1k3/1P6/8/8/8/8/8/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("b7")))
        # 4 promos x 3 destinations = 12 moves
        expected = set()
        for dest in ("a8", "b8", "c8"):
            for p in ("q", "r", "b", "n"):
                expected.add(f"b7{dest}{p}")
        assert moves == expected

    def test_black_promotion(self):
        # White king on h1 (off the e-file), so e1 is empty.
        b = Board.from_fen("4k3/8/8/8/8/8/4p3/7K b - - 0 1")
        moves = from_sq(generate_pseudo_legal_moves(b), sq("e2"))
        promos = [m for m in moves if m.to_sq == sq("e1")]
        assert len(promos) == 4
        assert {m.promotion for m in promos} == set(PROMOTION_PIECES)


class TestEnPassant:
    def test_white_can_capture_ep(self):
        # Position after 1.e4 d5 2.e5 f5 -- white pawn on e5 may take f5 ep.
        b = Board.from_fen(
            "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3"
        )
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e5")))
        assert "e5f6" in moves

    def test_black_can_capture_ep(self):
        # Symmetric: black pawn on d4 takes e3 ep.
        b = Board.from_fen(
            "rnbqkbnr/pppp1ppp/8/8/3pP3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        )
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("d4")))
        assert "d4e3" in moves

    def test_no_ep_when_target_field_absent(self):
        # Same pawns, no ep target in FEN -> no ep move.
        b = Board.from_fen(
            "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3"
        )
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e5")))
        assert "e5f6" not in moves


# ---------------------------------------------------------------------------
# knights
# ---------------------------------------------------------------------------


class TestKnight:
    def test_centre(self):
        b = Board.from_fen("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("d4")))
        # 8 L-shapes from d4: b3 b5 c2 c6 e2 e6 f3 f5
        assert moves == {
            "d4b3", "d4b5", "d4c2", "d4c6",
            "d4e2", "d4e6", "d4f3", "d4f5",
        }

    def test_corner(self):
        b = Board.from_fen("4k3/8/8/8/8/8/8/N3K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("a1")))
        assert moves == {"a1b3", "a1c2"}

    def test_blocked_by_friendly(self):
        # Knight on b1 with white pawns / pieces on its targets a3, c3.
        b = Board.from_fen("4k3/8/8/8/8/P1P5/8/1N2K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("b1")))
        assert moves == {"b1d2"}

    def test_captures_enemy(self):
        b = Board.from_fen("4k3/8/8/8/3p4/8/2N5/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("c2")))
        assert "c2d4" in moves


# ---------------------------------------------------------------------------
# bishops
# ---------------------------------------------------------------------------


class TestBishop:
    def test_centre_open_board(self):
        # Bishop on d4, lone kings elsewhere -- 13 squares reachable.
        b = Board.from_fen("4k3/8/8/8/3B4/8/8/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("d4")))
        # NE: e5 f6 g7 h8 ; NW: c5 b6 a7 ; SE: e3 f2 g1 ; SW: c3 b2 a1
        expected = {
            "d4e5", "d4f6", "d4g7", "d4h8",
            "d4c5", "d4b6", "d4a7",
            "d4e3", "d4f2", "d4g1",
            "d4c3", "d4b2", "d4a1",
        }
        assert moves == expected

    def test_blocked_by_friendly(self):
        # Pawn on e5 blocks NE ray immediately -> e5 not reachable.
        b = Board.from_fen("4k3/8/8/4P3/3B4/8/8/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("d4")))
        assert "d4e5" not in moves
        assert "d4f6" not in moves

    def test_captures_then_stops(self):
        # Black pawn on f6 -> bishop reaches e5 and f6 (capture), nothing past.
        b = Board.from_fen("4k3/8/5p2/8/3B4/8/8/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("d4")))
        assert "d4e5" in moves
        assert "d4f6" in moves
        assert "d4g7" not in moves
        assert "d4h8" not in moves


# ---------------------------------------------------------------------------
# rooks
# ---------------------------------------------------------------------------


class TestRook:
    def test_centre_open_board(self):
        # Rook on d4 -- 14 reachable squares (7 file + 7 rank).
        b = Board.from_fen("4k3/8/8/8/3R4/8/8/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("d4")))
        assert len(moves) == 14
        # Spot checks on extremes
        assert "d4d8" in moves
        assert "d4d1" in moves
        assert "d4a4" in moves
        assert "d4h4" in moves

    def test_blocked(self):
        b = Board.from_fen("4k3/8/3P4/8/3R4/8/8/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("d4")))
        assert "d4d5" in moves
        assert "d4d6" not in moves   # friendly pawn on d6 blocks
        assert "d4d7" not in moves

    def test_captures_then_stops(self):
        b = Board.from_fen("4k3/8/3p4/8/3R4/8/8/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("d4")))
        assert "d4d5" in moves
        assert "d4d6" in moves
        assert "d4d7" not in moves


# ---------------------------------------------------------------------------
# queens
# ---------------------------------------------------------------------------


class TestQueen:
    def test_centre_open_board(self):
        # Queen on d4 -- 27 squares (14 rook + 13 bishop).
        b = Board.from_fen("4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("d4")))
        assert len(moves) == 27


# ---------------------------------------------------------------------------
# king (non-castling step moves)
# ---------------------------------------------------------------------------


class TestKingSteps:
    def test_centre(self):
        b = Board.from_fen("8/8/8/8/3K4/8/8/4k3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("d4")))
        assert moves == {
            "d4c3", "d4c4", "d4c5",
            "d4d3",         "d4d5",
            "d4e3", "d4e4", "d4e5",
        }

    def test_blocked_by_friendly(self):
        # White pawns ring king; only diagonals are reachable.
        b = Board.from_fen("8/8/8/8/8/3PPP2/3PKP2/3PPP2 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e2")))
        # All 8 surrounding squares occupied by friendly pawns -> no moves.
        assert moves == set()

    def test_pseudo_legal_into_attacked_square(self):
        # White king on e1, black rook on e8: e1->e2 puts king in check
        # but is pseudo-legal (legality filter in stage 4 will drop it).
        b = Board.from_fen("4r3/8/8/8/8/8/8/4K3 w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e1")))
        assert "e1e2" in moves


# ---------------------------------------------------------------------------
# castling
# ---------------------------------------------------------------------------


class TestCastling:
    def test_white_kingside_available(self):
        b = Board.from_fen("4k3/8/8/8/8/8/8/4K2R w K - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e1")))
        assert "e1g1" in moves
        assert "e1c1" not in moves   # no rook on a1, no Q right

    def test_white_queenside_available(self):
        b = Board.from_fen("4k3/8/8/8/8/8/8/R3K3 w Q - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e1")))
        assert "e1c1" in moves
        assert "e1g1" not in moves

    def test_both_sides(self):
        b = Board.from_fen("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e1")))
        assert "e1g1" in moves
        assert "e1c1" in moves

    def test_blocked_by_piece_between(self):
        # Knight on f1 blocks kingside.
        b = Board.from_fen("4k3/8/8/8/8/8/8/4KN1R w K - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e1")))
        assert "e1g1" not in moves

        # Knight on b1 blocks queenside (b1 must be empty too).
        b = Board.from_fen("4k3/8/8/8/8/8/8/RN2K3 w Q - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e1")))
        assert "e1c1" not in moves

    def test_no_rights_no_castle(self):
        b = Board.from_fen("4k3/8/8/8/8/8/8/R3K2R w - - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e1")))
        assert "e1g1" not in moves
        assert "e1c1" not in moves

    def test_pseudo_legal_castle_through_check_still_allowed(self):
        # Black rook on f8 attacks f1, so e1->g1 castles through check.
        # Pseudo-legal generator MUST still emit this; legality filter
        # in stage 4 will drop it.
        b = Board.from_fen("4k1r1/8/8/8/8/8/8/4K2R w K - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e1")))
        assert "e1g1" in moves

    def test_black_castling(self):
        b = Board.from_fen("r3k2r/8/8/8/8/8/8/4K3 b kq - 0 1")
        moves = uci_set(from_sq(generate_pseudo_legal_moves(b), sq("e8")))
        assert "e8g8" in moves
        assert "e8c8" in moves


# ---------------------------------------------------------------------------
# convenience entry point
# ---------------------------------------------------------------------------


class TestPerSquareEntry:
    def test_empty_square(self):
        b = Board.starting_position()
        assert generate_pseudo_legal_moves_for_square(b, sq("e4")) == []

    def test_wrong_color(self):
        b = Board.starting_position()  # white to move
        # e7 has a black pawn; nothing pseudo-legal returned for it.
        assert generate_pseudo_legal_moves_for_square(b, sq("e7")) == []

    def test_correct_color(self):
        b = Board.starting_position()
        moves = generate_pseudo_legal_moves_for_square(b, sq("e2"))
        assert uci_set(moves) == {"e2e3", "e2e4"}

    def test_out_of_range(self):
        b = Board.starting_position()
        with pytest.raises(ValueError):
            generate_pseudo_legal_moves_for_square(b, 64)


# ---------------------------------------------------------------------------
# Board method exposes the same data
# ---------------------------------------------------------------------------


class TestBoardMethod:
    def test_starting_count(self):
        assert len(Board.starting_position().pseudo_legal_moves()) == 20

    def test_board_method_matches_function(self):
        b = Board.from_fen("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        assert (
            uci_set(b.pseudo_legal_moves())
            == uci_set(generate_pseudo_legal_moves(b))
        )
