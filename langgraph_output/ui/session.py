"""
Game session management.

Wraps GameState and Engine to provide a clean interface for the UI.
Handles game lifecycle, move validation, and engine interaction.
"""

from typing import Optional, List, Dict, Any
from core.board import Board
from core.game_state import GameState
from core.move import Move, Square
from search.engine import Engine


class GameSession:
    """
    Game session - manages a single game between human and engine.
    
    Attributes:
        board: Board instance
        game_state: GameState instance
        engine: Engine instance
        human_color: 'white' or 'black'
        elo_rating: Current engine ELO rating
    """
    
    def __init__(self, human_color: str = 'white', elo_rating: int = 1500):
        """
        Initialize new game session.
        
        Args:
            human_color: Color for human player ('white' or 'black')
            elo_rating: Engine strength (400-2400)
        """
        self.board = Board()
        self.game_state = GameState(self.board)
        self.engine = Engine(elo_rating)
        self.human_color = human_color
        self.elo_rating = elo_rating
        self.move_list: List[str] = []  # Algebraic notation moves
    
    def new_game(self, human_color: str = 'white', elo_rating: Optional[int] = None) -> None:
        """
        Start a new game.
        
        Args:
            human_color: Color for human player
            elo_rating: Optional new ELO rating (keeps current if None)
        """
        self.board = Board()
        self.game_state = GameState(self.board)
        self.human_color = human_color
        self.move_list = []
        
        if elo_rating is not None:
            self.elo_rating = elo_rating
            self.engine.set_elo(elo_rating)
        
        self.engine.new_game()
    
    def set_elo(self, elo_rating: int) -> None:
        """
        Adjust engine strength.
        
        Args:
            elo_rating: New ELO rating (400-2400)
        """
        self.elo_rating = elo_rating
        self.engine.set_elo(elo_rating)
    
    def get_legal_moves(self) -> List[str]:
        """
        Get legal moves in UCI notation.
        
        Returns:
            List of UCI move strings
        """
        moves = self.game_state.get_legal_moves()
        return [move.to_uci() for move in moves]
    
    def get_legal_moves_from_square(self, square_str: str) -> List[str]:
        """
        Get legal moves from a specific square.
        
        Args:
            square_str: Square in algebraic notation (e.g., 'e2')
        
        Returns:
            List of UCI move strings starting from that square
        """
        try:
            from_square = Square.from_algebraic(square_str)
        except ValueError:
            return []
        
        moves = self.game_state.get_legal_moves()
        return [move.to_uci() for move in moves if move.from_square == from_square]
    
    def make_move(self, move_str: str) -> bool:
        """
        Make a move (UCI notation).
        
        Args:
            move_str: Move in UCI notation (e.g., 'e2e4', 'e7e8q')
        
        Returns:
            True if move was legal and made, False otherwise
        """
        try:
            move = Move.from_uci(move_str)
        except ValueError:
            return False
        
        # Check if move is legal
        if not self.game_state.is_legal_move(move):
            return False
        
        # Store algebraic notation for move list
        algebraic = move.to_algebraic(self.board)
        
        # Make the move
        self.board.make_move(move)
        
        # Update move list with proper notation
        if self.board.active_color == 'white':
            # Black just moved
            self.move_list.append(algebraic)
        else:
            # White just moved
            self.move_list.append(algebraic)
        
        return True
    
    def get_engine_move(self, time_ms: int = 2000) -> Optional[str]:
        """
        Get engine's best move.
        
        Args:
            time_ms: Time limit in milliseconds
        
        Returns:
            Move in UCI notation, or None if no legal moves
        """
        legal_moves = self.game_state.get_legal_moves()
        if not legal_moves:
            return None
        
        best_move = self.engine.get_best_move(self.game_state, time_ms)
        if best_move:
            return best_move.to_uci()
        return None
    
    def is_human_turn(self) -> bool:
        """
        Check if it's the human player's turn.
        
        Returns:
            True if human should move
        """
        return self.board.active_color == self.human_color
    
    def get_game_status(self) -> Dict[str, Any]:
        """
        Get current game status.
        
        Returns:
            Dictionary with game state information
        """
        result = self.game_state.get_game_result()
        
        status = {
            'fen': self.board.to_fen(),
            'active_color': self.board.active_color,
            'human_color': self.human_color,
            'is_human_turn': self.is_human_turn(),
            'is_check': self.game_state.is_check(),
            'is_checkmate': self.game_state.is_checkmate(),
            'is_stalemate': self.game_state.is_stalemate(),
            'is_draw': self.game_state.is_draw(),
            'result': result,
            'legal_moves': self.get_legal_moves(),
            'move_list': self.move_list,
            'elo_rating': self.elo_rating,
            'halfmove_clock': self.board.halfmove_clock,
            'fullmove_number': self.board.fullmove_number,
        }
        
        # Add status message
        if result:
            if result == '1-0':
                status['message'] = 'White wins!'
            elif result == '0-1':
                status['message'] = 'Black wins!'
            else:
                status['message'] = 'Draw!'
        elif self.game_state.is_check():
            status['message'] = 'Check!'
        else:
            status['message'] = ''
        
        return status
    
    def get_board_array(self) -> List[List[Optional[str]]]:
        """
        Get board as 2D array of piece symbols.
        
        Returns:
            8x8 array where each cell is a piece symbol or None
        """
        board_array = []
        for rank in range(7, -1, -1):  # Start from rank 8
            row = []
            for file in range(8):
                piece = self.board.squares[rank][file]
                if piece:
                    # Use standard piece symbols
                    symbol = piece.piece_type[0].upper()
                    if piece.piece_type == 'knight':
                        symbol = 'N'
                    if piece.color == 'black':
                        symbol = symbol.lower()
                    row.append(symbol)
                else:
                    row.append(None)
            board_array.append(row)
        return board_array
    
    def resign(self) -> str:
        """
        Human player resigns.
        
        Returns:
            Game result string
        """
        if self.human_color == 'white':
            return '0-1'
        else:
            return '1-0'
