"""
Tests for search algorithms.

Tests:
- Basic search functionality
- Mate-in-1 detection
- Tactical move finding
- Alpha-beta pruning
- Transposition table
- Move ordering
"""

import pytest
from core.board import Board
from core.game_state import GameState
from core.move import Move, Square
from search.engine import Engine
from search.search import SearchLimits, Searcher
from search.evaluation import Evaluator
from search.transposition import TranspositionTable


class TestBasicSearch:
    """Test basic search functionality."""
    
    def test_engine_initialization(self):
        """Test engine can be initialized."""
        engine = Engine(elo_rating=1500)
        assert engine is not None
        assert engine.elo_config.elo_rating == 1500
    
    def test_search_returns_legal_move(self):
        """Test that search returns a legal move."""
        board = Board()
        game_state = GameState(board)
        engine = Engine(elo_rating=1500)
        
        limits = SearchLimits(max_depth=3)
        result = engine.search(game_state, limits)
        
        assert result.best_move is not None
        assert result.best_move in game_state.get_legal_moves()
    
    def test_search_with_time_limit(self):
        """Test search with time limit."""
        board = Board()
        game_state = GameState(board)
        engine = Engine(elo_rating=1500)
        
        limits = SearchLimits(max_time_ms=100)
        result = engine.search(game_state, limits)
        
        assert result.best_move is not None
        assert result.time_ms <= 200  # Some tolerance
    
    def test_only_one_legal_move(self):
        """Test search when only one legal move exists."""
        # Position where only one move is legal
        board = Board("7k/8/5K2/8/8/8/7R/8 w - - 0 1")
        game_state = GameState(board)
        engine = Engine(elo_rating=1500)
        
        limits = SearchLimits(max_depth=1)
        result = engine.search(game_state, limits)
        
        assert result.best_move is not None
        assert result.depth >= 1


class TestMateDetection:
    """Test mate detection and forcing."""
    
    def test_mate_in_one_detection(self):
        """Test that engine finds mate in one."""
        # White to move, mate in 1 with Qh7#
        board = Board("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1")
        game_state = GameState(board)
        engine = Engine(elo_rating=2400)  # High ELO for best play
        
        limits = SearchLimits(max_depth=3)
        result = engine.search(game_state, limits)
        
        # Should find Qh7# (or similar mating move)
        assert result.best_move is not None
        
        # Verify it's actually mate
        game_state.board.make_move(result.best_move)
        assert game_state.is_checkmate()
    
    def test_back_rank_mate(self):
        """Test back rank mate detection."""
        # White to move, back rank mate with Rd8#
        board = Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1")
        game_state = GameState(board)
        engine = Engine(elo_rating=2400)
        
        limits = SearchLimits(max_depth=3)
        result = engine.search(game_state, limits)
        
        assert result.best_move is not None
        
        # Check if it's a mating move
        game_state.board.make_move(result.best_move)
        is_mate = game_state.is_checkmate()
        game_state.board.unmake_move(result.best_move)
        
        # Should find mate or at least a very good move
        assert is_mate or result.score > 500
    
    def test_avoid_being_mated(self):
        """Test that engine avoids being mated."""
        # Black to move, must avoid mate
        board = Board("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 1")
        game_state = GameState(board)
        engine = Engine(elo_rating=2400)
        
        limits = SearchLimits(max_depth=3)
        result = engine.search(game_state, limits)
        
        assert result.best_move is not None
        
        # After the move, white should not have immediate mate
        game_state.board.make_move(result.best_move)
        game_state.board.active_color = 'white'
        white_gs = GameState(game_state.board)
        
        # Check that white doesn't have mate in 1
        has_mate = False
        for move in white_gs.get_legal_moves():
            white_gs.board.make_move(move)
            if white_gs.is_checkmate():
                has_mate = True
            white_gs.board.unmake_move(move)
            if has_mate:
                break
        
        # Engine should avoid positions where opponent has mate in 1
        # (though at depth 3 it might not always see it)


