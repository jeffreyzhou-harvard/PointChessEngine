"""
Board representation and FEN parsing.

Implements:
- Board class with 8x8 representation
- FEN string parsing and generation
- Piece placement and retrieval
- Move application (make_move/unmake_move)
- Board copying for search
"""

from typing import Optional, List, Dict
import copy
from .pieces import Piece
from .move import Square, Move


class Board:
    """
    8x8 chess board representation.
    
    Attributes:
        squares: 8x8 array where squares[rank][file] contains Piece or None
        active_color: 'white' or 'black'
        castling_rights: dict with keys 'K', 'Q', 'k', 'q' (bool values)
        en_passant_target: Optional[Square] - target square for en passant
        halfmove_clock: int - moves since last pawn move or capture (50-move rule)
        fullmove_number: int - increments after black's move
        move_history: List[Move] - all moves played (for threefold repetition)
    """
    
    def __init__(self, fen: str = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"):
        """
        Initialize board from FEN string (default: starting position).
        
        Args:
            fen: FEN string representing the position
        
        Raises:
            ValueError: If FEN string is invalid
        """
        # Initialize empty board
        self.squares: List[List[Optional[Piece]]] = [[None for _ in range(8)] for _ in range(8)]
        self.active_color: str = 'white'
        self.castling_rights: Dict[str, bool] = {'K': False, 'Q': False, 'k': False, 'q': False}
        self.en_passant_target: Optional[Square] = None
        self.halfmove_clock: int = 0
        self.fullmove_number: int = 1
        self.move_history: List[Move] = []
        
        # Parse FEN
        self._parse_fen(fen)
    
    def _parse_fen(self, fen: str) -> None:
        """
        Parse FEN string and set board state.
        
        FEN format: <pieces> <active> <castling> <en_passant> <halfmove> <fullmove>
        
        Args:
            fen: FEN string
        
        Raises:
            ValueError: If FEN string is invalid
        """
        parts = fen.strip().split()
        if len(parts) != 6:
            raise ValueError(f"Invalid FEN: expected 6 parts, got {len(parts)}")
        
        # Parse piece placement
        ranks = parts[0].split('/')
        if len(ranks) != 8:
            raise ValueError(f"Invalid FEN: expected 8 ranks, got {len(ranks)}")
        
        for rank_idx, rank_str in enumerate(ranks):
            rank = 7 - rank_idx  # FEN starts from rank 8
            file = 0
            
            for char in rank_str:
                if char.isdigit():
                    # Empty squares
                    file += int(char)
                else:
                    # Piece
                    if file >= 8:
                        raise ValueError(f"Invalid FEN: too many pieces in rank {rank + 1}")
                    self.squares[rank][file] = Piece.from_char(char)
                    file += 1
            
            if file != 8:
                raise ValueError(f"Invalid FEN: rank {rank + 1} has {file} squares (expected 8)")
        
        # Parse active color
        if parts[1] not in ['w', 'b']:
            raise ValueError(f"Invalid FEN: active color must be 'w' or 'b', got '{parts[1]}'")
        self.active_color = 'white' if parts[1] == 'w' else 'black'
        
        # Parse castling rights
        if parts[2] != '-':
            for char in parts[2]:
                if char not in 'KQkq':
                    raise ValueError(f"Invalid FEN: invalid castling right '{char}'")
                self.castling_rights[char] = True
        
        # Parse en passant target
        if parts[3] != '-':
            try:
                self.en_passant_target = Square.from_algebraic(parts[3])
            except ValueError as e:
                raise ValueError(f"Invalid FEN: invalid en passant square '{parts[3]}'") from e
        
        # Parse halfmove clock
        try:
            self.halfmove_clock = int(parts[4])
        except ValueError as e:
            raise ValueError(f"Invalid FEN: invalid halfmove clock '{parts[4]}'") from e
        
        # Parse fullmove number
        try:
            self.fullmove_number = int(parts[5])
        except ValueError as e:
            raise ValueError(f"Invalid FEN: invalid fullmove number '{parts[5]}'") from e
    
    def get_piece(self, square: Square) -> Optional[Piece]:
        """
        Get piece at square.
        
        Args:
            square: Square to query
        
        Returns:
            Piece at square or None if empty
        """
        return self.squares[square.rank][square.file]
    
    def set_piece(self, square: Square, piece: Optional[Piece]) -> None:
        """
        Set piece at square.
        
        Args:
            square: Square to set
            piece: Piece to place (or None to clear)
        """
        self.squares[square.rank][square.file] = piece
    
    def make_move(self, move: Move) -> None:
        """
        Apply move to board (mutates state).
        
        This method:
        - Moves the piece
        - Handles captures
        - Updates castling rights
        - Updates en passant target
        - Updates halfmove clock
        - Updates fullmove number
        - Stores state for unmake_move
        
        Args:
            move: Move to apply
        """
        piece = self.get_piece(move.from_square)
        if piece is None:
            raise ValueError(f"No piece at {move.from_square}")
        
        # Store state for unmake_move
        move.captured_piece = self.get_piece(move.to_square)
        move.previous_castling_rights = self.castling_rights.copy()
        move.previous_en_passant = self.en_passant_target
        move.previous_halfmove_clock = self.halfmove_clock
        
        # Detect special moves
        is_capture = move.captured_piece is not None
        is_pawn_move = piece.piece_type == 'pawn'
        
        # Check for castling
        if piece.piece_type == 'king':
            file_diff = move.to_square.file - move.from_square.file
            if abs(file_diff) == 2:
                move.is_castling = True
        
        # Check for en passant
        if (is_pawn_move and 
            self.en_passant_target is not None and 
            move.to_square == self.en_passant_target):
            move.is_en_passant = True
        
        # Update halfmove clock (reset on pawn move or capture)
        if is_pawn_move or is_capture:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1
        
        # Handle castling
        if move.is_castling:
            # Move king
            self.set_piece(move.to_square, piece)
            self.set_piece(move.from_square, None)
            
            # Move rook
            if move.to_square.file > move.from_square.file:
                # Kingside castling
                rook_from = Square(move.from_square.rank, 7)
                rook_to = Square(move.from_square.rank, 5)
            else:
                # Queenside castling
                rook_from = Square(move.from_square.rank, 0)
                rook_to = Square(move.from_square.rank, 3)
            
            rook = self.get_piece(rook_from)
            self.set_piece(rook_to, rook)
            self.set_piece(rook_from, None)
        
        # Handle en passant capture
        elif move.is_en_passant:
            # Move pawn
            self.set_piece(move.to_square, piece)
            self.set_piece(move.from_square, None)
            
            # Remove captured pawn
            captured_pawn_square = Square(move.from_square.rank, move.to_square.file)
            move.captured_piece = self.get_piece(captured_pawn_square)
            self.set_piece(captured_pawn_square, None)
        
        # Handle promotion
        elif move.promotion:
            promoted_piece = Piece(move.promotion, piece.color)
            self.set_piece(move.to_square, promoted_piece)
            self.set_piece(move.from_square, None)
        
        # Normal move
        else:
            self.set_piece(move.to_square, piece)
            self.set_piece(move.from_square, None)
        
        # Update en passant target
        self.en_passant_target = None
        if is_pawn_move:
            rank_diff = abs(move.to_square.rank - move.from_square.rank)
            if rank_diff == 2:
                # Double pawn push - set en passant target
                ep_rank = (move.from_square.rank + move.to_square.rank) // 2
                self.en_passant_target = Square(ep_rank, move.from_square.file)
        
        # Update castling rights
        # King moves
        if piece.piece_type == 'king':
            if piece.color == 'white':
                self.castling_rights['K'] = False
                self.castling_rights['Q'] = False
            else:
                self.castling_rights['k'] = False
                self.castling_rights['q'] = False
        
        # Rook moves
        if piece.piece_type == 'rook':
            if piece.color == 'white':
                if move.from_square == Square(0, 0):
                    self.castling_rights['Q'] = False
                elif move.from_square == Square(0, 7):
                    self.castling_rights['K'] = False
            else:
                if move.from_square == Square(7, 0):
                    self.castling_rights['q'] = False
                elif move.from_square == Square(7, 7):
                    self.castling_rights['k'] = False
        
        # Rook captures (opponent's rook captured)
        if is_capture and move.captured_piece.piece_type == 'rook':
            if move.to_square == Square(0, 0):
                self.castling_rights['Q'] = False
            elif move.to_square == Square(0, 7):
                self.castling_rights['K'] = False
            elif move.to_square == Square(7, 0):
                self.castling_rights['q'] = False
            elif move.to_square == Square(7, 7):
                self.castling_rights['k'] = False
        
        # Switch active color
        if self.active_color == 'black':
            self.fullmove_number += 1
        self.active_color = 'black' if self.active_color == 'white' else 'white'
        
        # Add to move history
        self.move_history.append(move)
    
    def unmake_move(self, move: Move) -> None:
        """
        Undo last move (for search).
        
        Args:
            move: Move to undo (must be the last move made)
        """
        # Switch active color back
        self.active_color = 'black' if self.active_color == 'white' else 'white'
        if self.active_color == 'black':
            self.fullmove_number -= 1
        
        # Get the piece that moved
        if move.promotion:
            # Restore original pawn
            piece = Piece('pawn', self.active_color)
        else:
            piece = self.get_piece(move.to_square)
        
        # Handle castling
        if move.is_castling:
            # Move king back
            self.set_piece(move.from_square, piece)
            self.set_piece(move.to_square, None)
            
            # Move rook back
            if move.to_square.file > move.from_square.file:
                # Kingside castling
                rook_from = Square(move.from_square.rank, 7)
                rook_to = Square(move.from_square.rank, 5)
            else:
                # Queenside castling
                rook_from = Square(move.from_square.rank, 0)
                rook_to = Square(move.from_square.rank, 3)
            
            rook = self.get_piece(rook_to)
            self.set_piece(rook_from, rook)
            self.set_piece(rook_to, None)
        
        # Handle en passant
        elif move.is_en_passant:
            # Move pawn back
            self.set_piece(move.from_square, piece)
            self.set_piece(move.to_square, None)
            
            # Restore captured pawn
            captured_pawn_square = Square(move.from_square.rank, move.to_square.file)
            self.set_piece(captured_pawn_square, move.captured_piece)
        
        # Normal move or promotion
        else:
            self.set_piece(move.from_square, piece)
            self.set_piece(move.to_square, move.captured_piece)
        
        # Restore state
        self.castling_rights = move.previous_castling_rights
        self.en_passant_target = move.previous_en_passant
        self.halfmove_clock = move.previous_halfmove_clock
        
        # Remove from move history
        if self.move_history and self.move_history[-1] == move:
            self.move_history.pop()
    
    def copy(self) -> 'Board':
        """
        Create deep copy of board.
        
        Returns:
            New Board instance with same state
        """
        return copy.deepcopy(self)
    
    def to_fen(self) -> str:
        """
        Export position as FEN string.
        
        Returns:
            FEN string
        """
        # Piece placement
        fen_parts = []
        for rank in range(7, -1, -1):  # Start from rank 8
            empty_count = 0
            rank_str = ''
            
            for file in range(8):
                piece = self.squares[rank][file]
                if piece is None:
                    empty_count += 1
                else:
                    if empty_count > 0:
                        rank_str += str(empty_count)
                        empty_count = 0
                    rank_str += str(piece)
            
            if empty_count > 0:
                rank_str += str(empty_count)
            
            fen_parts.append(rank_str)
        
        fen = '/'.join(fen_parts)
        
        # Active color
        fen += ' ' + ('w' if self.active_color == 'white' else 'b')
        
        # Castling rights
        castling = ''
        for right in ['K', 'Q', 'k', 'q']:
            if self.castling_rights[right]:
                castling += right
        fen += ' ' + (castling if castling else '-')
        
        # En passant target
        if self.en_passant_target:
            fen += ' ' + self.en_passant_target.to_algebraic()
        else:
            fen += ' -'
        
        # Halfmove clock and fullmove number
        fen += f' {self.halfmove_clock} {self.fullmove_number}'
        
        return fen
    
    def __str__(self) -> str:
        """
        Human-readable board display.
        
        Returns:
            String representation of board
        """
        lines = []
        for rank in range(7, -1, -1):
            line = f"{rank + 1} "
            for file in range(8):
                piece = self.squares[rank][file]
                if piece is None:
                    line += '. '
                else:
                    line += str(piece) + ' '
            lines.append(line)
        lines.append('  a b c d e f g h')
        return '\n'.join(lines)
    
    def find_king(self, color: str) -> Optional[Square]:
        """
        Find the king of the given color.
        
        Args:
            color: 'white' or 'black'
        
        Returns:
            Square containing the king, or None if not found
        """
        for rank in range(8):
            for file in range(8):
                piece = self.squares[rank][file]
                if piece and piece.piece_type == 'king' and piece.color == color:
                    return Square(rank, file)
        return None
