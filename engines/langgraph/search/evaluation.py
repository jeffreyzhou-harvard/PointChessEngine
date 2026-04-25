"""
Position evaluation.

Implements:
- Evaluator class with multiple evaluation components
- Material balance
- Piece-square tables
- King safety
- Mobility
- Pawn structure
- Center control
"""

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.board import Board
    from core.game_state import GameState

from core.pieces import PIECE_VALUES


# Piece-square tables (from white's perspective)
# Values are in centipawns, indexed by [rank][file]

PAWN_TABLE = [
    [  0,   0,   0,   0,   0,   0,   0,   0],
    [ 50,  50,  50,  50,  50,  50,  50,  50],
    [ 10,  10,  20,  30,  30,  20,  10,  10],
    [  5,   5,  10,  25,  25,  10,   5,   5],
    [  0,   0,   0,  20,  20,   0,   0,   0],
    [  5,  -5, -10,   0,   0, -10,  -5,   5],
    [  5,  10,  10, -20, -20,  10,  10,   5],
    [  0,   0,   0,   0,   0,   0,   0,   0]
]

KNIGHT_TABLE = [
    [-50, -40, -30, -30, -30, -30, -40, -50],
    [-40, -20,   0,   0,   0,   0, -20, -40],
    [-30,   0,  10,  15,  15,  10,   0, -30],
    [-30,   5,  15,  20,  20,  15,   5, -30],
    [-30,   0,  15,  20,  20,  15,   0, -30],
    [-30,   5,  10,  15,  15,  10,   5, -30],
    [-40, -20,   0,   5,   5,   0, -20, -40],
    [-50, -40, -30, -30, -30, -30, -40, -50]
]

BISHOP_TABLE = [
    [-20, -10, -10, -10, -10, -10, -10, -20],
    [-10,   0,   0,   0,   0,   0,   0, -10],
    [-10,   0,   5,  10,  10,   5,   0, -10],
    [-10,   5,   5,  10,  10,   5,   5, -10],
    [-10,   0,  10,  10,  10,  10,   0, -10],
    [-10,  10,  10,  10,  10,  10,  10, -10],
    [-10,   5,   0,   0,   0,   0,   5, -10],
    [-20, -10, -10, -10, -10, -10, -10, -20]
]

ROOK_TABLE = [
    [  0,   0,   0,   0,   0,   0,   0,   0],
    [  5,  10,  10,  10,  10,  10,  10,   5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [  0,   0,   0,   5,   5,   0,   0,   0]
]

QUEEN_TABLE = [
    [-20, -10, -10,  -5,  -5, -10, -10, -20],
    [-10,   0,   0,   0,   0,   0,   0, -10],
    [-10,   0,   5,   5,   5,   5,   0, -10],
    [ -5,   0,   5,   5,   5,   5,   0,  -5],
    [  0,   0,   5,   5,   5,   5,   0,  -5],
    [-10,   5,   5,   5,   5,   5,   0, -10],
    [-10,   0,   5,   0,   0,   0,   0, -10],
    [-20, -10, -10,  -5,  -5, -10, -10, -20]
]

KING_MIDDLE_GAME_TABLE = [
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-20, -30, -30, -40, -40, -30, -30, -20],
    [-10, -20, -20, -20, -20, -20, -20, -10],
    [ 20,  20,   0,   0,   0,   0,  20,  20],
    [ 20,  30,  10,   0,   0,  10,  30,  20]
]

KING_END_GAME_TABLE = [
    [-50, -40, -30, -20, -20, -30, -40, -50],
    [-30, -20, -10,   0,   0, -10, -20, -30],
    [-30, -10,  20,  30,  30,  20, -10, -30],
    [-30, -10,  30,  40,  40,  30, -10, -30],
    [-30, -10,  30,  40,  40,  30, -10, -30],
    [-30, -10,  20,  30,  30,  20, -10, -30],
    [-30, -30,   0,   0,   0,   0, -30, -30],
    [-50, -30, -30, -30, -30, -30, -30, -50]
]


