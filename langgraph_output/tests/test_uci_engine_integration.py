"""
Integration tests for UCI protocol with the chess engine.

Tests the complete integration between UCI protocol, game state, and engine.
"""

import pytest
import time

from uci.protocol import UCIProtocol
from core.move import Move


class TestUCIEngineIntegration:
    """Test UCI protocol integration with engine."""
    
    def test_engine_finds_best_move(self):
        """Test that engine finds reasonable moves."""
        protocol = UCIProtocol()
        protocol.handle_command("position startpos")
        protocol.handle_command("go depth 4")
        
        # Wait for search
        if protocol.search_thread:
            protocol.search_thread.join(timeout=15.0)
        
        # Verify search completed
        assert not protocol.search_thread.is_alive()
    
    def test_engine_respects_elo_setting(self):
        """Test that ELO setting affects engine behavior."""
        protocol = UCIProtocol()
        
        # Set low ELO
        protocol.handle_command("setoption name ELO value 600")
        assert protocol.engine.elo_config.elo_rating == 600
        assert protocol.engine.elo_config.base_depth < 5
        
        # Set high ELO
        protocol.handle_command("setoption name ELO value 2200")
        assert protocol.engine.elo_config.elo_rating == 2200
        assert protocol.engine.elo_config.base_depth > 5
    
    def test_position_with_complex_fen(self):
        """Test setting complex positions via FEN."""
        protocol = UCIProtocol()
        
        # Sicilian Defense position
        fen = "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2"
        protocol.handle_command(f"position fen {fen}")
        
        # Verify position was set correctly
        assert protocol.board.to_fen() == fen
        
        # Engine should be able to search this position
        protocol.handle_command("go depth 3")
        if protocol.search_thread:
            protocol.search_thread.join(timeout=10.0)
        
        assert not protocol.search_thread.is_alive()
    
    def test_engine_handles_endgame(self):
        """Test engine in endgame position."""
        protocol = UCIProtocol()
        
        # King and pawn endgame
        fen = "8/8/8/4k3/8/8/4P3/4K3 w - - 0 1"
        protocol.handle_command(f"position fen {fen}")
        protocol.handle_command("go depth 5")
        
        if protocol.search_thread:
            protocol.search_thread.join(timeout=15.0)
        
        assert not protocol.search_thread.is_alive()
    
    def test_engine_handles_tactical_position(self):
        """Test engine in tactical position."""
        protocol = UCIProtocol()
        
        # Position with tactical opportunities
        fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1"
        protocol.handle_command(f"position fen {fen}")
        protocol.handle_command("go depth 3")
        
        if protocol.search_thread:
            protocol.search_thread.join(timeout=15.0)
        
        assert not protocol.search_thread.is_alive()
    
    def test_multiple_positions_in_sequence(self):
        """Test handling multiple positions in sequence."""
        protocol = UCIProtocol()
        
        positions = [
            "position startpos",
            "position startpos moves e2e4",
            "position startpos moves e2e4 e7e5",
            "position startpos moves e2e4 e7e5 g1f3",
        ]
        
        for pos_cmd in positions:
            protocol.handle_command(pos_cmd)
            protocol.handle_command("go depth 2")
            
            if protocol.search_thread:
                protocol.search_thread.join(timeout=10.0)
            
            assert not protocol.search_thread.is_alive()
    
    def test_engine_with_castling_rights(self):
        """Test engine handles castling correctly."""
        protocol = UCIProtocol()
        
        # Position where castling is available
        fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1"
        protocol.handle_command(f"position fen {fen}")
        
        # Verify castling rights
        assert protocol.board.castling_rights['K']
        assert protocol.board.castling_rights['Q']
        assert protocol.board.castling_rights['k']
        assert protocol.board.castling_rights['q']
        
        protocol.handle_command("go depth 2")
        if protocol.search_thread:
            protocol.search_thread.join(timeout=10.0)
        
        assert not protocol.search_thread.is_alive()
    
    def test_engine_with_en_passant(self):
        """Test engine handles en passant correctly."""
        protocol = UCIProtocol()
        
        # Set up position with en passant opportunity
        protocol.handle_command("position startpos moves e2e4 a7a6 e4e5 d7d5")
        
        # Verify en passant target is set
        assert protocol.board.en_passant_target is not None
        
        protocol.handle_command("go depth 2")
        if protocol.search_thread:
            protocol.search_thread.join(timeout=10.0)
        
        assert not protocol.search_thread.is_alive()
    
    def test_engine_with_promotion(self):
        """Test engine handles pawn promotion."""
        protocol = UCIProtocol()
        
        # Position where white can promote
        fen = "8/4P3/8/8/8/8/8/4K2k w - - 0 1"
        protocol.handle_command(f"position fen {fen}")
        protocol.handle_command("go depth 4")
        
        if protocol.search_thread:
            protocol.search_thread.join(timeout=10.0)
        
        assert not protocol.search_thread.is_alive()
    
    def test_time_management(self):
        """Test engine respects time limits."""
        protocol = UCIProtocol()
        protocol.handle_command("position startpos")
        
        # Search with short time limit
        start_time = time.time()
        protocol.handle_command("go movetime 500")
        
        if protocol.search_thread:
            protocol.search_thread.join(timeout=3.0)
        
        elapsed = time.time() - start_time
        
        # Should complete within reasonable time (allow overhead)
        assert elapsed < 2.0
        assert not protocol.search_thread.is_alive()
    
    def test_depth_limited_search(self):
        """Test engine respects depth limits."""
        protocol = UCIProtocol()
        protocol.handle_command("position startpos")
        
        # Search to shallow depth should be fast
        start_time = time.time()
        protocol.handle_command("go depth 1")
        
        if protocol.search_thread:
            protocol.search_thread.join(timeout=5.0)
        
        elapsed = time.time() - start_time
        
        # Shallow search should be quick
        assert elapsed < 3.0
        assert not protocol.search_thread.is_alive()


class TestUCIStressTest:
    """Stress tests for UCI protocol."""
    
    def test_rapid_commands(self):
        """Test handling rapid command sequences."""
        protocol = UCIProtocol()
        
        for _ in range(5):
            protocol.handle_command("position startpos")
            protocol.handle_command("go depth 1")
            
            if protocol.search_thread:
                protocol.search_thread.join(timeout=2.0)
    
    def test_alternating_positions(self):
        """Test alternating between different positions."""
        protocol = UCIProtocol()
        
        positions = [
            "position startpos",
            "position fen rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "position startpos moves e2e4 e7e5",
        ]
        
        for pos in positions:
            protocol.handle_command(pos)
            protocol.handle_command("go depth 2")
            
            if protocol.search_thread:
                protocol.search_thread.join(timeout=5.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
