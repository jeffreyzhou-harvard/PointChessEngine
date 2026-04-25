"""Core types for the chess engine."""

from enum import IntEnum
from typing import NamedTuple, Optional


class Color(IntEnum):
    WHITE = 0
    BLACK = 1

    def opposite(self) -> 'Color':
        return Color(1 - self)


class PieceType(IntEnum):
    PAWN = 1
    KNIGHT = 2
    BISHOP = 3
    ROOK = 4
    QUEEN = 5
    KING = 6


class Piece(NamedTuple):
    color: Color
    piece_type: PieceType

    def symbol(self) -> str:
        symbols = {
            PieceType.PAWN: 'P', PieceType.KNIGHT: 'N', PieceType.BISHOP: 'B',
            PieceType.ROOK: 'R', PieceType.QUEEN: 'Q', PieceType.KING: 'K'
        }
        s = symbols[self.piece_type]
        return s if self.color == Color.WHITE else s.lower()

    def fen_char(self) -> str:
        return self.symbol()


# Square is an (row, col) tuple where row 0 = rank 8 (top), row 7 = rank 1 (bottom)
# col 0 = file a, col 7 = file h
class Square(NamedTuple):
    row: int
    col: int

    def is_valid(self) -> bool:
        return 0 <= self.row < 8 and 0 <= self.col < 8

    def algebraic(self) -> str:
        return chr(ord('a') + self.col) + str(8 - self.row)

    @staticmethod
    def from_algebraic(s: str) -> 'Square':
        return Square(8 - int(s[1]), ord(s[0]) - ord('a'))


class Move(NamedTuple):
    from_sq: Square
    to_sq: Square
    promotion: Optional[PieceType] = None

    def uci(self) -> str:
        s = self.from_sq.algebraic() + self.to_sq.algebraic()
        if self.promotion:
            promo_chars = {
                PieceType.QUEEN: 'q', PieceType.ROOK: 'r',
                PieceType.BISHOP: 'b', PieceType.KNIGHT: 'n'
            }
            s += promo_chars[self.promotion]
        return s

    @staticmethod
    def from_uci(s: str) -> 'Move':
        from_sq = Square.from_algebraic(s[0:2])
        to_sq = Square.from_algebraic(s[2:4])
        promotion = None
        if len(s) == 5:
            promo_map = {'q': PieceType.QUEEN, 'r': PieceType.ROOK,
                         'b': PieceType.BISHOP, 'n': PieceType.KNIGHT}
            promotion = promo_map[s[4].lower()]
        return Move(from_sq, to_sq, promotion)