class Evaluator:
    """
    Position evaluator.
    
    Evaluation components:
    - Material balance
    - Piece-square tables
    - King safety
    - Mobility
    - Pawn structure
    - Center control
    """
    
    def __init__(self):
        """Initialize evaluator."""
        pass
    
    def evaluate(self, board: 'Board', game_state: 'GameState' = None) -> int:
        """
        Evaluate position from white's perspective.
        
        Args:
            board: Board to evaluate
            game_state: Optional GameState for mobility evaluation
        
        Returns:
            Score in centipawns (positive = white advantage)
        """
        score = 0
        
        # Material balance
        score += self.evaluate_material(board)
        
        # Piece-square tables
        score += self.evaluate_piece_square(board)
        
        # King safety
        score += self.evaluate_king_safety(board)
        
        # Mobility (if game_state provided)
        if game_state:
            score += self.evaluate_mobility(board, game_state)
        
        # Pawn structure
        score += self.evaluate_pawn_structure(board)
        
        # Center control
        score += self.evaluate_center_control(board)
        
        return score
    
    def evaluate_material(self, board: 'Board') -> int:
        """
        Evaluate material balance.
        
        Args:
            board: Board to evaluate
        
        Returns:
            Material score in centipawns
        """
        score = 0
        
        for rank in range(8):
            for file in range(8):
                piece = board.squares[rank][file]
                if piece:
                    value = piece.get_value()
                    if piece.color == 'white':
                        score += value
                    else:
                        score -= value
        
        return score
    
    def evaluate_piece_square(self, board: 'Board') -> int:
        """
        Evaluate piece placement using piece-square tables.
        
        Args:
            board: Board to evaluate
        
        Returns:
            Piece-square score in centipawns
        """
        score = 0
        
        # Determine if we're in endgame (simplified: few pieces remaining)
        piece_count = sum(1 for rank in range(8) for file in range(8) 
                         if board.squares[rank][file] is not None)
        is_endgame = piece_count <= 10
        
        for rank in range(8):
            for file in range(8):
                piece = board.squares[rank][file]
                if piece:
                    # Get piece-square value
                    ps_value = self._get_piece_square_value(piece, rank, file, is_endgame)
                    
                    if piece.color == 'white':
                        score += ps_value
                    else:
                        score -= ps_value
        
        return score
    
    def _get_piece_square_value(self, piece, rank: int, file: int, is_endgame: bool) -> int:
        """Get piece-square table value for a piece."""
        # For black pieces, flip the rank
        if piece.color == 'black':
            rank = 7 - rank
        
        if piece.piece_type == 'pawn':
            return PAWN_TABLE[rank][file]
        elif piece.piece_type == 'knight':
            return KNIGHT_TABLE[rank][file]
        elif piece.piece_type == 'bishop':
            return BISHOP_TABLE[rank][file]
        elif piece.piece_type == 'rook':
            return ROOK_TABLE[rank][file]
        elif piece.piece_type == 'queen':
            return QUEEN_TABLE[rank][file]
        elif piece.piece_type == 'king':
            if is_endgame:
                return KING_END_GAME_TABLE[rank][file]
            else:
                return KING_MIDDLE_GAME_TABLE[rank][file]
        
        return 0
    
    def evaluate_king_safety(self, board: 'Board') -> int:
        """
        Evaluate king safety.
        
        Args:
            board: Board to evaluate
        
        Returns:
            King safety score in centipawns
        """
        score = 0
        
        # Find kings
        white_king = board.find_king('white')
        black_king = board.find_king('black')
        
        if white_king:
            score += self._evaluate_king_safety_for_color(board, white_king, 'white')
        
        if black_king:
            score -= self._evaluate_king_safety_for_color(board, black_king, 'black')
        
        return score
    
    def _evaluate_king_safety_for_color(self, board: 'Board', king_square, color: str) -> int:
        """Evaluate king safety for one side."""
        safety = 0
        
        # Pawn shield bonus (pawns in front of king)
        pawn_direction = 1 if color == 'white' else -1
        shield_rank = king_square.rank + pawn_direction
        
        if 0 <= shield_rank <= 7:
            for file_offset in [-1, 0, 1]:
                shield_file = king_square.file + file_offset
                if 0 <= shield_file <= 7:
                    piece = board.squares[shield_rank][shield_file]
                    if piece and piece.piece_type == 'pawn' and piece.color == color:
                        safety += 10
        
        # Penalty for exposed king in center
        if 2 <= king_square.file <= 5:
            safety -= 20
        
        return safety
    
    def evaluate_mobility(self, board: 'Board', game_state: 'GameState') -> int:
        """
        Evaluate mobility (number of legal moves).
        
        Args:
            board: Board to evaluate
            game_state: GameState for move generation
        
        Returns:
            Mobility score in centipawns
        """
        # Save current state
        original_color = board.active_color
        
        # Count white's mobility
        board.active_color = 'white'
        from core.game_state import GameState
        white_gs = GameState(board)
        white_moves = len(white_gs.get_legal_moves())
        
        # Count black's mobility
        board.active_color = 'black'
        black_gs = GameState(board)
        black_moves = len(black_gs.get_legal_moves())
        
        # Restore state
        board.active_color = original_color
        
        # Mobility bonus (scaled down to not dominate)
        mobility_score = (white_moves - black_moves) * 2
        
        return mobility_score
    
    def evaluate_pawn_structure(self, board: 'Board') -> int:
        """
        Evaluate pawn structure.
        
        Args:
            board: Board to evaluate
        
        Returns:
            Pawn structure score in centipawns
        """
        score = 0
        
        # Analyze white pawns
        white_pawns = self._get_pawn_files(board, 'white')
        score += self._evaluate_pawn_structure_for_color(white_pawns)
        
        # Analyze black pawns
        black_pawns = self._get_pawn_files(board, 'black')
        score -= self._evaluate_pawn_structure_for_color(black_pawns)
        
        return score
    
    def _get_pawn_files(self, board: 'Board', color: str) -> dict:
        """Get dictionary of file -> list of pawn ranks."""
        pawn_files = {f: [] for f in range(8)}
        
        for rank in range(8):
            for file in range(8):
                piece = board.squares[rank][file]
                if piece and piece.piece_type == 'pawn' and piece.color == color:
                    pawn_files[file].append(rank)
        
        return pawn_files
    
    def _evaluate_pawn_structure_for_color(self, pawn_files: dict) -> int:
        """Evaluate pawn structure for one color."""
        score = 0
        
        for file, ranks in pawn_files.items():
            # Doubled pawns penalty
            if len(ranks) > 1:
                score -= 20 * (len(ranks) - 1)
            
            # Isolated pawns penalty (no pawns on adjacent files)
            if ranks:
                has_neighbor = False
                for adj_file in [file - 1, file + 1]:
                    if 0 <= adj_file <= 7 and pawn_files[adj_file]:
                        has_neighbor = True
                        break
                
                if not has_neighbor:
                    score -= 15
        
        # Passed pawns bonus (simplified: no enemy pawns ahead on same or adjacent files)
        # This is a simplified check - full implementation would be more complex
        
        return score
    
    def evaluate_center_control(self, board: 'Board') -> int:
        """
        Evaluate center control.
        
        Args:
            board: Board to evaluate
        
        Returns:
            Center control score in centipawns
        """
        score = 0
        
        # Central squares (e4, d4, e5, d5)
        center_squares = [(3, 3), (3, 4), (4, 3), (4, 4)]
        
        # Extended center
        extended_center = [
            (2, 2), (2, 3), (2, 4), (2, 5),
            (3, 2), (3, 5),
            (4, 2), (4, 5),
            (5, 2), (5, 3), (5, 4), (5, 5)
        ]
        
        # Bonus for pieces in center
        for rank, file in center_squares:
            piece = board.squares[rank][file]
            if piece:
                bonus = 15
                if piece.color == 'white':
                    score += bonus
                else:
                    score -= bonus
        
        # Smaller bonus for extended center
        for rank, file in extended_center:
            piece = board.squares[rank][file]
            if piece:
                bonus = 5
                if piece.color == 'white':
                    score += bonus
                else:
                    score -= bonus
        
        return score
