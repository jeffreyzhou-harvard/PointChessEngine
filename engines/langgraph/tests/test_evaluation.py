"""
Tests for position evaluation.

Tests:
- Material evaluation
- Piece-square tables
- King safety
- Pawn structure
- Center control
"""

import pytest
from core.board import Board
from core.game_state import GameState
from search.evaluation import Evaluator


class TestEvaluation:
    """Test position evaluation."""
    
    def test_starting_position_near_equal(self):
        """Starting position should be near 0 (equal)."""
        board = Board()
        evaluator = Evaluator()
        score = evaluator.evaluate(board)
        
        # Should be close to 0 (within 50 centipawns)
        assert abs(score) < 50
    
    def test_material_advantage(self):
        """Test material evaluation."""
        # White up a queen (black missing queen)
        board = Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        evaluator = Evaluator()
        score = evaluator.evaluate_material(board)
        
        # White should be up ~900 centipawns (queen value)
        assert score > 800
    
    def test_black_material_advantage(self):
        """Test black material advantage."""
        # Black up a rook (white missing rook)
        board = Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/1NBQKBNR w Kkq - 0 1")
        evaluator = Evaluator()
        score = evaluator.evaluate_material(board)
        
        # Black should be up ~500 centipawns (rook value)
        assert score < -400
    
    def test_piece_square_tables(self):
        """Test piece-square table evaluation."""
        evaluator = Evaluator()
        
        # Knight in center vs knight on edge
        center_knight = Board("rnbqkbnr/pppppppp/8/8/4N3/8/PPPPPPPP/RNBQKB1R w KQkq - 0 1")
        edge_knight = Board("Nnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/R1BQKBNR w KQkq - 0 1")
        
        center_score = evaluator.evaluate_piece_square(center_knight)
        edge_score = evaluator.evaluate_piece_square(edge_knight)
        
        # Center knight should score higher
        assert center_score > edge_score
    
    def test_pawn_structure_doubled_pawns(self):
        """Test doubled pawns penalty."""
        evaluator = Evaluator()
        
        # Normal pawns
        normal = Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        
        # Doubled pawns for white
        doubled = Board("rnbqkbnr/pppppppp/8/8/8/4P3/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        
        normal_score = evaluator.evaluate_pawn_structure(normal)
        doubled_score = evaluator.evaluate_pawn_structure(doubled)
        
        # Doubled pawns should score worse
        assert doubled_score < normal_score
    
    def test_center_control(self):
        """Test center control evaluation."""
        evaluator = Evaluator()
        
        # Pieces in center
        center = Board("rnbqkbnr/pppppppp/8/8/3NN3/8/PPPPPPPP/R1BQKB1R w KQkq - 0 1")
        
        # Pieces on edge
        edge = Board("Nnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/R1BQKB1R w KQkq - 0 1")
        
        center_score = evaluator.evaluate_center_control(center)
        edge_score = evaluator.evaluate_center_control(edge)
        
        # Center control should score higher
        assert center_score > edge_score
    
    def test_king_safety(self):
        """Test king safety evaluation."""
        evaluator = Evaluator()
        
        # King with pawn shield
        safe = Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        
        # King without pawn shield (moved pawns)
        exposed = Board("rnbqkbnr/pppppppp/8/8/8/5PPP/PPPPP3/RNBQKBNR w KQkq - 0 1")
        
        safe_score = evaluator.evaluate_king_safety(safe)
        exposed_score = evaluator.evaluate_king_safety(exposed)
        
        # Safe king should score better
        assert safe_score > exposed_score
    
    def test_evaluation_symmetry(self):
        """Test that evaluation is symmetric for flipped positions."""
        evaluator = Evaluator()
        
        # Position with white advantage
        white_adv = Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
        score_white = evaluator.evaluate(white_adv)
        
        # Flipped position (black advantage)
        black_adv = Board("rnbqkbnr/pppp1ppp/8/4p3/8/8/PPPPPPPP/RNBQKBNR w KQkq e6 0 1")
        score_black = evaluator.evaluate(black_adv)
        
        # Scores should be roughly opposite (within some tolerance for asymmetry)
        # Note: Perfect symmetry is hard due to piece-square tables
        assert abs(score_white + score_black) < 100


class TestEvaluationEdgeCases:
    """Test evaluation edge cases."""
    
    def test_empty_board_except_kings(self):
        """Test evaluation with only kings."""
        board = Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        evaluator = Evaluator()
        score = evaluator.evaluate(board)
        
        # Should be close to 0
        assert abs(score) < 100
    
    def test_endgame_king_position(self):
        """Test king position in endgame."""
        evaluator = Evaluator()
        
        # King in center (endgame)
        center_king = Board("8/8/8/3k4/3K4/8/8/8 w - - 0 1")
        
        # King on edge (endgame)
        edge_king = Board("k7/8/8/8/8/8/8/K7 w - - 0 1")
        
        center_score = evaluator.evaluate(center_king)
        edge_score = evaluator.evaluate(edge_king)
        
        # In endgame, centralized king is better
        # This tests that endgame piece-square tables are used
        assert abs(center_score) < abs(edge_score) + 50  # Some tolerance


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
