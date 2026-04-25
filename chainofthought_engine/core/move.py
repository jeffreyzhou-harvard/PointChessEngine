"""Move value type.

A ``Move`` is *only* a description of a move (from-square, to-square,
optional promotion). It carries no board context. Whether the move is
legal, what it captures, and whether it is castling/en-passant is all
determined by the ``Board`` it is applied to. This keeps moves cheap to
construct, hash, and pass through search.

The string form is **pure coordinate** (UCI-compatible): ``e2e4``,
``e7e8q``. SAN parsing/printing belongs in a later PGN stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .types import (
    PieceType,
    Square,
    square_from_algebraic,
    square_to_algebraic,
)


@dataclass(frozen=True, slots=True)
class Move:
    from_sq: Square
    to_sq: Square
    promotion: Optional[PieceType] = None

    def uci(self) -> str:
        s = square_to_algebraic(self.from_sq) + square_to_algebraic(self.to_sq)
        if self.promotion is not None:
            s += {
                PieceType.KNIGHT: "n",
                PieceType.BISHOP: "b",
                PieceType.ROOK: "r",
                PieceType.QUEEN: "q",
            }[self.promotion]
        return s

    @classmethod
    def from_uci(cls, text: str) -> "Move":
        """Parse a UCI coordinate string into a :class:`Move`.

        Accepts ``"e2e4"`` and ``"e7e8q"`` (and the other three
        promotion letters). The UCI null-move sentinel ``"0000"``
        is rejected here -- it is not a ``Move`` value, and only
        the UCI layer knows what to do with it.
        """
        if not isinstance(text, str) or len(text) not in (4, 5):
            raise ValueError(f"not a UCI move: {text!r}")
        if text.startswith("0000"):
            raise ValueError(
                "'0000' is the UCI null-move sentinel; it is not a Move "
                "value. Handle it at the protocol layer instead."
            )
        from_sq = square_from_algebraic(text[0:2])
        to_sq = square_from_algebraic(text[2:4])
        promo: Optional[PieceType] = None
        if len(text) == 5:
            promo = {
                "n": PieceType.KNIGHT,
                "b": PieceType.BISHOP,
                "r": PieceType.ROOK,
                "q": PieceType.QUEEN,
            }.get(text[4].lower())
            if promo is None:
                raise ValueError(f"not a UCI move (bad promotion): {text!r}")
        return cls(from_sq=from_sq, to_sq=to_sq, promotion=promo)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.uci()
