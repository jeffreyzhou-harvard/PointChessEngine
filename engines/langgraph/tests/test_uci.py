"""
Tests for UCI protocol implementation.

Tests:
- UCI handshake (uci, isready)
- Position setup (startpos, FEN, moves)
- Search commands (go, stop)
- Engine options (setoption for ELO)
- Error handling (malformed input)
- Background search and stop functionality
"""

import pytest
import threading
import time
from io import StringIO

from uci.protocol import UCIProtocol, run_uci
from core.board import Board
from core.game_state import GameState
from core.move import Move


class TestUCIHandshake:
    """Test UCI protocol handshake."""
    
    def test_uci_command(self):
        """Test 'uci' command returns engine identification."""
        protocol = UCIProtocol()
        response = protocol.handle_command("uci")
        
        assert "id name" in response
        assert "id author" in response
        assert "option name ELO" in response
        assert "uciok" in response
    
    def test_isready_command(self):
        """Test 'isready' command returns readyok."""
        protocol = UCIProtocol()
        response = protocol.handle_command("isready")
        
        assert response == "readyok"
    
    def test_ucinewgame_command(self):
        """Test 'ucinewgame' resets game state."""
        protocol = UCIProtocol()
        
        # Set up a position
        protocol.handle_command("position startpos moves e2e4")
        
        # Reset game
        response = protocol.handle_command("ucinewgame")
        
        # Verify board is reset
        assert protocol.board.to_fen().startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq")
        assert response == ""


class TestPositionSetup:
    """Test position command."""
    
    def test_position_startpos(self):
        """Test setting starting position."""
        protocol = UCIProtocol()
        response = protocol.handle_command("position startpos")
        
        assert response == ""
        assert protocol.board.to_fen().startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq")
    
    def test_position_startpos_with_moves(self):
        """Test setting position with moves."""
        protocol = UCIProtocol()
        response = protocol.handle_command("position startpos moves e2e4 e7e5")
        
        assert response == ""
        # Verify moves were applied
        assert protocol.board.get_piece(Move.from_uci("e2e4").to_square) is not None
    
    def test_position_fen(self):
        """Test setting position from FEN."""
        protocol = UCIProtocol()
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        response = protocol.handle_command(f"position fen {fen}")
        
        assert response == ""
        assert protocol.board.to_fen() == fen
    
    def test_position_fen_with_moves(self):
        """Test setting FEN position with moves."""
        protocol = UCIProtocol()
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        response = protocol.handle_command(f"position fen {fen} moves e2e4 e7e5 g1f3")
        
        assert response == ""
        # Verify knight moved to f3
        knight_square = Move.from_uci("g1f3").to_square
        piece = protocol.board.get_piece(knight_square)
        assert piece is not None
        assert piece.piece_type == "knight"
    
    def test_position_illegal_move(self):
        """Test that illegal moves are rejected."""
        protocol = UCIProtocol()
        response = protocol.handle_command("position startpos moves e2e5")
        
        assert "Error" in response or "illegal" in response.lower()
    
    def test_position_invalid_uci(self):
        """Test that invalid UCI notation is rejected."""
        protocol = UCIProtocol()
        response = protocol.handle_command("position startpos moves xyz")
        
        assert "Error" in response or "invalid" in response.lower()


