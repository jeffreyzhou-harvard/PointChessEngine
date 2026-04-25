"""Primitive chess types.

These are intentionally small and dependency-free so that every other
module can import them without risk of cycles. They are *defined* in
this stage; the algorithms that consume them arrive in later stages.

Square encoding
---------------
A square is an ``int`` in ``[0, 64)``. ``0`` is a1, ``7`` is h1, ``56``
is a8, ``63`` is h8. ``file = sq & 7``, ``rank = sq >> 3``. This is the
same convention used by most engines and matches algebraic notation in
a single bit-shift, which keeps move generation cheap later.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Final


class Color(IntEnum):
    WHITE = 0
    BLACK = 1

    def opponent(self) -> "Color":
        return Color.BLACK if self is Color.WHITE else Color.WHITE


class PieceType(IntEnum):
    PAWN = 1
    KNIGHT = 2
    BISHOP = 3
    ROOK = 4
    QUEEN = 5
    KING = 6


@dataclass(frozen=True, slots=True)
class Piece:
    """A typed piece on a square.

    ``Piece`` is intentionally a value type - two pieces with the same
    color and type are equal and hashable.
    """

    color: Color
    type: PieceType

    @classmethod
    def from_symbol(cls, symbol: str) -> "Piece":
        """Parse a FEN-style piece symbol (``'P'``, ``'n'``, ...).

        Uppercase = white, lowercase = black.
        """
        if len(symbol) != 1 or symbol not in _SYMBOL_TO_PIECE_TYPE:
            raise ValueError(f"not a piece symbol: {symbol!r}")
        color = Color.WHITE if symbol.isupper() else Color.BLACK
        return cls(color=color, type=_SYMBOL_TO_PIECE_TYPE[symbol])

    @property
    def symbol(self) -> str:
        s = _PIECE_TYPE_TO_SYMBOL[self.type]
        return s.upper() if self.color is Color.WHITE else s.lower()


_PIECE_TYPE_TO_SYMBOL: Final[dict[PieceType, str]] = {
    PieceType.PAWN: "p",
    PieceType.KNIGHT: "n",
    PieceType.BISHOP: "b",
    PieceType.ROOK: "r",
    PieceType.QUEEN: "q",
    PieceType.KING: "k",
}

_SYMBOL_TO_PIECE_TYPE: Final[dict[str, PieceType]] = {
    sym: pt for pt, low in _PIECE_TYPE_TO_SYMBOL.items() for sym in (low, low.upper())
}


# A square is just an int 0..63. We expose the alias and a few helpers
# rather than a class, because allocating a tiny object per square would
# be ruinously slow once move generation starts running.
Square = int

A1: Final[Square] = 0
H1: Final[Square] = 7
A8: Final[Square] = 56
H8: Final[Square] = 63


def square(file: int, rank: int) -> Square:
    """Build a square from 0-indexed ``file`` (a=0..h=7) and ``rank`` (1=0..8=7)."""
    if not (0 <= file < 8 and 0 <= rank < 8):
        raise ValueError(f"file/rank out of range: file={file}, rank={rank}")
    return rank * 8 + file


def square_file(sq: Square) -> int:
    return sq & 7


def square_rank(sq: Square) -> int:
    return sq >> 3


def square_from_algebraic(name: str) -> Square:
    """Parse ``'e4'`` -> ``28``."""
    if len(name) != 2:
        raise ValueError(f"not a square name: {name!r}")
    file_ch, rank_ch = name[0], name[1]
    if not ("a" <= file_ch <= "h" and "1" <= rank_ch <= "8"):
        raise ValueError(f"not a square name: {name!r}")
    return square(ord(file_ch) - ord("a"), ord(rank_ch) - ord("1"))


def square_to_algebraic(sq: Square) -> str:
    if not (0 <= sq < 64):
        raise ValueError(f"square out of range: {sq}")
    return f"{chr(ord('a') + square_file(sq))}{square_rank(sq) + 1}"
