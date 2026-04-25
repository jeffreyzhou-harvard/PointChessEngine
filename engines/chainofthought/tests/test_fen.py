"""Stage 2: FEN parsing and serialization.

The contract:

* :func:`parse_fen` returns a :class:`Board` with all six FEN fields
  populated. Round-trip with :func:`board_to_fen` must be exact for
  any well-formed FEN.
* Malformed FEN (wrong field count, bad characters, ranks that do not
  sum to 8, illegal en-passant target rank, non-numeric counters,
  out-of-range counters) raises ``ValueError``.

Position legality (e.g. both kings present, side-not-to-move not in
check) is intentionally **not** validated here - that requires move
generation and lives in a later stage.
"""

from __future__ import annotations

import pytest

from engines.chainofthought.core import (
    Board,
    CastlingRights,
    Color,
    Piece,
    PieceType,
)
from engines.chainofthought.core.fen import board_to_fen, parse_fen
from engines.chainofthought.core.types import square_from_algebraic


# ---------------------------------------------------------------------------
# initial position
# ---------------------------------------------------------------------------


class TestInitialPosition:
    def test_parse(self):
        b = parse_fen(Board.STARTING_FEN)

        assert b.turn is Color.WHITE
        assert b.castling_rights == CastlingRights.all()
        assert b.ep_square is None
        assert b.halfmove_clock == 0
        assert b.fullmove_number == 1

        # 32 occupied squares
        occupied = [b.piece_at(s) for s in range(64) if b.piece_at(s) is not None]
        assert len(occupied) == 32

        # Specific spot checks
        assert b.piece_at(square_from_algebraic("e1")) == Piece(Color.WHITE, PieceType.KING)
        assert b.piece_at(square_from_algebraic("d8")) == Piece(Color.BLACK, PieceType.QUEEN)
        assert b.piece_at(square_from_algebraic("a2")) == Piece(Color.WHITE, PieceType.PAWN)
        assert b.piece_at(square_from_algebraic("h7")) == Piece(Color.BLACK, PieceType.PAWN)

    def test_serialize(self):
        assert board_to_fen(Board.starting_position()) == Board.STARTING_FEN

    def test_board_method_round_trip(self):
        # Board.fen / Board.from_fen delegate to this module
        assert Board.from_fen(Board.STARTING_FEN).fen() == Board.STARTING_FEN


# ---------------------------------------------------------------------------
# round-trip on a curated set of real positions
# ---------------------------------------------------------------------------


ROUNDTRIP_FENS = [
    # Starting position
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",

    # After 1. e4 -- black to move, ep square = e3
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",

    # After 1. e4 c5 -- white to move, ep square = c6
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2",

    # Kiwipete (Stockfish's classic move-gen test position)
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",

    # No castling rights, mid-game with counters advanced
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 41",

    # Promotion-ready / late game / no castling
    "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",

    # Endgame: K + R vs K, half-move clock != 0
    "8/8/8/8/8/4k3/8/R3K3 w Q - 17 60",

    # Mate-in-1 puzzle
    "6k1/5ppp/8/8/8/8/8/4K2Q w - - 0 1",
]


@pytest.mark.parametrize("fen", ROUNDTRIP_FENS)
def test_fen_roundtrip(fen):
    b = parse_fen(fen)
    assert board_to_fen(b) == fen


# ---------------------------------------------------------------------------
# field-by-field
# ---------------------------------------------------------------------------


class TestSideToMove:
    def test_white(self):
        fen = "8/8/8/8/8/8/8/4K3 w - - 0 1"
        assert parse_fen(fen).turn is Color.WHITE

    def test_black(self):
        fen = "8/8/8/8/8/8/8/4K3 b - - 0 1"
        assert parse_fen(fen).turn is Color.BLACK

    @pytest.mark.parametrize("bad", ["x", "W", "B", "white", ""])
    def test_invalid_side(self, bad):
        fen = f"8/8/8/8/8/8/8/4K3 {bad} - - 0 1"
        with pytest.raises(ValueError):
            parse_fen(fen)


class TestCastlingField:
    @pytest.mark.parametrize(
        "field,expected",
        [
            ("-", CastlingRights.none()),
            ("KQkq", CastlingRights.all()),
            ("Kk", CastlingRights(True, False, True, False)),
            ("Qq", CastlingRights(False, True, False, True)),
            ("Q", CastlingRights(False, True, False, False)),
        ],
    )
    def test_each_subset(self, field, expected):
        fen = f"4k3/8/8/8/8/8/8/R3K2R w {field} - 0 1"
        b = parse_fen(fen)
        assert b.castling_rights == expected
        assert board_to_fen(b).split()[2] == field

    @pytest.mark.parametrize("bad", ["KQKQ", "KQz", "?"])
    def test_invalid_castling(self, bad):
        fen = f"4k3/8/8/8/8/8/8/4K3 w {bad} - 0 1"
        with pytest.raises(ValueError):
            parse_fen(fen)


