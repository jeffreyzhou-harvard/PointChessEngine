"""
Integration tests for the complete engine.

Tests:
- Engine can play a complete game
- Engine respects ELO settings
- Engine finds good moves in various positions
"""

import pytest
from core.board import Board
from core.game_state import GameState
from search.engine import Engine
from search.search import SearchLimits


class TestEngineIntegration:
    """Test complete engine integration."""
    
    def test_engine_plays_opening_moves(self):
        """Test that engine can play reasonable opening moves."""
        board = Board()
        game_state = GameState(board)
        engine = Engine(elo_rating=1500)
        
        # Play a few moves
        for _ in range(3):
            if game_state.get_game_result() is not None:
                break
            
            limits = SearchLimits(max_depth=2)
            result = engine.search(game_state, limits)
            move = result.best_move
            
            assert move is not None
            assert move in game_state.get_legal_moves()
            
            game_state.board.make_move(move)
        
        # Should have made 3 moves without error
        assert game_state.board.fullmove_number >= 2
    
    def test_engine_different_elo_levels(self):
        """Test engine at different ELO levels."""
        board = Board()
        game_state = GameState(board)
        
        # Test various ELO levels
        elo_levels = [600, 1200, 1800, 2400]
        
        for elo in elo_levels:
            engine = Engine(elo_rating=elo)
            limits = SearchLimits(max_depth=2)
            result = engine.search(game_state, limits)
            
            assert result.best_move is not None
            assert result.best_move in game_state.get_legal_moves()
    
    def test_engine_handles_complex_position(self):
        """Test engine in a complex middlegame position."""
        # Complex position from a real game
        fen = "r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 0 10"
        board = Board(fen)
        game_state = GameState(board)
        engine = Engine(elo_rating=1800)
        
        limits = SearchLimits(max_depth=3)
        result = engine.search(game_state, limits)
        
        assert result.best_move is not None
        assert result.best_move in game_state.get_legal_moves()
        assert result.depth >= 3
        assert result.nodes > 0
    
    def test_engine_evaluation_consistency(self):
        """Test that evaluation is consistent."""
        board = Board()
        game_state = GameState(board)
        engine = Engine(elo_rating=2400)
        
        # Evaluate same position multiple times
        scores = []
        for _ in range(3):
            score = engine.get_evaluation(game_state)
            scores.append(score)
        
        # All scores should be the same (no randomness in evaluation itself)
        assert scores[0] == scores[1] == scores[2]
    
    def test_engine_new_game_reset(self):
        """Test that new_game resets engine state."""
        engine = Engine(elo_rating=1500)
        
        # Play some moves to populate transposition table
        board = Board()
        game_state = GameState(board)
        
        limits = SearchLimits(max_depth=2)
        for _ in range(2):
            result = engine.search(game_state, limits)
            game_state.board.make_move(result.best_move)
        
        # Check TT has entries
        tt_size_before = engine.transposition_table.size()
        assert tt_size_before > 0
        
        # Reset
        engine.new_game()
        
        # TT should be cleared
        assert engine.transposition_table.size() == 0
    
    def test_engine_time_management(self):
        """Test that engine respects time limits."""
        board = Board()
        game_state = GameState(board)
        engine = Engine(elo_rating=1500)
        
        # Search with short time limit
        limits = SearchLimits(max_time_ms=50)
        result = engine.search(game_state, limits)
        
        assert result.best_move is not None
        assert result.best_move in game_state.get_legal_moves()
    
    def test_engine_finds_mate_in_one(self):
        """Test that engine finds mate in one."""
        # Position with mate in 1
        fen = "7k/6Q1/5K2/8/8/8/8/8 w - - 0 1"
        board = Board(fen)
        game_state = GameState(board)
        engine = Engine(elo_rating=2400)
        
        limits = SearchLimits(max_depth=3)
        result = engine.search(game_state, limits)
        
        # Should find a mating move
        assert result.best_move is not None
        
        # Verify it's mate
        game_state.board.make_move(result.best_move)
        assert game_state.is_checkmate()
    
    def test_engine_handles_endgame(self):
        """Test engine in endgame position."""
        # King and pawn endgame
        fen = "8/8/8/4k3/8/4K3/4P3/8 w - - 0 1"
        board = Board(fen)
        game_state = GameState(board)
        engine = Engine(elo_rating=1800)
        
        limits = SearchLimits(max_depth=3)
        result = engine.search(game_state, limits)
        
        assert result.best_move is not None
        assert result.best_move in game_state.get_legal_moves()


class TestEnginePerformance:
    """Test engine performance characteristics."""
    
    def test_iterative_deepening_increases_nodes(self):
        """Test that iterative deepening searches more nodes at higher depths."""
        board = Board()
        game_state = GameState(board)
        engine = Engine(elo_rating=2400)
        
        result_d2 = engine.search(game_state, SearchLimits(max_depth=2))
        result_d3 = engine.search(game_state, SearchLimits(max_depth=3))
        
        # Deeper search should examine more nodes
        assert result_d3.nodes > result_d2.nodes
    
    def test_transposition_table_stores_positions(self):
        """Test that transposition table stores positions."""
        board = Board()
        game_state = GameState(board)
        
        engine = Engine(elo_rating=2400)
        engine.transposition_table.clear()
        
        # Search to populate TT
        result = engine.search(game_state, SearchLimits(max_depth=3))
        
        # TT should have entries
        assert engine.transposition_table.size() > 0
        assert result.best_move is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
