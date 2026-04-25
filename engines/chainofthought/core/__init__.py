"""Core chess rules and data structures.

This package owns the *what* of chess: pieces, squares, moves, board
state, FEN. It does not know anything about search, UCI, or any UI.
Everything else in the project depends on this package; nothing in this
package imports from `search`, `uci`, or `ui`.
"""

from .types import Color, PieceType, Piece, Square
from .move import Move
from .board import Board, CastlingRights
from .game import GameState

__all__ = [
    "Color",
    "PieceType",
    "Piece",
    "Square",
    "Move",
    "Board",
    "CastlingRights",
    "GameState",
]
