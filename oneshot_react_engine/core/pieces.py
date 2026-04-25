"""Piece, color, and piece-type primitives.

Kept intentionally small and free of board logic so other modules can depend
on it without circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class Color(IntEnum):
    WHITE = 0
    BLACK = 1

    def opposite(self) -> "Color":
        return Color.BLACK if self == Color.WHITE else Color.WHITE


class PieceType(IntEnum):
    PAWN = 1
    KNIGHT = 2
    BISHOP = 3
    ROOK = 4
    QUEEN = 5
    KING = 6


# FEN character mapping is shared in both directions
_PIECE_TO_FEN = {
    (Color.WHITE, PieceType.PAWN): "P",
    (Color.WHITE, PieceType.KNIGHT): "N",
    (Color.WHITE, PieceType.BISHOP): "B",
    (Color.WHITE, PieceType.ROOK): "R",
    (Color.WHITE, PieceType.QUEEN): "Q",
    (Color.WHITE, PieceType.KING): "K",
    (Color.BLACK, PieceType.PAWN): "p",
    (Color.BLACK, PieceType.KNIGHT): "n",
    (Color.BLACK, PieceType.BISHOP): "b",
    (Color.BLACK, PieceType.ROOK): "r",
    (Color.BLACK, PieceType.QUEEN): "q",
    (Color.BLACK, PieceType.KING): "k",
}

FEN_TO_PIECE = {ch: (color, pt) for (color, pt), ch in _PIECE_TO_FEN.items()}

# Unicode display characters (used in textual board rendering)
_PIECE_TO_SYMBOL = {
    (Color.WHITE, PieceType.PAWN): "\u2659",
    (Color.WHITE, PieceType.KNIGHT): "\u2658",
    (Color.WHITE, PieceType.BISHOP): "\u2657",
    (Color.WHITE, PieceType.ROOK): "\u2656",
    (Color.WHITE, PieceType.QUEEN): "\u2655",
    (Color.WHITE, PieceType.KING): "\u2654",
    (Color.BLACK, PieceType.PAWN): "\u265F",
    (Color.BLACK, PieceType.KNIGHT): "\u265E",
    (Color.BLACK, PieceType.BISHOP): "\u265D",
    (Color.BLACK, PieceType.ROOK): "\u265C",
    (Color.BLACK, PieceType.QUEEN): "\u265B",
    (Color.BLACK, PieceType.KING): "\u265A",
}


@dataclass(frozen=True)
class Piece:
    color: Color
    piece_type: PieceType

    def fen_char(self) -> str:
        return _PIECE_TO_FEN[(self.color, self.piece_type)]

    def symbol(self) -> str:
        return _PIECE_TO_SYMBOL[(self.color, self.piece_type)]

    def __repr__(self) -> str:
        return f"Piece({self.fen_char()})"
