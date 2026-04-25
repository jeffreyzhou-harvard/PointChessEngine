"""Square coordinates.

We index rows from the top of the visual board (row 0 = rank 8) so that
``squares[row][col]`` matches the FEN layout. ``Square.algebraic()`` produces
standard chess notation (``e4``, ``a1``, ...).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Square:
    row: int  # 0..7, 0 is rank 8 (top)
    col: int  # 0..7, 0 is file a (left)

    def __iter__(self):
        yield self.row
        yield self.col

    def algebraic(self) -> str:
        return f"{chr(ord('a') + self.col)}{8 - self.row}"

    @staticmethod
    def from_algebraic(s: str) -> "Square":
        if len(s) != 2:
            raise ValueError(f"invalid algebraic square: {s!r}")
        file_ch, rank_ch = s[0].lower(), s[1]
        col = ord(file_ch) - ord("a")
        row = 8 - int(rank_ch)
        if not (0 <= row < 8 and 0 <= col < 8):
            raise ValueError(f"square out of range: {s!r}")
        return Square(row, col)

    def in_bounds(self) -> bool:
        return 0 <= self.row < 8 and 0 <= self.col < 8

    def __repr__(self) -> str:
        return self.algebraic()
