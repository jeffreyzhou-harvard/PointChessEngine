"""
Move and Square representation.

Implements:
- Square class (rank/file, algebraic notation conversion)
- Move class (from/to squares, special move flags, UCI/algebraic notation)
"""

from typing import Optional
from dataclasses import dataclass


class Square:
    """
    Chess board square (rank/file pair).
    
    Attributes:
        rank: int (0-7, where 0 is rank 1, 7 is rank 8)
        file: int (0-7, where 0 is 'a', 7 is 'h')
    """
    
    def __init__(self, rank: int, file: int):
        """
        Initialize square from rank and file.
        
        Args:
            rank: 0-7 (0=rank 1, 7=rank 8)
            file: 0-7 (0=file a, 7=file h)
        """
        if not (0 <= rank <= 7):
            raise ValueError(f"Invalid rank: {rank} (must be 0-7)")
        if not (0 <= file <= 7):
            raise ValueError(f"Invalid file: {file} (must be 0-7)")
        self.rank = rank
        self.file = file
    
    @classmethod
    def from_algebraic(cls, notation: str) -> 'Square':
        """
        Create square from algebraic notation (e.g., 'e4').
        
        Args:
            notation: Algebraic notation string (e.g., 'e4', 'a1', 'h8')
        
        Returns:
            Square instance
        
        Raises:
            ValueError: If notation is invalid
        """
        if len(notation) != 2:
            raise ValueError(f"Invalid algebraic notation: {notation}")
        
        file_char = notation[0].lower()
        rank_char = notation[1]
        
        if file_char not in 'abcdefgh':
            raise ValueError(f"Invalid file: {file_char}")
        if rank_char not in '12345678':
            raise ValueError(f"Invalid rank: {rank_char}")
        
        file = ord(file_char) - ord('a')  # 0-7
        rank = int(rank_char) - 1  # 0-7
        
        return cls(rank, file)
    
    def to_algebraic(self) -> str:
        """
        Convert to algebraic notation (e.g., 'e4').
        
        Returns:
            Algebraic notation string
        """
        file_char = chr(ord('a') + self.file)
        rank_char = str(self.rank + 1)
        return file_char + rank_char
    
    def __eq__(self, other) -> bool:
        """Check equality with another square."""
        if not isinstance(other, Square):
            return False
        return self.rank == other.rank and self.file == other.file
    
    def __hash__(self) -> int:
        """Hash for use in sets and dicts."""
        return hash((self.rank, self.file))
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"Square({self.to_algebraic()})"
    
    def __str__(self) -> str:
        """Human-readable string."""
        return self.to_algebraic()


class Move:
    """
    Chess move with all necessary information.
    
    Attributes:
        from_square: Square - origin square
        to_square: Square - destination square
        promotion: Optional[str] - piece type if pawn promotion ('queen', 'rook', 'bishop', 'knight')
        is_castling: bool - True if castling move
        is_en_passant: bool - True if en passant capture
        captured_piece: Optional[Piece] - piece captured (for unmake_move)
        previous_castling_rights: dict - castling rights before move (for unmake_move)
        previous_en_passant: Optional[Square] - en passant target before move (for unmake_move)
        previous_halfmove_clock: int - halfmove clock before move (for unmake_move)
    """
    
    def __init__(self, from_square: Square, to_square: Square, 
                 promotion: Optional[str] = None):
        """
        Initialize move.
        
        Args:
            from_square: Origin square
            to_square: Destination square
            promotion: Promotion piece type ('queen', 'rook', 'bishop', 'knight')
        """
        self.from_square = from_square
        self.to_square = to_square
        self.promotion = promotion
        
        # Special move flags (set by board when move is made)
        self.is_castling = False
        self.is_en_passant = False
        
        # State for unmake_move (set by board when move is made)
        self.captured_piece = None
        self.previous_castling_rights = None
        self.previous_en_passant = None
        self.previous_halfmove_clock = 0
    
    def to_uci(self) -> str:
        """
        Convert to UCI notation (e.g., 'e2e4', 'e7e8q').
        
        Returns:
            UCI notation string
        """
        uci = self.from_square.to_algebraic() + self.to_square.to_algebraic()
        if self.promotion:
            # UCI uses single letter for promotion
            promotion_map = {
                'queen': 'q',
                'rook': 'r',
                'bishop': 'b',
                'knight': 'n'
            }
            uci += promotion_map[self.promotion]
        return uci
    
    @classmethod
    def from_uci(cls, uci_str: str) -> 'Move':
        """
        Parse UCI notation (e.g., 'e2e4', 'e7e8q').
        
        Args:
            uci_str: UCI notation string
        
        Returns:
            Move instance
        
        Raises:
            ValueError: If UCI string is invalid
        """
        if len(uci_str) < 4 or len(uci_str) > 5:
            raise ValueError(f"Invalid UCI notation: {uci_str}")
        
        from_square = Square.from_algebraic(uci_str[0:2])
        to_square = Square.from_algebraic(uci_str[2:4])
        
        promotion = None
        if len(uci_str) == 5:
            promotion_char = uci_str[4].lower()
            promotion_map = {
                'q': 'queen',
                'r': 'rook',
                'b': 'bishop',
                'n': 'knight'
            }
            if promotion_char not in promotion_map:
                raise ValueError(f"Invalid promotion piece: {promotion_char}")
            promotion = promotion_map[promotion_char]
        
        return cls(from_square, to_square, promotion)
    
    def to_algebraic(self, board: 'Board') -> str:
        """
        Convert to standard algebraic notation (e.g., 'Nf3', 'O-O', 'exd5').
        
        This is a simplified version. Full SAN requires checking for ambiguity
        and whether the move gives check.
        
        Args:
            board: Board instance (needed to determine piece types and ambiguity)
        
        Returns:
            Algebraic notation string
        """
        # Import here to avoid circular dependency
        from .board import Board
        
        # Castling
        if self.is_castling:
            if self.to_square.file > self.from_square.file:
                return 'O-O'  # Kingside
            else:
                return 'O-O-O'  # Queenside
        
        piece = board.get_piece(self.from_square)
        if piece is None:
            return self.to_uci()  # Fallback
        
        notation = ''
        
        # Piece prefix (except for pawns)
        if piece.piece_type != 'pawn':
            notation += piece.piece_type[0].upper()
        
        # Capture notation
        is_capture = board.get_piece(self.to_square) is not None or self.is_en_passant
        if is_capture:
            if piece.piece_type == 'pawn':
                # Pawn captures include file
                notation += self.from_square.to_algebraic()[0]
            notation += 'x'
        
        # Destination square
        notation += self.to_square.to_algebraic()
        
        # Promotion
        if self.promotion:
            notation += '=' + self.promotion[0].upper()
        
        return notation
    
    def __eq__(self, other) -> bool:
        """Check equality with another move."""
        if not isinstance(other, Move):
            return False
        return (self.from_square == other.from_square and
                self.to_square == other.to_square and
                self.promotion == other.promotion)
    
    def __hash__(self) -> int:
        """Hash for use in sets and dicts."""
        return hash((self.from_square, self.to_square, self.promotion))
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"Move({self.to_uci()})"
    
    def __str__(self) -> str:
        """Human-readable string."""
        return self.to_uci()
