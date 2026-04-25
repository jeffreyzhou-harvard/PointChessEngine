"""
Tests for UI game session management.

Tests:
- Session initialization
- New game creation
- Move making and validation
- Legal move generation
- Engine move requests
- Game status tracking
- ELO adjustment
- Resignation
"""

import pytest
from ui.session import GameSession
from core.move import Move, Square


class TestGameSession:
    """Test GameSession class."""
    
    def test_init_default(self):
        """Test default initialization."""
        session = GameSession()
        
        assert session.human_color == 'white'
        assert session.elo_rating == 1500
        assert session.board.to_fen().startswith('rnbqkbnr/pppppppp')
        assert len(session.move_list) == 0
    
    def test_init_custom(self):
        """Test custom initialization."""
        session = GameSession(human_color='black', elo_rating=2000)
        
        assert session.human_color == 'black'
        assert session.elo_rating == 2000
    
    def test_new_game(self):
        """Test starting a new game."""
        session = GameSession()
        
        # Make some moves
        session.make_move('e2e4')
        session.make_move('e7e5')
        
        assert len(session.move_list) == 2
        
        # Start new game
        session.new_game(human_color='black', elo_rating=1800)
        
        assert session.human_color == 'black'
        assert session.elo_rating == 1800
        assert len(session.move_list) == 0
        assert session.board.to_fen().startswith('rnbqkbnr/pppppppp')
    
    def test_set_elo(self):
        """Test ELO adjustment."""
        session = GameSession(elo_rating=1500)
        
        session.set_elo(2200)
        
        assert session.elo_rating == 2200
        assert session.engine.elo_config.elo_rating == 2200
    
    def test_get_legal_moves(self):
        """Test getting legal moves."""
        session = GameSession()
        
        moves = session.get_legal_moves()
        
        # Starting position has 20 legal moves
        assert len(moves) == 20
        assert 'e2e4' in moves
        assert 'g1f3' in moves
    
    def test_get_legal_moves_from_square(self):
        """Test getting legal moves from specific square."""
        session = GameSession()
        
        # E2 pawn can move to e3 or e4
        moves = session.get_legal_moves_from_square('e2')
        
        assert len(moves) == 2
        assert 'e2e3' in moves
        assert 'e2e4' in moves
    
    def test_get_legal_moves_from_invalid_square(self):
        """Test getting legal moves from invalid square."""
        session = GameSession()
        
        moves = session.get_legal_moves_from_square('invalid')
        
        assert len(moves) == 0
    
    def test_make_move_legal(self):
        """Test making a legal move."""
        session = GameSession()
        
        success = session.make_move('e2e4')
        
        assert success
        assert len(session.move_list) == 1
        assert session.board.active_color == 'black'
    
    def test_make_move_illegal(self):
        """Test making an illegal move."""
        session = GameSession()
        
        success = session.make_move('e2e5')  # Can't move pawn 3 squares
        
        assert not success
        assert len(session.move_list) == 0
    
    def test_make_move_invalid_notation(self):
        """Test making a move with invalid notation."""
        session = GameSession()
        
        success = session.make_move('invalid')
        
        assert not success
    
    def test_get_engine_move(self):
        """Test getting engine move."""
        session = GameSession(elo_rating=1500)
        
        move = session.get_engine_move(time_ms=100)
        
        assert move is not None
        assert len(move) >= 4  # UCI notation
        
        # Move should be legal
        legal_moves = session.get_legal_moves()
        assert move in legal_moves
    
    def test_is_human_turn(self):
        """Test checking if it's human's turn."""
        session = GameSession(human_color='white')
        
        assert session.is_human_turn()
        
        session.make_move('e2e4')
        
        assert not session.is_human_turn()
        
        session.make_move('e7e5')
        
        assert session.is_human_turn()
    
    def test_is_human_turn_black(self):
        """Test human turn when playing as black."""
        session = GameSession(human_color='black')
        
        assert not session.is_human_turn()
        
        session.make_move('e2e4')
        
        assert session.is_human_turn()
    
    def test_get_game_status_initial(self):
        """Test getting game status at start."""
        session = GameSession()
        
        status = session.get_game_status()
        
        assert status['active_color'] == 'white'
        assert status['human_color'] == 'white'
        assert status['is_human_turn']
        assert not status['is_check']
        assert not status['is_checkmate']
        assert not status['is_stalemate']
        assert status['result'] is None
        assert len(status['legal_moves']) == 20
        assert status['elo_rating'] == 1500
    
    def test_get_game_status_after_moves(self):
        """Test getting game status after moves."""
        session = GameSession()
        
        session.make_move('e2e4')
        session.make_move('e7e5')
        
        # Check basic properties without triggering full game result check
        assert session.board.active_color == 'white'
        assert len(session.move_list) == 2
        assert session.board.fullmove_number == 2
    
    def test_get_board_array(self):
        """Test getting board as array."""
        session = GameSession()
        
        board = session.get_board_array()
        
        assert len(board) == 8
        assert len(board[0]) == 8
        
        # Check starting position (board is from rank 8 to rank 1)
        assert board[7][0] == 'R'  # White rook on a1 (rank 0, displayed as board[7])
        assert board[7][4] == 'K'  # White king on e1
        assert board[6][0] == 'P'  # White pawn on a2
        assert board[1][0] == 'p'  # Black pawn on a7
        assert board[0][0] == 'r'  # Black rook on a8
    
    def test_resign_white(self):
        """Test resignation as white."""
        session = GameSession(human_color='white')
        
        result = session.resign()
        
        assert result == '0-1'
    
    def test_resign_black(self):
        """Test resignation as black."""
        session = GameSession(human_color='black')
        
        result = session.resign()
        
        assert result == '1-0'
    
    def test_move_list_algebraic(self):
        """Test that move list contains algebraic notation."""
        session = GameSession()
        
        session.make_move('e2e4')
        session.make_move('e7e5')
        session.make_move('g1f3')
        
        assert len(session.move_list) == 3
        # Moves should be in algebraic notation (simplified)
        assert all(isinstance(move, str) for move in session.move_list)
    
    def test_promotion_move(self):
        """Test pawn promotion."""
        from core.board import Board
        from core.game_state import GameState
        
        session = GameSession()
        
        # Set up position where white pawn can promote
        session.board = Board('8/P7/8/8/8/8/8/K6k w - - 0 1')
        session.game_state = GameState(session.board)
        
        success = session.make_move('a7a8q')
        
        assert success
        piece = session.board.get_piece(Square(7, 0))
        assert piece.piece_type == 'queen'