class TestEnPassant:
    def test_none(self):
        b = parse_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        assert b.ep_square is None

    @pytest.mark.parametrize("name", ["a3", "e3", "h3", "a6", "e6", "h6"])
    def test_valid_squares(self, name):
        fen = f"4k3/8/8/8/8/8/8/4K3 w - {name} 0 1"
        b = parse_fen(fen)
        assert b.ep_square == square_from_algebraic(name)

    @pytest.mark.parametrize("bad_rank", ["e1", "e2", "e4", "e5", "e7", "e8"])
    def test_wrong_rank_rejected(self, bad_rank):
        # ep target must be on rank 3 or 6.
        fen = f"4k3/8/8/8/8/8/8/4K3 w - {bad_rank} 0 1"
        with pytest.raises(ValueError):
            parse_fen(fen)

    @pytest.mark.parametrize("bad", ["zz", "i3", "e9", "e", "ee"])
    def test_malformed_rejected(self, bad):
        fen = f"4k3/8/8/8/8/8/8/4K3 w - {bad} 0 1"
        with pytest.raises(ValueError):
            parse_fen(fen)


class TestMoveCounters:
    @pytest.mark.parametrize("hm,fm", [(0, 1), (5, 12), (49, 100), (99, 999)])
    def test_valid_counters(self, hm, fm):
        fen = f"4k3/8/8/8/8/8/8/4K3 w - - {hm} {fm}"
        b = parse_fen(fen)
        assert b.halfmove_clock == hm
        assert b.fullmove_number == fm
        assert board_to_fen(b) == fen

    def test_negative_halfmove(self):
        with pytest.raises(ValueError):
            parse_fen("4k3/8/8/8/8/8/8/4K3 w - - -1 1")

    def test_zero_fullmove(self):
        with pytest.raises(ValueError):
            parse_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 0")

    @pytest.mark.parametrize("bad", ["x", "1.5", "", "0x10"])
    def test_non_numeric(self, bad):
        with pytest.raises(ValueError):
            parse_fen(f"4k3/8/8/8/8/8/8/4K3 w - - {bad} 1")
        with pytest.raises(ValueError):
            parse_fen(f"4k3/8/8/8/8/8/8/4K3 w - - 0 {bad}")


# ---------------------------------------------------------------------------
# placement validation
# ---------------------------------------------------------------------------


class TestPlacementValidation:
    @pytest.mark.parametrize(
        "bad_fen",
        [
            # 7 ranks
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP w KQkq - 0 1",
            # 9 ranks
            "rnbqkbnr/pppppppp/8/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            # rank with 9 squares (8 + 1)
            "rnbqkbnr/pppppppp/8/8/8/9/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            # invalid piece symbol 'x'
            "rnbqkbnr/pppppppx/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            # rank that doesn't sum to 8
            "rnbqkbnr/ppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            # zero in rank
            "rnbqkbnr/pppppppp/0/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            # empty rank
            "rnbqkbnr/pppppppp//8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        ],
    )
    def test_malformed_placement(self, bad_fen):
        with pytest.raises(ValueError):
            parse_fen(bad_fen)

    @pytest.mark.parametrize("bad_field_count", [
        "",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1 extra",
    ])
    def test_field_count(self, bad_field_count):
        with pytest.raises(ValueError):
            parse_fen(bad_field_count)

    def test_non_string_input(self):
        with pytest.raises(ValueError):
            parse_fen(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# example FEN round-trip cases (advertised in this stage's writeup)
# ---------------------------------------------------------------------------


class TestExampleRoundTrips:
    """Showcased examples - intentionally readable test names so the
    summary at the end of this stage can point at them."""

    def test_after_1_e4(self):
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        b = parse_fen(fen)
        assert b.turn is Color.BLACK
        assert b.ep_square == square_from_algebraic("e3")
        assert b.piece_at(square_from_algebraic("e4")) == Piece(Color.WHITE, PieceType.PAWN)
        assert b.piece_at(square_from_algebraic("e2")) is None
        assert board_to_fen(b) == fen

    def test_kiwipete(self):
        fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        b = parse_fen(fen)
        assert b.castling_rights == CastlingRights.all()
        assert b.turn is Color.WHITE
        assert board_to_fen(b) == fen

    def test_endgame_kr_vs_k(self):
        fen = "8/8/8/8/8/4k3/8/R3K3 w Q - 17 60"
        b = parse_fen(fen)
        assert b.castling_rights == CastlingRights(False, True, False, False)
        assert b.halfmove_clock == 17
        assert b.fullmove_number == 60
        assert board_to_fen(b) == fen