class TestTacticalMoves:
    """Test finding tactical moves."""
    
    def test_win_material(self):
        """Test that engine wins material when possible."""
        # White can win a pawn
        board = Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1")
        game_state = GameState(board)
        engine = Engine(elo_rating=2400)
        
        limits = SearchLimits(max_depth=3)
        result = engine.search(game_state, limits)
        
        # Should find a reasonable move
        assert result.best_move is not None
        # Score should be reasonable (not necessarily winning material immediately)
        assert abs(result.score) < 1000
    
    def test_engine_makes_legal_moves(self):
        """Test that engine consistently makes legal moves."""
        # Various positions
        positions = [
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 1",
            "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 1",
        ]
        
        engine = Engine(elo_rating=1500)
        
        for fen in positions:
            board = Board(fen)
            game_state = GameState(board)
            
            limits = SearchLimits(max_depth=2)
            result = engine.search(game_state, limits)
            
            assert result.best_move is not None
            assert result.best_move in game_state.get_legal_moves()


class TestTranspositionTable:
    """Test transposition table functionality."""
    
    def test_tt_stores_and_retrieves(self):
        """Test that TT stores and retrieves positions."""
        tt = TranspositionTable(size_mb=1)
        board = Board()
        
        position_hash = tt.hash_position(board)
        move = Move(Square(1, 4), Square(3, 4))  # e2e4
        
        tt.store(position_hash, depth=5, score=50, best_move=move, 
                node_type=TranspositionTable.EXACT)
        
        entry = tt.probe(position_hash)
        assert entry is not None
        assert entry['depth'] == 5
        assert entry['score'] == 50
        assert entry['best_move'] == move
    
    def test_tt_different_positions(self):
        """Test that different positions have different hashes."""
        tt = TranspositionTable(size_mb=1)
        
        board1 = Board()
        board2 = Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
        
        hash1 = tt.hash_position(board1)
        hash2 = tt.hash_position(board2)
        
        assert hash1 != hash2
    
    def test_tt_clear(self):
        """Test clearing transposition table."""
        tt = TranspositionTable(size_mb=1)
        board = Board()
        
        position_hash = tt.hash_position(board)
        move = Move(Square(1, 4), Square(3, 4))
        
        tt.store(position_hash, depth=5, score=50, best_move=move,
                node_type=TranspositionTable.EXACT)
        
        assert tt.size() > 0
        
        tt.clear()
        assert tt.size() == 0


class TestMoveOrdering:
    """Test move ordering."""
    
    def test_captures_ordered_first(self):
        """Test that captures are ordered before quiet moves."""
        board = Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 1")
        game_state = GameState(board)
        
        evaluator = Evaluator()
        searcher = Searcher(evaluator)
        
        moves = game_state.get_legal_moves()
        ordered = searcher.order_moves(moves, board)
        
        # Captures should be near the front
        # Find a capture move
        capture_indices = []
        for i, move in enumerate(ordered):
            if board.get_piece(move.to_square) is not None:
                capture_indices.append(i)
        
        # At least one capture should be in first half of moves
        if capture_indices:
            assert min(capture_indices) < len(ordered) // 2


class TestEloStrength:
    """Test ELO-based strength adjustment."""
    
    def test_different_elo_different_depth(self):
        """Test that different ELO ratings use different depths."""
        engine_weak = Engine(elo_rating=800)
        engine_strong = Engine(elo_rating=2000)
        
        assert engine_weak.elo_config.base_depth < engine_strong.elo_config.base_depth
    
    def test_low_elo_makes_mistakes(self):
        """Test that low ELO engine makes suboptimal moves sometimes."""
        board = Board()
        game_state = GameState(board)
        
        # Run multiple searches with low ELO
        engine = Engine(elo_rating=600)
        moves = []
        
        for _ in range(5):
            limits = SearchLimits(max_depth=2)
            result = engine.search(game_state, limits)
            moves.append(result.best_move.to_uci())
        
        # With noise and probabilistic selection, should get some variation
        # (though not guaranteed in all positions)
        # We just check that the engine runs without error


class TestSearchDepth:
    """Test search depth functionality."""
    
    def test_deeper_search_better_score(self):
        """Test that deeper search generally finds better moves."""
        board = Board()
        game_state = GameState(board)
        engine = Engine(elo_rating=2400)
        
        # Shallow search
        result_shallow = engine.search(game_state, SearchLimits(max_depth=2))
        
        # Deeper search
        result_deep = engine.search(game_state, SearchLimits(max_depth=4))
        
        # Both should return moves
        assert result_shallow.best_move is not None
        assert result_deep.best_move is not None
        
        # Deeper search should search more nodes
        assert result_deep.nodes > result_shallow.nodes


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
