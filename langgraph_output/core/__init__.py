"""
Core chess rules module.

This module implements all chess rules from scratch:
- Board representation and FEN parsing
- Move generation (including special moves)
- Game state management
- Check, checkmate, stalemate detection
- Draw conditions (50-move, repetition, insufficient material)

Public API (FROZEN - see docs/architecture.md):
    - Board: Chess board representation
    - Square: Board square (rank/file)
    - Piece: Chess piece
    - Move: Chess move
    - GameState: Game state and rule enforcement
"""

from .board import Board
from .move import Move, Square
from .pieces import Piece
from .game_state import GameState

__all__ = [
    'Board',
    'Square', 
    'Piece',
    'Move',
    'GameState',
]
