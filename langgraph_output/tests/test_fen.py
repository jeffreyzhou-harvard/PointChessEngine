"""
Tests for FEN parsing and generation.

Test coverage:
- FEN parsing
- FEN generation
- Edge cases and invalid FEN strings
"""

import pytest
from core import Board, Square, Piece


class TestFENParsing:
    """Test FEN parsing."""
    
    def test_starting_position(self):
        """Test parsing starting position FEN."""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        board = Board(fen)
        
        assert board.active_color == 'white'
        assert board.castling_rights == {'K': True, 'Q': True, 'k': True, 'q': True}
        assert board.en_passant_target is None
        assert board.halfmove_clock == 0
        assert board.fullmove_number == 1
    
    def test_complex_position(self):
        """Test parsing complex position."""
        fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        board = Board(fen)
        
        # Check some pieces
        assert board.get_piece(Square(7, 0)).piece_type == 'rook'
        assert board.get_piece(Square(7, 4)).piece_type == 'king'
        assert board.get_piece(Square(4, 4)).piece_type == 'pawn'
        assert board.get_piece(Square(4, 4)).color == 'white'
    
    def test_en_passant_target(self):
        """Test parsing en passant target."""
        fen = "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2"
        board = Board(fen)
        
        assert board.en_passant_target == Square(5, 3)
    
    def test_no_castling_rights(self):
        """Test parsing position with no castling rights."""
        fen = "r3k2r/8/8/8/8/8/8/R3K2R w - - 0 1"
        board = Board(fen)
        
        assert board.castling_rights == {'K': False, 'Q': False, 'k': False, 'q': False}
    
    def test_partial_castling_rights(self):
        """Test parsing position with partial castling rights."""
        fen = "r3k2r/8/8/8/8/8/8/R3K2R w Kq - 0 1"
        board = Board(fen)
        
        assert board.castling_rights == {'K': True, 'Q': False, 'k': False, 'q': True}
    
    def test_halfmove_clock(self):
        """Test parsing halfmove clock."""
        fen = "4k3/8/8/8/8/8/8/4K3 w - - 50 25"
        board = Board(fen)
        
        assert board.halfmove_clock == 50
        assert board.fullmove_number == 25


class TestFENGeneration:
    """Test FEN generation."""
    
    def test_generate_starting_position(self):
        """Test generating FEN for starting position."""
        board = Board()
        fen = board.to_fen()
        
        assert fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    def test_generate_after_move(self):
        """Test generating FEN after a move."""
        board = Board()
        from core import Move
        
        # e2-e4
        move = Move(Square(1, 4), Square(3, 4))
        board.make_move(move)
        
        fen = board.to_fen()
        assert fen == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    
    def test_generate_complex_position(self):
        """Test generating FEN for complex position."""
        fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        board = Board(fen)
        
        assert board.to_fen() == fen


class TestFENRoundTrip:
    """Test FEN round-trip (parse and generate)."""
    
    def test_round_trip_various_positions(self):
        """Test round-trip for various positions."""
        fens = [
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
            "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
            "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
            "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
        ]
        
        for fen in fens:
            board = Board(fen)
            assert board.to_fen() == fen


class TestInvalidFEN:
    """Test invalid FEN strings."""
    
    def test_too_few_parts(self):
        """Test FEN with too few parts."""
        with pytest.raises(ValueError):
            Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq")
    
    def test_too_many_parts(self):
        """Test FEN with too many parts."""
        with pytest.raises(ValueError):
            Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1 extra")
    
    def test_invalid_rank_count(self):
        """Test FEN with wrong number of ranks."""
        with pytest.raises(ValueError):
            Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP w KQkq - 0 1")
    
    def test_invalid_active_color(self):
        """Test FEN with invalid active color."""
        with pytest.raises(ValueError):
            Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR x KQkq - 0 1")
    
    def test_invalid_castling_rights(self):
        """Test FEN with invalid castling rights."""
        with pytest.raises(ValueError):
            Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkqX - 0 1")
    
    def test_invalid_en_passant(self):
        """Test FEN with invalid en passant square."""
        with pytest.raises(ValueError):
            Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq z9 0 1")
    
    def test_invalid_halfmove_clock(self):
        """Test FEN with invalid halfmove clock."""
        with pytest.raises(ValueError):
            Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - abc 1")
    
    def test_invalid_fullmove_number(self):
        """Test FEN with invalid fullmove number."""
        with pytest.raises(ValueError):
            Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 xyz")


class TestEdgeCases:
    """Test edge cases in FEN parsing."""
    
    def test_empty_board(self):
        """Test FEN with empty board (only kings)."""
        fen = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
        board = Board(fen)
        
        assert board.get_piece(Square(7, 4)).piece_type == 'king'
        assert board.get_piece(Square(0, 4)).piece_type == 'king'
    
    def test_all_pieces(self):
        """Test FEN with all piece types."""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        board = Board(fen)
        
        # Check all piece types exist
        piece_types = set()
        for rank in range(8):
            for file in range(8):
                piece = board.get_piece(Square(rank, file))
                if piece:
                    piece_types.add(piece.piece_type)
        
        assert piece_types == {'pawn', 'knight', 'bishop', 'rook', 'queen', 'king'}
    
    def test_promoted_pieces(self):
        """Test FEN with promoted pieces (multiple queens)."""
        fen = "4k3/8/8/8/8/8/8/Q3KQ2 w - - 0 1"
        board = Board(fen)
        
        assert board.get_piece(Square(0, 0)).piece_type == 'queen'
        assert board.get_piece(Square(0, 5)).piece_type == 'queen'
