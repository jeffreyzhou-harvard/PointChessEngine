"""
Chess piece representation and movement rules.

Implements:
- Piece class (type, color, value)
- Piece value constants
"""

from typing import Dict


# Material values in centipawns
PIECE_VALUES: Dict[str, int] = {
    'pawn': 100,
    'knight': 320,
    'bishop': 330,
    'rook': 500,
    'queen': 900,
    'king': 0  # King has no material value (invaluable)
}


class Piece:
    """
    Chess piece.
    
    Attributes:
        piece_type: str - 'pawn', 'knight', 'bishop', 'rook', 'queen', 'king'
        color: str - 'white' or 'black'
    """
    
    VALID_TYPES = {'pawn', 'knight', 'bishop', 'rook', 'queen', 'king'}
    VALID_COLORS = {'white', 'black'}
    
    def __init__(self, piece_type: str, color: str):
        """
        Initialize piece.
        
        Args:
            piece_type: Piece type ('pawn', 'knight', 'bishop', 'rook', 'queen', 'king')
            color: Piece color ('white' or 'black')
        
        Raises:
            ValueError: If piece_type or color is invalid
        """
        if piece_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid piece type: {piece_type}")
        if color not in self.VALID_COLORS:
            raise ValueError(f"Invalid color: {color}")
        
        self.piece_type = piece_type
        self.color = color
    
    def get_value(self) -> int:
        """
        Get material value in centipawns.
        
        Returns:
            Material value (pawn=100, knight=320, bishop=330, rook=500, queen=900, king=0)
        """
        return PIECE_VALUES[self.piece_type]
    
    def __str__(self) -> str:
        """
        Single character representation.
        
        White pieces: uppercase (P, N, B, R, Q, K)
        Black pieces: lowercase (p, n, b, r, q, k)
        
        Returns:
            Single character string
        """
        char_map = {
            'pawn': 'P',
            'knight': 'N',
            'bishop': 'B',
            'rook': 'R',
            'queen': 'Q',
            'king': 'K'
        }
        char = char_map[self.piece_type]
        return char if self.color == 'white' else char.lower()
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"Piece({self.piece_type}, {self.color})"
    
    def __eq__(self, other) -> bool:
        """Check equality with another piece."""
        if not isinstance(other, Piece):
            return False
        return self.piece_type == other.piece_type and self.color == other.color
    
    def __hash__(self) -> int:
        """Hash for use in sets and dicts."""
        return hash((self.piece_type, self.color))
    
    @staticmethod
    def from_char(char: str) -> 'Piece':
        """
        Create piece from single character.
        
        Args:
            char: Single character (P/p, N/n, B/b, R/r, Q/q, K/k)
        
        Returns:
            Piece instance
        
        Raises:
            ValueError: If character is invalid
        """
        char_to_type = {
            'P': 'pawn', 'p': 'pawn',
            'N': 'knight', 'n': 'knight',
            'B': 'bishop', 'b': 'bishop',
            'R': 'rook', 'r': 'rook',
            'Q': 'queen', 'q': 'queen',
            'K': 'king', 'k': 'king'
        }
        
        if char not in char_to_type:
            raise ValueError(f"Invalid piece character: {char}")
        
        piece_type = char_to_type[char]
        color = 'white' if char.isupper() else 'black'
        
        return Piece(piece_type, color)
