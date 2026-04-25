"""
Tests for move generation.

Test coverage:
- Pseudo-legal move generation for all piece types
- Legal move filtering (check detection)
- Special moves (castling, en passant, promotion)
- Move validation
"""

import pytest
from core import Board, Square, Piece, Move, GameState


class TestPawnMoves:
    """Test pawn move generation."""
    
    def test_pawn_single_push(self):
        """Test single pawn push."""
        board = Board()
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # e2-e3 should be legal
        e2e3 = Move(Square(1, 4), Square(2, 4))
        assert e2e3 in moves
    
    def test_pawn_double_push(self):
        """Test double pawn push from starting position."""
        board = Board()
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # e2-e4 should be legal
        e2e4 = Move(Square(1, 4), Square(3, 4))
        assert e2e4 in moves
    
    def test_pawn_capture(self):
        """Test pawn capture."""
        board = Board("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # exd5 should be legal
        exd5 = Move(Square(3, 4), Square(4, 3))
        assert exd5 in moves
    
    def test_pawn_en_passant(self):
        """Test en passant capture."""
        board = Board("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # exf6 en passant should be legal
        exf6 = Move(Square(4, 4), Square(5, 5))
        assert exf6 in moves
    
    def test_pawn_promotion(self):
        """Test pawn promotion."""
        board = Board("8/P7/8/8/8/8/8/K6k w - - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # a7-a8 with all promotion options
        promotions = [
            Move(Square(6, 0), Square(7, 0), 'queen'),
            Move(Square(6, 0), Square(7, 0), 'rook'),
            Move(Square(6, 0), Square(7, 0), 'bishop'),
            Move(Square(6, 0), Square(7, 0), 'knight'),
        ]
        
        for promo in promotions:
            assert promo in moves


class TestKnightMoves:
    """Test knight move generation."""
    
    def test_knight_moves_from_start(self):
        """Test knight moves from starting position."""
        board = Board()
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # Nf3 and Nh3 should be legal
        nf3 = Move(Square(0, 6), Square(2, 5))
        nh3 = Move(Square(0, 6), Square(2, 7))
        
        assert nf3 in moves
        assert nh3 in moves
    
    def test_knight_moves_center(self):
        """Test knight moves from center."""
        board = Board("8/8/8/4N3/8/8/8/K6k w - - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # Knight on e5 should have 8 possible moves
        knight_moves = [m for m in moves if m.from_square == Square(4, 4)]
        assert len(knight_moves) == 8


class TestBishopMoves:
    """Test bishop move generation."""
    
    def test_bishop_moves(self):
        """Test bishop diagonal moves."""
        board = Board("8/8/8/4B3/8/8/8/K6k w - - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # Bishop on e5 should have 13 possible moves (can't capture own king)
        # Actually let me count: from e5, diagonals go to:
        # NE: f6, g7, h8 (3)
        # NW: d6, c7, b8 (3)
        # SE: f4, g3, h2 (3)
        # SW: d4, c3, b2, a1 (4)
        # Total: 13 moves
        # But the king is on a1, so one diagonal is blocked at a1
        # So it's 12 moves (can't go to a1 because king is there)
        bishop_moves = [m for m in moves if m.from_square == Square(4, 4)]
        assert len(bishop_moves) == 12


class TestRookMoves:
    """Test rook move generation."""
    
    def test_rook_moves(self):
        """Test rook horizontal/vertical moves."""
        board = Board("8/8/8/4R3/8/8/8/K6k w - - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # Rook on e5 should have 14 possible moves
        rook_moves = [m for m in moves if m.from_square == Square(4, 4)]
        assert len(rook_moves) == 14


class TestQueenMoves:
    """Test queen move generation."""
    
    def test_queen_moves(self):
        """Test queen moves (combination of rook and bishop)."""
        board = Board("8/8/8/4Q3/8/8/8/K6k w - - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # Queen on e5 should have 27 possible moves
        # Rook moves: 14, Bishop moves: 12 (blocked by king on a1)
        # Total: 26
        queen_moves = [m for m in moves if m.from_square == Square(4, 4)]
        assert len(queen_moves) == 26


class TestKingMoves:
    """Test king move generation."""
    
    def test_king_moves(self):
        """Test king moves."""
        board = Board("8/8/8/4K3/8/8/8/7k w - - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # King on e5 should have 8 possible moves
        king_moves = [m for m in moves if m.from_square == Square(4, 4)]
        assert len(king_moves) == 8
    
    def test_castling_kingside(self):
        """Test kingside castling."""
        board = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # O-O should be legal
        castle = Move(Square(0, 4), Square(0, 6))
        assert castle in moves
    
    def test_castling_queenside(self):
        """Test queenside castling."""
        board = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # O-O-O should be legal
        castle = Move(Square(0, 4), Square(0, 2))
        assert castle in moves
    
    def test_castling_blocked(self):
        """Test castling blocked by piece."""
        board = Board("r3k2r/8/8/8/8/8/8/R2QK2R w KQkq - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # O-O-O should be blocked
        castle = Move(Square(0, 4), Square(0, 2))
        assert castle not in moves
    
    def test_castling_through_check(self):
        """Test castling through check."""
        board = Board("r3k2r/8/8/8/8/5r2/8/R3K2R w KQkq - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # O-O should be blocked (f1 is attacked by rook on f3)
        castle = Move(Square(0, 4), Square(0, 6))
        assert castle not in moves
    
    def test_castling_out_of_check(self):
        """Test that castling out of check is illegal."""
        board = Board("r3k2r/8/8/8/8/8/8/R2rK2R w KQkq - 0 1")
        game_state = GameState(board)
        
        # King is in check from rook on d1, so no castling
        moves = game_state.get_legal_moves()
        
        castle_kingside = Move(Square(0, 4), Square(0, 6))
        castle_queenside = Move(Square(0, 4), Square(0, 2))
        
        assert castle_kingside not in moves
        assert castle_queenside not in moves


class TestLegalMoveFiltering:
    """Test legal move filtering (removing moves that leave king in check)."""
    
    def test_pinned_piece(self):
        """Test that pinned piece cannot move."""
        # Black rook on a1 pins white knight on e1 to white king on h1
        board = Board("4k3/8/8/8/8/8/8/r3N2K w - - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # Knight on e1 is pinned and cannot move
        knight_moves = [m for m in moves if m.from_square == Square(0, 4)]
        assert len(knight_moves) == 0
    
    def test_must_block_check(self):
        """Test that player in check must block or move king."""
        board = Board("4k3/8/8/8/8/8/8/4K2r w - - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # Only king moves should be legal
        for move in moves:
            piece = board.get_piece(move.from_square)
            assert piece.piece_type == 'king'
    
    def test_cannot_move_into_check(self):
        """Test that king cannot move into check."""
        board = Board("4k3/8/8/8/8/8/8/4K2r w - - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # King cannot move to f1 (attacked by rook)
        kf1 = Move(Square(0, 4), Square(0, 5))
        assert kf1 not in moves


class TestMoveCount:
    """Test move count for known positions."""
    
    def test_starting_position(self):
        """Test move count from starting position."""
        board = Board()
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # Starting position has 20 legal moves
        assert len(moves) == 20
    
    def test_perft_position_1(self):
        """Test move count for perft position 1."""
        board = Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        game_state = GameState(board)
        
        moves = game_state.get_legal_moves()
        
        # This position has 48 legal moves
        assert len(moves) == 48


class TestSpecialMoves:
    """Test special move detection."""
    
    def test_en_passant_detection(self):
        """Test en passant move detection."""
        board = Board("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3")
        game_state = GameState(board)
        
        move = Move(Square(4, 4), Square(5, 5))
        board.make_move(move)
        
        assert move.is_en_passant
    
    def test_castling_detection(self):
        """Test castling move detection."""
        board = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        
        move = Move(Square(0, 4), Square(0, 6))
        board.make_move(move)
        
        assert move.is_castling


class TestMoveValidation:
    """Test move validation."""
    
    def test_is_legal_move(self):
        """Test is_legal_move method."""
        board = Board()
        game_state = GameState(board)
        
        # Legal move
        legal_move = Move(Square(1, 4), Square(3, 4))  # e2-e4
        assert game_state.is_legal_move(legal_move)
        
        # Illegal move (piece doesn't exist)
        illegal_move = Move(Square(4, 4), Square(5, 4))
        assert not game_state.is_legal_move(illegal_move)
    
    def test_is_legal_move_check(self):
        """Test that moves leaving king in check are illegal."""
        # Black rook on a1 pins white knight on e1 to white king on h1
        board = Board("4k3/8/8/8/8/8/8/r3N2K w - - 0 1")
        game_state = GameState(board)
        
        # Knight is pinned
        illegal_move = Move(Square(0, 4), Square(2, 5))
        assert not game_state.is_legal_move(illegal_move)
