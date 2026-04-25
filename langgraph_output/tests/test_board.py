"""
Tests for Board class.

Test coverage:
- Board initialization (default and from FEN)
- Piece placement and retrieval
- FEN parsing and generation
- Board copying
- Move application (make_move/unmake_move)
"""

import pytest
from core import Board, Square, Piece, Move


class TestBoardInitialization:
    """Test board initialization."""
    
    def test_default_initialization(self):
        """Test default starting position."""
        board = Board()
        
        # Check white pieces
        assert board.get_piece(Square(0, 0)).piece_type == 'rook'
        assert board.get_piece(Square(0, 0)).color == 'white'
        assert board.get_piece(Square(0, 4)).piece_type == 'king'
        assert board.get_piece(Square(1, 0)).piece_type == 'pawn'
        
        # Check black pieces
        assert board.get_piece(Square(7, 0)).piece_type == 'rook'
        assert board.get_piece(Square(7, 0)).color == 'black'
        assert board.get_piece(Square(7, 4)).piece_type == 'king'
        assert board.get_piece(Square(6, 0)).piece_type == 'pawn'
        
        # Check empty squares
        assert board.get_piece(Square(2, 0)) is None
        assert board.get_piece(Square(4, 4)) is None
        
        # Check initial state
        assert board.active_color == 'white'
        assert board.castling_rights == {'K': True, 'Q': True, 'k': True, 'q': True}
        assert board.en_passant_target is None
        assert board.halfmove_clock == 0
        assert board.fullmove_number == 1
    
    def test_custom_fen(self):
        """Test initialization from custom FEN."""
        fen = "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"
        board = Board(fen)
        
        assert board.active_color == 'black'
        assert board.halfmove_clock == 1
        assert board.fullmove_number == 2
        # e4 is rank 3, file 4 (0-indexed)
        assert board.get_piece(Square(3, 4)).piece_type == 'pawn'
        assert board.get_piece(Square(3, 4)).color == 'white'
        # f3 is rank 2, file 5
        assert board.get_piece(Square(2, 5)).piece_type == 'knight'


class TestFENParsing:
    """Test FEN parsing and generation."""
    
    def test_fen_round_trip(self):
        """Test FEN parsing and generation round trip."""
        fens = [
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
            "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
            "8/8/8/4k3/8/8/8/4K3 w - - 0 1",
        ]
        
        for fen in fens:
            board = Board(fen)
            assert board.to_fen() == fen
    
    def test_invalid_fen(self):
        """Test invalid FEN strings."""
        invalid_fens = [
            "invalid",
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR",  # Missing parts
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP w KQkq - 0 1",  # Only 7 ranks
        ]
        
        for fen in invalid_fens:
            with pytest.raises(ValueError):
                Board(fen)


class TestPiecePlacement:
    """Test piece placement and retrieval."""
    
    def test_get_set_piece(self):
        """Test getting and setting pieces."""
        board = Board()
        
        # Get piece
        piece = board.get_piece(Square(0, 0))
        assert piece.piece_type == 'rook'
        assert piece.color == 'white'
        
        # Set piece
        new_piece = Piece('queen', 'black')
        board.set_piece(Square(4, 4), new_piece)
        assert board.get_piece(Square(4, 4)) == new_piece
        
        # Clear piece
        board.set_piece(Square(4, 4), None)
        assert board.get_piece(Square(4, 4)) is None
    
    def test_find_king(self):
        """Test finding king."""
        board = Board()
        
        white_king = board.find_king('white')
        assert white_king == Square(0, 4)
        
        black_king = board.find_king('black')
        assert black_king == Square(7, 4)