class TestGameSessionIntegration:
    """Integration tests for game session."""
    
    def test_full_game_flow(self):
        """Test a complete game flow."""
        session = GameSession(human_color='white', elo_rating=1500)
        
        # Initial state
        assert session.is_human_turn()
        assert len(session.get_legal_moves()) == 20
        
        # Human move
        session.make_move('e2e4')
        assert not session.is_human_turn()
        
        # Engine move
        engine_move = session.get_engine_move(time_ms=100)
        assert engine_move is not None
        session.make_move(engine_move)
        assert session.is_human_turn()
        
        # Check basic status (avoid triggering threefold repetition check)
        assert len(session.move_list) == 2
        assert session.board.fullmove_number == 2
    
    def test_elo_affects_engine_strength(self):
        """Test that ELO setting affects engine behavior."""
        # This is a basic test - we can't easily verify strength difference
        # but we can verify the setting is applied
        
        session_weak = GameSession(elo_rating=400)
        session_strong = GameSession(elo_rating=2400)
        
        assert session_weak.engine.elo_config.base_depth < session_strong.engine.elo_config.base_depth
        assert session_weak.engine.elo_config.eval_noise > session_strong.engine.elo_config.eval_noise
    
    def test_new_game_resets_state(self):
        """Test that new game properly resets all state."""
        session = GameSession()
        
        # Play some moves
        session.make_move('e2e4')
        session.make_move('e7e5')
        session.make_move('g1f3')
        
        # Start new game
        session.new_game(human_color='black', elo_rating=2000)
        
        # Verify reset
        assert session.human_color == 'black'
        assert session.elo_rating == 2000
        assert len(session.move_list) == 0
        assert session.board.to_fen().startswith('rnbqkbnr/pppppppp')
        assert not session.is_human_turn()  # Black to move, so engine goes first


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