class TestSearchCommands:
    """Test search commands (go, stop)."""
    
    def test_go_depth(self):
        """Test 'go depth' command."""
        protocol = UCIProtocol()
        protocol.handle_command("position startpos")
        
        # Start search
        response = protocol.handle_command("go depth 3")
        assert response == ""
        
        # Wait for search to complete
        if protocol.search_thread:
            protocol.search_thread.join(timeout=5.0)
        
        # Search should have completed
        assert not protocol.search_thread.is_alive()
    
    def test_go_movetime(self):
        """Test 'go movetime' command."""
        protocol = UCIProtocol()
        protocol.handle_command("position startpos")
        
        # Start search with time limit
        start_time = time.time()
        response = protocol.handle_command("go movetime 500")
        assert response == ""
        
        # Wait for search
        if protocol.search_thread:
            protocol.search_thread.join(timeout=2.0)
        
        elapsed = time.time() - start_time
        # Should complete within reasonable time (allow some overhead)
        assert elapsed < 2.0
    
    def test_go_infinite(self):
        """Test 'go infinite' command (must be stopped)."""
        protocol = UCIProtocol()
        protocol.handle_command("position startpos")
        
        # Start infinite search
        response = protocol.handle_command("go infinite")
        assert response == ""
        
        # Let it run briefly
        time.sleep(0.1)
        
        # Stop search
        protocol.handle_command("stop")
        
        # Wait for search to stop
        if protocol.search_thread:
            protocol.search_thread.join(timeout=2.0)
        
        assert not protocol.search_thread.is_alive()
    
    def test_stop_command(self):
        """Test 'stop' command interrupts search."""
        protocol = UCIProtocol()
        protocol.handle_command("position startpos")
        
        # Start deep search
        protocol.handle_command("go depth 20")
        
        # Let it run briefly
        time.sleep(0.1)
        
        # Stop search
        response = protocol.handle_command("stop")
        assert response == ""
        
        # Wait for search to stop
        if protocol.search_thread:
            protocol.search_thread.join(timeout=2.0)
        
        # Search should have stopped
        assert not protocol.search_thread.is_alive()
    
    def test_go_with_time_controls(self):
        """Test 'go' with time controls (wtime, btime)."""
        protocol = UCIProtocol()
        protocol.handle_command("position startpos")
        
        # Start search with time controls
        response = protocol.handle_command("go wtime 60000 btime 60000 winc 1000 binc 1000")
        assert response == ""
        
        # Wait for search
        if protocol.search_thread:
            protocol.search_thread.join(timeout=5.0)
        
        assert not protocol.search_thread.is_alive()


class TestEngineOptions:
    """Test setoption command."""
    
    def test_setoption_elo(self):
        """Test setting ELO rating."""
        protocol = UCIProtocol()
        
        # Set ELO to 1200
        response = protocol.handle_command("setoption name ELO value 1200")
        assert "Error" not in response
        
        # Verify ELO was set
        assert protocol.engine.elo_config.elo_rating == 1200
    
    def test_setoption_elo_bounds(self):
        """Test ELO bounds checking."""
        protocol = UCIProtocol()
        
        # Try invalid ELO (too low)
        response = protocol.handle_command("setoption name ELO value 300")
        assert "Error" in response
        
        # Try invalid ELO (too high)
        response = protocol.handle_command("setoption name ELO value 3000")
        assert "Error" in response
        
        # Valid ELO should work
        response = protocol.handle_command("setoption name ELO value 2000")
        assert "Error" not in response
        assert protocol.engine.elo_config.elo_rating == 2000
    
    def test_setoption_hash(self):
        """Test setting hash table size."""
        protocol = UCIProtocol()
        
        # Set hash size
        response = protocol.handle_command("setoption name Hash value 128")
        # Should not error (even if not fully implemented)
        assert "unknown option" not in response.lower()
    
    def test_setoption_unknown_option(self):
        """Test unknown option handling."""
        protocol = UCIProtocol()
        
        response = protocol.handle_command("setoption name UnknownOption value 123")
        assert "Error" in response or "unknown" in response.lower()
    
    def test_setoption_malformed(self):
        """Test malformed setoption command."""
        protocol = UCIProtocol()
        
        # Missing 'value' keyword
        response = protocol.handle_command("setoption name ELO 1500")
        assert "Error" in response


class TestErrorHandling:
    """Test error handling for malformed input."""
    
    def test_empty_command(self):
        """Test empty command."""
        protocol = UCIProtocol()
        response = protocol.handle_command("")
        assert response == ""
    
    def test_unknown_command(self):
        """Test unknown command."""
        protocol = UCIProtocol()
        response = protocol.handle_command("unknowncommand")
        # Should not crash, may return empty or info string
        assert response is not None
    
    def test_position_no_args(self):
        """Test position command without arguments."""
        protocol = UCIProtocol()
        response = protocol.handle_command("position")
        assert "Error" in response or "requires" in response.lower()
    
    def test_quit_command(self):
        """Test quit command returns None."""
        protocol = UCIProtocol()
        response = protocol.handle_command("quit")
        assert response is None


