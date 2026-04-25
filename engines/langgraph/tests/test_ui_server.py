"""
Tests for UI HTTP server and API endpoints.

Simplified tests that avoid complex threading issues.
"""

import pytest
from ui.session import GameSession


class TestGameSessionViaAPI:
    """Test game session functionality (simulates API usage)."""
    
    def test_session_lifecycle(self):
        """Test complete session lifecycle."""
        # Create session
        session = GameSession(human_color='white', elo_rating=1500)
        
        # Get initial status
        status = session.get_game_status()
        assert status['human_color'] == 'white'
        assert status['is_human_turn']
        assert len(status['legal_moves']) == 20
        
        # Make human move
        success = session.make_move('e2e4')
        assert success
        
        # Get engine move
        engine_move = session.get_engine_move(time_ms=100)
        assert engine_move is not None
        
        # Make engine move
        success = session.make_move(engine_move)
        assert success
        
        # Verify state
        assert len(session.move_list) == 2
    
    def test_new_game_api_flow(self):
        """Test new game flow."""
        session = GameSession()
        
        # Play some moves
        session.make_move('e2e4')
        session.make_move('e7e5')
        
        # Start new game
        session.new_game(human_color='black', elo_rating=2000)
        
        status = session.get_game_status()
        assert status['human_color'] == 'black'
        assert status['elo_rating'] == 2000
        assert len(status['move_list']) == 0
    
    def test_elo_adjustment_api_flow(self):
        """Test ELO adjustment flow."""
        session = GameSession(elo_rating=1500)
        
        # Adjust ELO
        session.set_elo(1800)
        
        status = session.get_game_status()
        assert status['elo_rating'] == 1800
    
    def test_legal_moves_api_flow(self):
        """Test legal moves retrieval."""
        session = GameSession()
        
        # Get all legal moves
        moves = session.get_legal_moves()
        assert len(moves) == 20
        
        # Get moves from specific square
        moves_from_e2 = session.get_legal_moves_from_square('e2')
        assert len(moves_from_e2) == 2
        assert 'e2e4' in moves_from_e2
    
    def test_resign_api_flow(self):
        """Test resignation flow."""
        session = GameSession(human_color='white')
        
        result = session.resign()
        assert result == '0-1'
    
    def test_board_array_api_flow(self):
        """Test board array retrieval."""
        session = GameSession()
        
        board = session.get_board_array()
        assert len(board) == 8
        assert all(len(row) == 8 for row in board)
    
    def test_invalid_move_api_flow(self):
        """Test invalid move handling."""
        session = GameSession()
        
        success = session.make_move('e2e5')
        assert not success
        
        success = session.make_move('invalid')
        assert not success
    
    def test_promotion_api_flow(self):
        """Test pawn promotion."""
        from core.board import Board
        from core.game_state import GameState
        
        session = GameSession()
        session.board = Board('8/P7/8/8/8/8/8/K6k w - - 0 1')
        session.game_state = GameState(session.board)
        
        success = session.make_move('a7a8q')
        assert success


class TestAPIDataFormats:
    """Test API data format expectations."""
    
    def test_status_format(self):
        """Test game status format."""
        session = GameSession()
        status = session.get_game_status()
        
        # Check required fields
        required_fields = [
            'fen', 'active_color', 'human_color', 'is_human_turn',
            'is_check', 'is_checkmate', 'is_stalemate', 'is_draw',
            'result', 'legal_moves', 'move_list', 'elo_rating',
            'halfmove_clock', 'fullmove_number', 'message'
        ]
        
        for field in required_fields:
            assert field in status
    
    def test_board_array_format(self):
        """Test board array format."""
        session = GameSession()
        board = session.get_board_array()
        
        # Should be 8x8
        assert len(board) == 8
        assert all(len(row) == 8 for row in board)
        
        # Should contain piece symbols or None
        for row in board:
            for cell in row:
                assert cell is None or isinstance(cell, str)
    
    def test_legal_moves_format(self):
        """Test legal moves format."""
        session = GameSession()
        moves = session.get_legal_moves()
        
        # Should be list of UCI strings
        assert isinstance(moves, list)
        assert all(isinstance(move, str) for move in moves)
        assert all(len(move) >= 4 for move in moves)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
