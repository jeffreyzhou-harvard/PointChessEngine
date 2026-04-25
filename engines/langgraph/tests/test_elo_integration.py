"""
Integration tests for ELO system with engine.

Tests:
- Engine respects ELO configuration
- Different ELO levels produce different behavior
- ELO can be adjusted dynamically
"""

import pytest
from core.board import Board
from core.game_state import GameState
from search.engine import Engine
from search.search import SearchLimits


class TestEloEngineIntegration:
    """Test ELO integration with engine."""
    
    def test_engine_uses_elo_depth(self):
        """Test that engine uses depth from ELO config."""
        board = Board()
        game_state = GameState(board)
        
        # Low ELO should use shallow depth
        engine_low = Engine(elo_rating=400)
        assert engine_low.elo_config.base_depth == 1
        
        # High ELO should use deeper depth
        engine_high = Engine(elo_rating=2400)
        assert engine_high.elo_config.base_depth == 8
    
    def test_engine_elo_can_be_adjusted(self):
        """Test that engine ELO can be changed dynamically."""
        engine = Engine(elo_rating=1000)
        
        # Initial ELO
        assert engine.elo_config.elo_rating == 1000
        initial_depth = engine.elo_config.base_depth
        
        # Change ELO
        engine.set_elo(2000)
        assert engine.elo_config.elo_rating == 2000
        new_depth = engine.elo_config.base_depth
        
        # Depth should have increased
        assert new_depth > initial_depth
    
    def test_engine_plays_at_different_elo_levels(self):
        """Test that engine can play at different ELO levels."""
        board = Board()
        game_state = GameState(board)
        
        elo_levels = [400, 1000, 1600, 2400]
        
        for elo in elo_levels:
            engine = Engine(elo_rating=elo)
            limits = SearchLimits(max_depth=min(2, engine.elo_config.base_depth))
            
            result = engine.search(game_state, limits)
            
            # Should find a legal move
            assert result.best_move is not None
            assert result.best_move in game_state.get_legal_moves()
    
    def test_low_elo_adds_noise(self):
        """Test that low ELO adds noise to evaluation."""
        board = Board()
        game_state = GameState(board)
        
        # Low ELO should have noise
        engine_low = Engine(elo_rating=400)
        assert engine_low.elo_config.eval_noise > 0
        
        # High ELO should have no noise
        engine_high = Engine(elo_rating=2400)
        assert engine_high.elo_config.eval_noise == 0
    
    def test_engine_finds_mate_at_high_elo(self):
        """Test that high ELO engine finds mate (never blunders forced mate)."""
        # Position with mate in 1
        fen = "7k/6Q1/5K2/8/8/8/8/8 w - - 0 1"
        board = Board(fen)
        game_state = GameState(board)
        
        # Test at high ELO (should definitely find it)
        engine = Engine(elo_rating=2400)
        limits = SearchLimits(max_depth=2)
        result = engine.search(game_state, limits)
        
        # Should find a move
        assert result.best_move is not None
        
        # Verify it's mate
        game_state.board.make_move(result.best_move)
        is_mate = game_state.is_checkmate()
        game_state.board.unmake_move(result.best_move)
        
        # Should find mate (requirement: never blunder forced mate)
        assert is_mate, "High ELO failed to find mate in 1"
    
    def test_engine_get_best_move_respects_elo(self):
        """Test that get_best_move uses ELO configuration."""
        board = Board()
        game_state = GameState(board)
        
        # Low ELO
        engine_low = Engine(elo_rating=400)
        move_low = engine_low.get_best_move(game_state)
        assert move_low is not None
        assert move_low in game_state.get_legal_moves()
        
        # High ELO
        engine_high = Engine(elo_rating=2400)
        move_high = engine_high.get_best_move(game_state)
        assert move_high is not None
        assert move_high in game_state.get_legal_moves()
    
    def test_engine_time_multiplier_affects_search(self):
        """Test that time multiplier affects search time."""
        board = Board()
        game_state = GameState(board)
        
        # Low ELO has low time multiplier
        engine_low = Engine(elo_rating=400)
        assert engine_low.elo_config.time_multiplier == 0.1
        
        # High ELO has high time multiplier
        engine_high = Engine(elo_rating=2400)
        assert engine_high.elo_config.time_multiplier == 1.0
        
        # Both should still find moves
        move_low = engine_low.get_best_move(game_state, time_ms=100)
        move_high = engine_high.get_best_move(game_state, time_ms=100)
        
        assert move_low is not None
        assert move_high is not None


class TestEloConsistency:
    """Test ELO system consistency."""
    
    def test_same_elo_same_config(self):
        """Test that same ELO produces same configuration."""
        engine1 = Engine(elo_rating=1500)
        engine2 = Engine(elo_rating=1500)
        
        assert engine1.elo_config.base_depth == engine2.elo_config.base_depth
        assert engine1.elo_config.time_multiplier == engine2.elo_config.time_multiplier
        assert engine1.elo_config.eval_noise == engine2.elo_config.eval_noise
        assert engine1.elo_config.best_move_probability == engine2.elo_config.best_move_probability
    
    def test_elo_config_string_representation(self):
        """Test that ELO config has useful string representation."""
        engine = Engine(elo_rating=1500)
        
        config_str = str(engine.elo_config)
        
        # Should contain key information
        assert '1500' in config_str
        assert 'EloConfig' in config_str
    
    def test_engine_string_representation(self):
        """Test that engine has useful string representation."""
        engine = Engine(elo_rating=1500)
        
        engine_str = str(engine)
        
        # Should contain ELO information
        assert '1500' in engine_str
        assert 'Engine' in engine_str


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
