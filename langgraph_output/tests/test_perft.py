"""
Perft (performance test) for move generation validation.

Perft counts the number of leaf nodes at a given depth in the move tree.
This is used to validate move generation correctness by comparing against
known values.

Test coverage:
- Starting position perft
- Complex positions perft
- Special move positions (castling, en passant, promotion)
"""

import pytest
from core import Board, GameState


def perft(game_state: GameState, depth: int) -> int:
    """
    Count leaf nodes at given depth.
    
    Args:
        game_state: Current game state
        depth: Depth to search
    
    Returns:
        Number of leaf nodes
    """
    if depth == 0:
        return 1
    
    moves = game_state.get_legal_moves()
    if depth == 1:
        return len(moves)
    
    count = 0
    for move in moves:
        game_state.board.make_move(move)
        count += perft(game_state, depth - 1)
        game_state.board.unmake_move(move)
    
    return count


def perft_divide(game_state: GameState, depth: int) -> dict:
    """
    Perft with move breakdown (for debugging).
    
    Args:
        game_state: Current game state
        depth: Depth to search
    
    Returns:
        Dictionary mapping moves to node counts
    """
    moves = game_state.get_legal_moves()
    results = {}
    
    for move in moves:
        game_state.board.make_move(move)
        count = perft(game_state, depth - 1)
        game_state.board.unmake_move(move)
        results[move.to_uci()] = count
    
    return results


class TestPerftStartingPosition:
    """Test perft from starting position."""
    
    def test_perft_depth_1(self):
        """Test perft depth 1 from starting position."""
        board = Board()
        game_state = GameState(board)
        
        assert perft(game_state, 1) == 20
    
    def test_perft_depth_2(self):
        """Test perft depth 2 from starting position."""
        board = Board()
        game_state = GameState(board)
        
        assert perft(game_state, 2) == 400
    
    def test_perft_depth_3(self):
        """Test perft depth 3 from starting position."""
        board = Board()
        game_state = GameState(board)
        
        assert perft(game_state, 3) == 8902
    
    @pytest.mark.slow
    def test_perft_depth_4(self):
        """Test perft depth 4 from starting position (slow)."""
        board = Board()
        game_state = GameState(board)
        
        assert perft(game_state, 4) == 197281


class TestPerftPosition2:
    """Test perft from position 2 (Kiwipete)."""
    
    def test_perft_depth_1(self):
        """Test perft depth 1 from position 2."""
        board = Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        game_state = GameState(board)
        
        assert perft(game_state, 1) == 48
    
    def test_perft_depth_2(self):
        """Test perft depth 2 from position 2."""
        board = Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        game_state = GameState(board)
        
        assert perft(game_state, 2) == 2039
    
    @pytest.mark.slow
    def test_perft_depth_3(self):
        """Test perft depth 3 from position 2 (slow)."""
        board = Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        game_state = GameState(board)
        
        assert perft(game_state, 3) == 97862


class TestPerftPosition3:
    """Test perft from position 3."""
    
    def test_perft_depth_1(self):
        """Test perft depth 1 from position 3."""
        board = Board("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1")
        game_state = GameState(board)
        
        assert perft(game_state, 1) == 14
    
    def test_perft_depth_2(self):
        """Test perft depth 2 from position 3."""
        board = Board("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1")
        game_state = GameState(board)
        
        assert perft(game_state, 2) == 191
    
    def test_perft_depth_3(self):
        """Test perft depth 3 from position 3."""
        board = Board("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1")
        game_state = GameState(board)
        
        assert perft(game_state, 3) == 2812
    
    @pytest.mark.slow
    def test_perft_depth_4(self):
        """Test perft depth 4 from position 3 (slow)."""
        board = Board("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1")
        game_state = GameState(board)
        
        assert perft(game_state, 4) == 43238


class TestPerftPosition4:
    """Test perft from position 4 (castling)."""
    
    def test_perft_depth_1(self):
        """Test perft depth 1 from position 4."""
        board = Board("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1")
        game_state = GameState(board)
        
        assert perft(game_state, 1) == 6
    
    def test_perft_depth_2(self):
        """Test perft depth 2 from position 4."""
        board = Board("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1")
        game_state = GameState(board)
        
        assert perft(game_state, 2) == 264
    
    def test_perft_depth_3(self):
        """Test perft depth 3 from position 4."""
        board = Board("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1")
        game_state = GameState(board)
        
        assert perft(game_state, 3) == 9467


class TestPerftPosition5:
    """Test perft from position 5 (promotions)."""
    
    def test_perft_depth_1(self):
        """Test perft depth 1 from position 5."""
        board = Board("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8")
        game_state = GameState(board)
        
        assert perft(game_state, 1) == 44
    
    def test_perft_depth_2(self):
        """Test perft depth 2 from position 5."""
        board = Board("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8")
        game_state = GameState(board)
        
        assert perft(game_state, 2) == 1486
    
    @pytest.mark.slow
    def test_perft_depth_3(self):
        """Test perft depth 3 from position 5 (slow)."""
        board = Board("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8")
        game_state = GameState(board)
        
        assert perft(game_state, 3) == 62379


class TestPerftPosition6:
    """Test perft from position 6 (complex)."""
    
    def test_perft_depth_1(self):
        """Test perft depth 1 from position 6."""
        board = Board("r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10")
        game_state = GameState(board)
        
        assert perft(game_state, 1) == 46
    
    def test_perft_depth_2(self):
        """Test perft depth 2 from position 6."""
        board = Board("r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10")
        game_state = GameState(board)
        
        assert perft(game_state, 2) == 2079
    
    @pytest.mark.slow
    def test_perft_depth_3(self):
        """Test perft depth 3 from position 6 (slow)."""
        board = Board("r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10")
        game_state = GameState(board)
        
        assert perft(game_state, 3) == 89890


class TestPerftEnPassant:
    """Test perft with en passant positions."""
    
    def test_en_passant_capture(self):
        """Test perft with en passant capture available."""
        board = Board("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3")
        game_state = GameState(board)
        
        # Should include en passant capture
        assert perft(game_state, 1) == 31


class TestPerftCastling:
    """Test perft with castling positions."""
    
    def test_both_castling_available(self):
        """Test perft with both castling options available."""
        board = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        game_state = GameState(board)
        
        # Should include both castling moves
        assert perft(game_state, 1) == 26


class TestPerftPromotion:
    """Test perft with promotion positions."""
    
    def test_promotion_options(self):
        """Test perft with promotion available."""
        board = Board("n1n5/PPPk4/8/8/8/8/4Kppp/5N1N b - - 0 1")
        game_state = GameState(board)
        
        # Should include all promotion options
        assert perft(game_state, 1) == 24


# Helper function to run perft divide for debugging
def test_perft_divide_example():
    """Example of using perft_divide for debugging."""
    board = Board()
    game_state = GameState(board)
    
    results = perft_divide(game_state, 2)
    
    # Check a few known values
    assert results['e2e4'] == 20
    assert results['d2d4'] == 20
    assert results['g1f3'] == 20
