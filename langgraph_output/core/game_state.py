"""
Game state management and rule enforcement.

Implements:
- GameState class
- Legal move generation
- Check detection
- Checkmate and stalemate detection
- Draw conditions (50-move rule, threefold repetition, insufficient material)
- Game result determination
"""

from typing import List, Optional, Set, Tuple
from .board import Board
from .move import Move, Square
from .pieces import Piece


class GameState:
    """
    Game state manager - handles move generation and game status.
    
    Attributes:
        board: Board
    """
    
    def __init__(self, board: Board):
        """
        Initialize game state.
        
        Args:
            board: Board instance
        """
        self.board = board
    
    def get_legal_moves(self) -> List[Move]:
        """
        Generate all legal moves for active player.
        
        Returns:
            List of legal moves
        """
        pseudo_legal_moves = self._generate_pseudo_legal_moves()
        legal_moves = []
        
        for move in pseudo_legal_moves:
            if self._is_move_legal(move):
                legal_moves.append(move)
        
        return legal_moves
    
    def is_legal_move(self, move: Move) -> bool:
        """
        Check if move is legal.
        
        Args:
            move: Move to check
        
        Returns:
            True if move is legal
        """
        # Check if move is in pseudo-legal moves
        pseudo_legal = self._generate_pseudo_legal_moves()
        if move not in pseudo_legal:
            return False
        
        return self._is_move_legal(move)
    
    def _is_move_legal(self, move: Move) -> bool:
        """
        Check if pseudo-legal move is actually legal (doesn't leave king in check).
        
        Args:
            move: Move to check
        
        Returns:
            True if move is legal
        """
        # Make move
        self.board.make_move(move)
        
        # Check if opponent's king is in check (we just moved, so check opponent)
        # Actually, we need to check if OUR king is in check after the move
        # Since make_move switches active_color, we need to check the opposite color
        our_color = 'black' if self.board.active_color == 'white' else 'white'
        in_check = self._is_in_check(our_color)
        
        # Unmake move
        self.board.unmake_move(move)
        
        return not in_check
    
    def is_check(self) -> bool:
        """
        Check if active player is in check.
        
        Returns:
            True if active player is in check
        """
        return self._is_in_check(self.board.active_color)
    
    def _is_in_check(self, color: str) -> bool:
        """
        Check if the given color's king is in check.
        
        Args:
            color: 'white' or 'black'
        
        Returns:
            True if king is in check
        """
        king_square = self.board.find_king(color)
        if king_square is None:
            return False  # No king (shouldn't happen in valid position)
        
        # Check if any opponent piece attacks the king
        opponent_color = 'black' if color == 'white' else 'white'
        return self._is_square_attacked(king_square, opponent_color)
    
    def _is_square_attacked(self, square: Square, by_color: str) -> bool:
        """
        Check if a square is attacked by any piece of the given color.
        
        Args:
            square: Square to check
            by_color: Color of attacking pieces
        
        Returns:
            True if square is attacked
        """
        # Check all pieces of the attacking color
        for rank in range(8):
            for file in range(8):
                piece = self.board.squares[rank][file]
                if piece and piece.color == by_color:
                    from_square = Square(rank, file)
                    if self._can_piece_attack(from_square, square, piece):
                        return True
        
        return False
    
    def _can_piece_attack(self, from_square: Square, to_square: Square, piece: Piece) -> bool:
        """
        Check if a piece can attack a target square.
        
        This is similar to move generation but doesn't check for check.
        
        Args:
            from_square: Square containing the piece
            to_square: Target square
            piece: Piece to check
        
        Returns:
            True if piece can attack target
        """
        if from_square == to_square:
            return False
        
        rank_diff = to_square.rank - from_square.rank
        file_diff = to_square.file - from_square.file
        
        if piece.piece_type == 'pawn':
            # Pawns attack diagonally
            direction = 1 if piece.color == 'white' else -1
            if rank_diff == direction and abs(file_diff) == 1:
                return True
        
        elif piece.piece_type == 'knight':
            # Knight moves in L-shape
            if (abs(rank_diff), abs(file_diff)) in [(2, 1), (1, 2)]:
                return True
        
        elif piece.piece_type == 'bishop':
            # Bishop moves diagonally
            if abs(rank_diff) == abs(file_diff):
                return self._is_path_clear(from_square, to_square)
        
        elif piece.piece_type == 'rook':
            # Rook moves horizontally or vertically
            if rank_diff == 0 or file_diff == 0:
                return self._is_path_clear(from_square, to_square)
        
        elif piece.piece_type == 'queen':
            # Queen moves like rook or bishop
            if rank_diff == 0 or file_diff == 0 or abs(rank_diff) == abs(file_diff):
                return self._is_path_clear(from_square, to_square)
        
        elif piece.piece_type == 'king':
            # King moves one square in any direction
            if abs(rank_diff) <= 1 and abs(file_diff) <= 1:
                return True
        
        return False
    
    def _is_path_clear(self, from_square: Square, to_square: Square) -> bool:
        """
        Check if path between two squares is clear (no pieces in between).
        
        Args:
            from_square: Starting square
            to_square: Ending square
        
        Returns:
            True if path is clear
        """
        rank_diff = to_square.rank - from_square.rank
        file_diff = to_square.file - from_square.file
        
        # Determine direction
        rank_step = 0 if rank_diff == 0 else (1 if rank_diff > 0 else -1)
        file_step = 0 if file_diff == 0 else (1 if file_diff > 0 else -1)
        
        # Check each square along the path
        current_rank = from_square.rank + rank_step
        current_file = from_square.file + file_step
        
        while current_rank != to_square.rank or current_file != to_square.file:
            if self.board.squares[current_rank][current_file] is not None:
                return False
            current_rank += rank_step
            current_file += file_step
        
        return True
    
    def _generate_pseudo_legal_moves(self) -> List[Move]:
        """
        Generate all pseudo-legal moves (moves that follow piece movement rules).
        
        Does not check if moves leave king in check.
        
        Returns:
            List of pseudo-legal moves
        """
        moves = []
        color = self.board.active_color
        
        # Generate moves for each piece
        for rank in range(8):
            for file in range(8):
                piece = self.board.squares[rank][file]
                if piece and piece.color == color:
                    from_square = Square(rank, file)
                    moves.extend(self._generate_piece_moves(from_square, piece))
        
        return moves
    
    def _generate_piece_moves(self, from_square: Square, piece: Piece) -> List[Move]:
        """
        Generate pseudo-legal moves for a piece.
        
        Args:
            from_square: Square containing the piece
            piece: Piece to generate moves for
        
        Returns:
            List of pseudo-legal moves
        """
        if piece.piece_type == 'pawn':
            return self._generate_pawn_moves(from_square, piece)
        elif piece.piece_type == 'knight':
            return self._generate_knight_moves(from_square, piece)
        elif piece.piece_type == 'bishop':
            return self._generate_bishop_moves(from_square, piece)
        elif piece.piece_type == 'rook':
            return self._generate_rook_moves(from_square, piece)
        elif piece.piece_type == 'queen':
            return self._generate_queen_moves(from_square, piece)
        elif piece.piece_type == 'king':
            return self._generate_king_moves(from_square, piece)
        return []
    
    def _generate_pawn_moves(self, from_square: Square, piece: Piece) -> List[Move]:
        """Generate pawn moves."""
        moves = []
        direction = 1 if piece.color == 'white' else -1
        start_rank = 1 if piece.color == 'white' else 6
        promotion_rank = 7 if piece.color == 'white' else 0
        
        # Forward move
        to_rank = from_square.rank + direction
        if 0 <= to_rank <= 7:
            to_square = Square(to_rank, from_square.file)
            if self.board.get_piece(to_square) is None:
                # Check for promotion
                if to_rank == promotion_rank:
                    for promo in ['queen', 'rook', 'bishop', 'knight']:
                        moves.append(Move(from_square, to_square, promo))
                else:
                    moves.append(Move(from_square, to_square))
                
                # Double forward move from start
                if from_square.rank == start_rank:
                    to_rank2 = from_square.rank + 2 * direction
                    to_square2 = Square(to_rank2, from_square.file)
                    if self.board.get_piece(to_square2) is None:
                        moves.append(Move(from_square, to_square2))
        
        # Captures
        for file_offset in [-1, 1]:
            to_file = from_square.file + file_offset
            to_rank = from_square.rank + direction
            if 0 <= to_file <= 7 and 0 <= to_rank <= 7:
                to_square = Square(to_rank, to_file)
                target_piece = self.board.get_piece(to_square)
                
                # Regular capture
                if target_piece and target_piece.color != piece.color:
                    if to_rank == promotion_rank:
                        for promo in ['queen', 'rook', 'bishop', 'knight']:
                            moves.append(Move(from_square, to_square, promo))
                    else:
                        moves.append(Move(from_square, to_square))
                
                # En passant
                elif (self.board.en_passant_target and 
                      to_square == self.board.en_passant_target):
                    moves.append(Move(from_square, to_square))
        
        return moves
    
    def _generate_knight_moves(self, from_square: Square, piece: Piece) -> List[Move]:
        """Generate knight moves."""
        moves = []
        offsets = [
            (2, 1), (2, -1), (-2, 1), (-2, -1),
            (1, 2), (1, -2), (-1, 2), (-1, -2)
        ]
        
        for rank_offset, file_offset in offsets:
            to_rank = from_square.rank + rank_offset
            to_file = from_square.file + file_offset
            
            if 0 <= to_rank <= 7 and 0 <= to_file <= 7:
                to_square = Square(to_rank, to_file)
                target_piece = self.board.get_piece(to_square)
                
                if target_piece is None or target_piece.color != piece.color:
                    moves.append(Move(from_square, to_square))
        
        return moves
    
    def _generate_sliding_moves(self, from_square: Square, piece: Piece, 
                                directions: List[Tuple[int, int]]) -> List[Move]:
        """Generate moves for sliding pieces (bishop, rook, queen)."""
        moves = []
        
        for rank_step, file_step in directions:
            to_rank = from_square.rank + rank_step
            to_file = from_square.file + file_step
            
            while 0 <= to_rank <= 7 and 0 <= to_file <= 7:
                to_square = Square(to_rank, to_file)
                target_piece = self.board.get_piece(to_square)
                
                if target_piece is None:
                    moves.append(Move(from_square, to_square))
                elif target_piece.color != piece.color:
                    moves.append(Move(from_square, to_square))
                    break
                else:
                    break
                
                to_rank += rank_step
                to_file += file_step
        
        return moves
    
    def _generate_bishop_moves(self, from_square: Square, piece: Piece) -> List[Move]:
        """Generate bishop moves."""
        directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        return self._generate_sliding_moves(from_square, piece, directions)
    
    def _generate_rook_moves(self, from_square: Square, piece: Piece) -> List[Move]:
        """Generate rook moves."""
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        return self._generate_sliding_moves(from_square, piece, directions)
    
    def _generate_queen_moves(self, from_square: Square, piece: Piece) -> List[Move]:
        """Generate queen moves."""
        directions = [
            (1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]
        return self._generate_sliding_moves(from_square, piece, directions)
    
    def _generate_king_moves(self, from_square: Square, piece: Piece) -> List[Move]:
        """Generate king moves including castling."""
        moves = []
        
        # Normal king moves
        for rank_offset in [-1, 0, 1]:
            for file_offset in [-1, 0, 1]:
                if rank_offset == 0 and file_offset == 0:
                    continue
                
                to_rank = from_square.rank + rank_offset
                to_file = from_square.file + file_offset
                
                if 0 <= to_rank <= 7 and 0 <= to_file <= 7:
                    to_square = Square(to_rank, to_file)
                    target_piece = self.board.get_piece(to_square)
                    
                    if target_piece is None or target_piece.color != piece.color:
                        moves.append(Move(from_square, to_square))
        
        # Castling
        if not self.is_check():  # Can't castle out of check
            moves.extend(self._generate_castling_moves(from_square, piece))
        
        return moves
    
    def _generate_castling_moves(self, from_square: Square, piece: Piece) -> List[Move]:
        """Generate castling moves."""
        moves = []
        
        if piece.color == 'white':
            # Kingside castling
            if self.board.castling_rights['K']:
                if self._can_castle_kingside('white'):
                    moves.append(Move(from_square, Square(0, 6)))
            
            # Queenside castling
            if self.board.castling_rights['Q']:
                if self._can_castle_queenside('white'):
                    moves.append(Move(from_square, Square(0, 2)))
        else:
            # Kingside castling
            if self.board.castling_rights['k']:
                if self._can_castle_kingside('black'):
                    moves.append(Move(from_square, Square(7, 6)))
            
            # Queenside castling
            if self.board.castling_rights['q']:
                if self._can_castle_queenside('black'):
                    moves.append(Move(from_square, Square(7, 2)))
        
        return moves
    
    def _can_castle_kingside(self, color: str) -> bool:
        """Check if kingside castling is possible."""
        rank = 0 if color == 'white' else 7
        
        # Check if squares between king and rook are empty
        if (self.board.get_piece(Square(rank, 5)) is not None or
            self.board.get_piece(Square(rank, 6)) is not None):
            return False
        
        # Check if king passes through or lands on attacked square
        if (self._is_square_attacked(Square(rank, 4), 'black' if color == 'white' else 'white') or
            self._is_square_attacked(Square(rank, 5), 'black' if color == 'white' else 'white') or
            self._is_square_attacked(Square(rank, 6), 'black' if color == 'white' else 'white')):
            return False
        
        return True
    
    def _can_castle_queenside(self, color: str) -> bool:
        """Check if queenside castling is possible."""
        rank = 0 if color == 'white' else 7
        
        # Check if squares between king and rook are empty
        if (self.board.get_piece(Square(rank, 1)) is not None or
            self.board.get_piece(Square(rank, 2)) is not None or
            self.board.get_piece(Square(rank, 3)) is not None):
            return False
        
        # Check if king passes through or lands on attacked square
        if (self._is_square_attacked(Square(rank, 4), 'black' if color == 'white' else 'white') or
            self._is_square_attacked(Square(rank, 3), 'black' if color == 'white' else 'white') or
            self._is_square_attacked(Square(rank, 2), 'black' if color == 'white' else 'white')):
            return False
        
        return True
    
    def is_checkmate(self) -> bool:
        """
        Check if active player is checkmated.
        
        Returns:
            True if active player is checkmated
        """
        if not self.is_check():
            return False
        
        # Check if there are any legal moves
        return len(self.get_legal_moves()) == 0
    
    def is_stalemate(self) -> bool:
        """
        Check if position is stalemate.
        
        Returns:
            True if position is stalemate
        """
        if self.is_check():
            return False
        
        # Check if there are any legal moves
        return len(self.get_legal_moves()) == 0
    
    def is_draw(self) -> bool:
        """
        Check for draw (stalemate, 50-move, repetition, insufficient material).
        
        Returns:
            True if position is a draw
        """
        return (self.is_stalemate() or
                self._is_fifty_move_draw() or
                self.is_threefold_repetition() or
                self.is_insufficient_material())
    
    def _is_fifty_move_draw(self) -> bool:
        """
        Check for 50-move rule draw.
        
        Returns:
            True if 50 moves without pawn move or capture
        """
        return self.board.halfmove_clock >= 100  # 50 full moves = 100 half moves
    
    def is_threefold_repetition(self) -> bool:
        """
        Check for threefold repetition.
        
        Returns:
            True if current position has occurred 3 times
        """
        current_fen = self._position_fen()
        count = 0
        
        # Count occurrences in move history
        # We need to reconstruct positions from move history
        # For simplicity, we'll use a simplified approach
        # In a full implementation, we'd store position hashes
        
        # Create a temporary board and replay moves
        temp_board = Board(self.board.to_fen().split()[0] + " w KQkq - 0 1")
        positions = [self._position_fen_from_board(temp_board)]
        
        for move in self.board.move_history:
            temp_board.make_move(move)
            positions.append(self._position_fen_from_board(temp_board))
        
        # Count current position
        for pos in positions:
            if pos == current_fen:
                count += 1
        
        return count >= 3
    
    def _position_fen(self) -> str:
        """Get position-only FEN (without move counters)."""
        return self._position_fen_from_board(self.board)
    
    def _position_fen_from_board(self, board: Board) -> str:
        """Get position-only FEN from a board."""
        fen_parts = board.to_fen().split()
        # Include piece placement, active color, castling, and en passant
        # Exclude halfmove and fullmove counters
        return ' '.join(fen_parts[:4])
    
    def is_insufficient_material(self) -> bool:
        """
        Check for insufficient mating material.
        
        Returns:
            True if neither side can checkmate
        """
        pieces = []
        for rank in range(8):
            for file in range(8):
                piece = self.board.squares[rank][file]
                if piece:
                    pieces.append(piece)
        
        # King vs King
        if len(pieces) == 2:
            return True
        
        # King and minor piece vs King
        if len(pieces) == 3:
            for piece in pieces:
                if piece.piece_type in ['bishop', 'knight']:
                    return True
        
        # King and bishop vs King and bishop (same color squares)
        if len(pieces) == 4:
            bishops = [p for p in pieces if p.piece_type == 'bishop']
            if len(bishops) == 2:
                # Find bishop squares
                bishop_squares = []
                for rank in range(8):
                    for file in range(8):
                        piece = self.board.squares[rank][file]
                        if piece and piece.piece_type == 'bishop':
                            bishop_squares.append((rank, file))
                
                # Check if bishops are on same color squares
                if len(bishop_squares) == 2:
                    square1_color = (bishop_squares[0][0] + bishop_squares[0][1]) % 2
                    square2_color = (bishop_squares[1][0] + bishop_squares[1][1]) % 2
                    if square1_color == square2_color:
                        return True
        
        return False
    
    def get_game_result(self) -> Optional[str]:
        """
        Return game result.
        
        Returns:
            '1-0' (white wins), '0-1' (black wins), '1/2-1/2' (draw), or None (game ongoing)
        """
        if self.is_checkmate():
            # Active player is checkmated, so opponent wins
            return '0-1' if self.board.active_color == 'white' else '1-0'
        
        if self.is_draw():
            return '1/2-1/2'
        
        return None
