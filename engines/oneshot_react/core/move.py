"""Move representation and UCI string parsing.

A ``Move`` is a triplet ``(from_sq, to_sq, promotion)``.  Castling is encoded as
a king move of two files; en passant is encoded as the diagonal capture of an
empty square.  The board executor disambiguates by piece type at execution time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .pieces import PieceType
from .square import Square


_PROMO_LETTER = {
    PieceType.QUEEN: "q",
    PieceType.ROOK: "r",
    PieceType.BISHOP: "b",
    PieceType.KNIGHT: "n",
}
_LETTER_PROMO = {v: k for k, v in _PROMO_LETTER.items()}


@dataclass(frozen=True)
class Move:
    from_sq: Square
    to_sq: Square
    promotion: Optional[PieceType] = None

    def uci(self) -> str:
        s = self.from_sq.algebraic() + self.to_sq.algebraic()
        if self.promotion is not None:
            s += _PROMO_LETTER[self.promotion]
        return s

    @staticmethod
    def from_uci(s: str) -> "Move":
        s = s.strip().lower()
        if len(s) not in (4, 5):
            raise ValueError(f"invalid UCI move: {s!r}")
        fr = Square.from_algebraic(s[0:2])
        to = Square.from_algebraic(s[2:4])
        promo = _LETTER_PROMO[s[4]] if len(s) == 5 else None
        return Move(fr, to, promo)

    def __repr__(self) -> str:
        return self.uci()