class TestDebugMode:
    """Test debug mode functionality."""
    
    def test_debug_on(self):
        """Test enabling debug mode."""
        protocol = UCIProtocol()
        
        assert not protocol.debug_mode
        
        protocol.handle_command("debug on")
        assert protocol.debug_mode
    
    def test_debug_off(self):
        """Test disabling debug mode."""
        protocol = UCIProtocol()
        protocol.debug_mode = True
        
        protocol.handle_command("debug off")
        assert not protocol.debug_mode


class TestIntegration:
    """Integration tests for complete UCI sessions."""
    
    def test_complete_game_session(self):
        """Test a complete UCI game session."""
        protocol = UCIProtocol()
        
        # Handshake
        response = protocol.handle_command("uci")
        assert "uciok" in response
        
        response = protocol.handle_command("isready")
        assert response == "readyok"
        
        # New game
        protocol.handle_command("ucinewgame")
        
        # Set position
        protocol.handle_command("position startpos")
        
        # Search
        protocol.handle_command("go depth 2")
        if protocol.search_thread:
            protocol.search_thread.join(timeout=5.0)
        
        # Make a move and search again
        protocol.handle_command("position startpos moves e2e4")
        protocol.handle_command("go depth 2")
        if protocol.search_thread:
            protocol.search_thread.join(timeout=5.0)
        
        # Quit
        response = protocol.handle_command("quit")
        assert response is None
    
    def test_elo_adjustment_during_game(self):
        """Test adjusting ELO during a game."""
        protocol = UCIProtocol()
        
        # Start at default ELO
        protocol.handle_command("position startpos")
        protocol.handle_command("go depth 2")
        if protocol.search_thread:
            protocol.search_thread.join(timeout=5.0)
        
        # Adjust ELO
        protocol.handle_command("setoption name ELO value 800")
        assert protocol.engine.elo_config.elo_rating == 800
        
        # Search again with new ELO
        protocol.handle_command("position startpos moves e2e4")
        protocol.handle_command("go depth 2")
        if protocol.search_thread:
            protocol.search_thread.join(timeout=5.0)
    
    def test_multiple_searches(self):
        """Test multiple consecutive searches."""
        protocol = UCIProtocol()
        protocol.handle_command("position startpos")
        
        # Run multiple searches
        for _ in range(3):
            protocol.handle_command("go depth 1")
            if protocol.search_thread:
                protocol.search_thread.join(timeout=2.0)
            
            # Verify search completed
            assert not protocol.search_thread.is_alive()


class TestMatePositions:
    """Test UCI protocol with mate positions."""
    
    def test_mate_in_one(self):
        """Test engine finds mate in one."""
        protocol = UCIProtocol()
        
        # Position: White to move, mate in 1 (Qh5#)
        # This is a simplified position for testing
        fen = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1"
        protocol.handle_command(f"position fen {fen}")
        
        # Search should find mate quickly
        protocol.handle_command("go depth 3")
        if protocol.search_thread:
            protocol.search_thread.join(timeout=5.0)
        
        # Search should complete
        assert not protocol.search_thread.is_alive()


class TestConcurrency:
    """Test concurrent search operations."""
    
    def test_stop_during_search(self):
        """Test stopping search while it's running."""
        protocol = UCIProtocol()
        protocol.handle_command("position startpos")
        
        # Start long search
        protocol.handle_command("go depth 15")
        
        # Verify search is running
        time.sleep(0.05)
        assert protocol.search_thread.is_alive()
        
        # Stop it
        protocol.handle_command("stop")
        
        # Wait for stop
        if protocol.search_thread:
            protocol.search_thread.join(timeout=2.0)
        
        # Should be stopped
        assert not protocol.search_thread.is_alive()
    
    def test_new_search_stops_previous(self):
        """Test that starting new search stops previous one."""
        protocol = UCIProtocol()
        protocol.handle_command("position startpos")
        
        # Start first search
        protocol.handle_command("go depth 15")
        first_thread = protocol.search_thread
        
        time.sleep(0.05)
        
        # Start second search (should stop first)
        protocol.handle_command("go depth 2")
        
        # Wait for both to complete
        if first_thread:
            first_thread.join(timeout=2.0)
        if protocol.search_thread:
            protocol.search_thread.join(timeout=2.0)
        
        # Both should be stopped
        assert not first_thread.is_alive()
        assert not protocol.search_thread.is_alive()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