class TestMoveApplication:
    """Test move application and undo."""
    
    def test_simple_move(self):
        """Test simple pawn move."""
        board = Board()
        move = Move(Square(1, 4), Square(3, 4))  # e2-e4
        
        board.make_move(move)
        
        assert board.get_piece(Square(1, 4)) is None
        assert board.get_piece(Square(3, 4)).piece_type == 'pawn'
        assert board.active_color == 'black'
        assert board.halfmove_clock == 0  # Pawn move resets
    
    def test_capture(self):
        """Test capture move."""
        board = Board("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2")
        move = Move(Square(3, 4), Square(4, 3))  # exd5
        
        board.make_move(move)
        
        assert board.get_piece(Square(3, 4)) is None
        assert board.get_piece(Square(4, 3)).piece_type == 'pawn'
        assert board.get_piece(Square(4, 3)).color == 'white'
        assert board.halfmove_clock == 0  # Capture resets
    
    def test_en_passant(self):
        """Test en passant capture."""
        board = Board("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3")
        move = Move(Square(4, 4), Square(5, 5))  # exf6 en passant
        
        board.make_move(move)
        
        assert board.get_piece(Square(4, 4)) is None
        assert board.get_piece(Square(5, 5)).piece_type == 'pawn'
        assert board.get_piece(Square(4, 5)) is None  # Captured pawn removed
    
    def test_castling_kingside(self):
        """Test kingside castling."""
        board = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        move = Move(Square(0, 4), Square(0, 6))  # O-O
        
        board.make_move(move)
        
        assert board.get_piece(Square(0, 6)).piece_type == 'king'
        assert board.get_piece(Square(0, 5)).piece_type == 'rook'
        assert board.get_piece(Square(0, 4)) is None
        assert board.get_piece(Square(0, 7)) is None
        assert not board.castling_rights['K']
        assert not board.castling_rights['Q']
    
    def test_castling_queenside(self):
        """Test queenside castling."""
        board = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        move = Move(Square(0, 4), Square(0, 2))  # O-O-O
        
        board.make_move(move)
        
        assert board.get_piece(Square(0, 2)).piece_type == 'king'
        assert board.get_piece(Square(0, 3)).piece_type == 'rook'
        assert board.get_piece(Square(0, 4)) is None
        assert board.get_piece(Square(0, 0)) is None
    
    def test_promotion(self):
        """Test pawn promotion."""
        board = Board("8/P7/8/8/8/8/8/K6k w - - 0 1")
        move = Move(Square(6, 0), Square(7, 0), 'queen')
        
        board.make_move(move)
        
        assert board.get_piece(Square(7, 0)).piece_type == 'queen'
        assert board.get_piece(Square(7, 0)).color == 'white'
    
    def test_unmake_move(self):
        """Test move undo."""
        board = Board()
        original_fen = board.to_fen()
        
        move = Move(Square(1, 4), Square(3, 4))  # e2-e4
        board.make_move(move)
        board.unmake_move(move)
        
        assert board.to_fen() == original_fen
    
    def test_unmake_capture(self):
        """Test undo of capture."""
        board = Board("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2")
        original_fen = board.to_fen()
        
        move = Move(Square(3, 4), Square(4, 3))  # exd5
        board.make_move(move)
        board.unmake_move(move)
        
        assert board.to_fen() == original_fen
    
    def test_unmake_castling(self):
        """Test undo of castling."""
        board = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        original_fen = board.to_fen()
        
        move = Move(Square(0, 4), Square(0, 6))  # O-O
        board.make_move(move)
        board.unmake_move(move)
        
        assert board.to_fen() == original_fen


class TestBoardCopy:
    """Test board copying."""
    
    def test_copy(self):
        """Test board copy."""
        board1 = Board()
        board2 = board1.copy()
        
        # Modify board2
        board2.set_piece(Square(4, 4), Piece('queen', 'white'))
        
        # board1 should be unchanged
        assert board1.get_piece(Square(4, 4)) is None
        assert board2.get_piece(Square(4, 4)).piece_type == 'queen'


class TestCastlingRights:
    """Test castling rights updates."""
    
    def test_king_move_removes_castling(self):
        """Test that moving king removes castling rights."""
        board = Board()
        move = Move(Square(0, 4), Square(0, 5))  # Ke1-f1
        
        board.make_move(move)
        
        assert not board.castling_rights['K']
        assert not board.castling_rights['Q']
    
    def test_rook_move_removes_castling(self):
        """Test that moving rook removes castling rights."""
        board = Board()
        
        # Move kingside rook
        move = Move(Square(0, 7), Square(0, 6))
        board.make_move(move)
        
        assert not board.castling_rights['K']
        assert board.castling_rights['Q']  # Queenside still available


class TestEnPassant:
    """Test en passant target setting."""
    
    def test_double_pawn_push_sets_en_passant(self):
        """Test that double pawn push sets en passant target."""
        board = Board()
        move = Move(Square(1, 4), Square(3, 4))  # e2-e4
        
        board.make_move(move)
        
        assert board.en_passant_target == Square(2, 4)
    
    def test_single_pawn_push_no_en_passant(self):
        """Test that single pawn push doesn't set en passant."""
        board = Board()
        move = Move(Square(1, 4), Square(2, 4))  # e2-e3
        
        board.make_move(move)
        
        assert board.en_passant_target is None
    
    def test_en_passant_cleared_after_move(self):
        """Test that en passant target is cleared after next move."""
        board = Board()
        
        # Double pawn push
        move1 = Move(Square(1, 4), Square(3, 4))  # e2-e4
        board.make_move(move1)
        assert board.en_passant_target is not None
        
        # Another move
        move2 = Move(Square(6, 0), Square(5, 0))  # a7-a6
        board.make_move(move2)
        assert board.en_passant_target is None
