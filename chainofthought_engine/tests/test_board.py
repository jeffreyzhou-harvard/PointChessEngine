"""Stage 2: board state and CastlingRights.

FEN parsing/serializing has its own file (test_fen.py); this file
exercises the Board / CastlingRights value types directly.
"""

from __future__ import annotations

import pytest

from chainofthought_engine.core import (
    Board,
    CastlingRights,
    Color,
    Piece,
    PieceType,
)
from chainofthought_engine.core.types import square_from_algebraic


# ---------------------------------------------------------------------------
# CastlingRights
# ---------------------------------------------------------------------------


class TestCastlingRights:
    def test_none(self):
        r = CastlingRights.none()
        assert not r.white_kingside
        assert not r.white_queenside
        assert not r.black_kingside
        assert not r.black_queenside
        assert r.to_fen() == "-"

    def test_all(self):
        r = CastlingRights.all()
        assert r.to_fen() == "KQkq"

    @pytest.mark.parametrize(
        "fen,expected",
        [
            ("-", CastlingRights.none()),
            ("KQkq", CastlingRights.all()),
            ("KQ", CastlingRights(True, True, False, False)),
            ("kq", CastlingRights(False, False, True, True)),
            ("Kq", CastlingRights(True, False, False, True)),
            ("Q", CastlingRights(False, True, False, False)),
            ("k", CastlingRights(False, False, True, False)),
        ],
    )
    def test_from_fen_roundtrip(self, fen, expected):
        parsed = CastlingRights.from_fen(fen)
        assert parsed == expected
        assert parsed.to_fen() == fen

    def test_value_semantics(self):
        a = CastlingRights(True, False, True, False)
        b = CastlingRights(True, False, True, False)
        assert a == b
        assert hash(a) == hash(b)

    @pytest.mark.parametrize("bad", ["", "x", "Kx", "KK", "KQq?", "K Q"])
    def test_invalid_fen(self, bad):
        with pytest.raises(ValueError):
            CastlingRights.from_fen(bad)


# ---------------------------------------------------------------------------
# Board construction & inspection
# ---------------------------------------------------------------------------


class TestBoardConstruction:
    def test_default_is_empty(self):
        b = Board()
        for sq in range(64):
            assert b.piece_at(sq) is None
        assert b.turn is Color.WHITE
        assert b.castling_rights == CastlingRights.none()
        assert b.ep_square is None
        assert b.halfmove_clock == 0
        assert b.fullmove_number == 1

    def test_empty_alias(self):
        assert Board.empty() == Board()

    def test_explicit_construction(self):
        squares = [None] * 64
        squares[square_from_algebraic("e1")] = Piece(Color.WHITE, PieceType.KING)
        squares[square_from_algebraic("e8")] = Piece(Color.BLACK, PieceType.KING)
        b = Board(
            squares=squares,
            turn=Color.BLACK,
            castling=CastlingRights(True, False, False, True),
            ep_square=square_from_algebraic("e3"),
            halfmove_clock=5,
            fullmove_number=12,
        )
        assert b.piece_at(square_from_algebraic("e1")) == Piece(Color.WHITE, PieceType.KING)
        assert b.turn is Color.BLACK
        assert b.castling_rights == CastlingRights(True, False, False, True)
        assert b.ep_square == square_from_algebraic("e3")
        assert b.halfmove_clock == 5
        assert b.fullmove_number == 12

    def test_squares_length_validated(self):
        with pytest.raises(ValueError):
            Board(squares=[None] * 63)

    @pytest.mark.parametrize("sq", [-1, 64, 100])
    def test_ep_range_validated(self, sq):
        with pytest.raises(ValueError):
            Board(ep_square=sq)

    def test_halfmove_validated(self):
        with pytest.raises(ValueError):
            Board(halfmove_clock=-1)

    def test_fullmove_validated(self):
        with pytest.raises(ValueError):
            Board(fullmove_number=0)


class TestStartingPosition:
    def test_piece_layout(self):
        b = Board.starting_position()
        # White back rank
        layout = ["R", "N", "B", "Q", "K", "B", "N", "R"]
        for file, sym in enumerate(layout):
            assert b.piece_at(file).symbol == sym
        # White pawns on rank 2
        for file in range(8):
            assert b.piece_at(8 + file) == Piece(Color.WHITE, PieceType.PAWN)
        # Empty middle
        for sq in range(16, 48):
            assert b.piece_at(sq) is None
        # Black pawns on rank 7
        for file in range(8):
            assert b.piece_at(48 + file) == Piece(Color.BLACK, PieceType.PAWN)
        # Black back rank
        for file, sym in enumerate(layout):
            piece = b.piece_at(56 + file)
            assert piece is not None
            assert piece.symbol == sym.lower()

    def test_state_fields(self):
        b = Board.starting_position()
        assert b.turn is Color.WHITE
        assert b.castling_rights == CastlingRights.all()
        assert b.ep_square is None
        assert b.halfmove_clock == 0
        assert b.fullmove_number == 1


class TestPieceAtBoundary:
    @pytest.mark.parametrize("sq", [-1, 64, 999])
    def test_out_of_range_raises(self, sq):
        with pytest.raises(ValueError):
            Board().piece_at(sq)


class TestSetPieceAt:
    def test_round_trip(self):
        b = Board.empty()
        sq = square_from_algebraic("d4")
        piece = Piece(Color.WHITE, PieceType.QUEEN)
        b.set_piece_at(sq, piece)
        assert b.piece_at(sq) == piece
        b.set_piece_at(sq, None)
        assert b.piece_at(sq) is None

    @pytest.mark.parametrize("sq", [-1, 64])
    def test_out_of_range_raises(self, sq):
        with pytest.raises(ValueError):
            Board().set_piece_at(sq, None)


# ---------------------------------------------------------------------------
# copy / equality / hash
# ---------------------------------------------------------------------------


class TestCopyAndEquality:
    def test_copy_is_independent(self):
        a = Board.starting_position()
        b = a.copy()
        assert a == b
        b.set_piece_at(0, None)  # mutate copy
        assert a != b
        # Original is intact
        assert a.piece_at(0) == Piece(Color.WHITE, PieceType.ROOK)

    def test_value_equality(self):
        a = Board.starting_position()
        b = Board.starting_position()
        assert a == b
        assert hash(a) == hash(b)

    def test_inequality_on_any_field(self):
        base = Board.starting_position()

        # different square
        diff_sq = base.copy()
        diff_sq.set_piece_at(0, None)
        assert base != diff_sq

        # different turn
        diff_turn = Board(
            squares=[base.piece_at(s) for s in range(64)],
            turn=Color.BLACK,
            castling=base.castling_rights,
        )
        assert base != diff_turn

        # different castling
        diff_castling = Board(
            squares=[base.piece_at(s) for s in range(64)],
            castling=CastlingRights(True, False, True, False),
        )
        assert base != diff_castling

        # different ep
        diff_ep = Board(
            squares=[base.piece_at(s) for s in range(64)],
            castling=base.castling_rights,
            ep_square=square_from_algebraic("e3"),
        )
        assert base != diff_ep

        # different counters
        diff_hm = Board(
            squares=[base.piece_at(s) for s in range(64)],
            castling=base.castling_rights,
            halfmove_clock=1,
        )
        assert base != diff_hm
        diff_fm = Board(
            squares=[base.piece_at(s) for s in range(64)],
            castling=base.castling_rights,
            fullmove_number=2,
        )
        assert base != diff_fm

    def test_equality_with_non_board(self):
        assert (Board() == "not a board") is False
