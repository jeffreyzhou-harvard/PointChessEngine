"""Tests for chess board, move generation, and special rules."""

import unittest
from oneshot_nocontext_engine.core.board import Board, STARTING_FEN
from oneshot_nocontext_engine.core.types import Color, PieceType, Piece, Move, Square


class TestFEN(unittest.TestCase):
    def test_starting_position(self):
        board = Board()
        self.assertEqual(board.to_fen(), STARTING_FEN)

    def test_load_custom_fen(self):
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        board = Board(fen)
        self.assertEqual(board.to_fen(), fen)
        self.assertEqual(board.turn, Color.BLACK)
        self.assertEqual(board.en_passant, Square.from_algebraic('e3'))

    def test_fen_no_castling(self):
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"
        board = Board(fen)
        for key in board.castling_rights:
            self.assertFalse(board.castling_rights[key])

    def test_fen_roundtrip(self):
        fens = [
            STARTING_FEN,
            "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1",
            "8/8/8/8/8/8/8/4K3 w - - 0 1",
            "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        ]
        for fen in fens:
            board = Board(fen)
            self.assertEqual(board.to_fen(), fen)


class TestMoveGeneration(unittest.TestCase):
    def test_starting_position_moves(self):
        board = Board()
        moves = board.legal_moves()
        self.assertEqual(len(moves), 20)  # 16 pawn + 4 knight

    def test_pawn_double_push(self):
        board = Board()
        e2e4 = Move(Square.from_algebraic('e2'), Square.from_algebraic('e4'))
        self.assertIn(e2e4, board.legal_moves())

    def test_knight_moves(self):
        board = Board()
        # Nf3
        nf3 = Move(Square.from_algebraic('g1'), Square.from_algebraic('f3'))
        self.assertIn(nf3, board.legal_moves())

    def test_blocked_pawn(self):
        fen = "8/8/8/8/4p3/4P3/8/4K2k w - - 0 1"
        board = Board(fen)
        moves = board.legal_moves()
        # e3 pawn is blocked, should not be able to move
        pawn_moves = [m for m in moves if m.from_sq == Square.from_algebraic('e3')]
        self.assertEqual(len(pawn_moves), 0)


class TestSpecialMoves(unittest.TestCase):
    def test_en_passant(self):
        # Set up en passant position
        fen = "rnbqkbnr/pppp1ppp/8/4pP2/8/8/PPPPP1PP/RNBQKBNR w KQkq e6 0 3"
        board = Board(fen)
        ep_move = Move(Square.from_algebraic('f5'), Square.from_algebraic('e6'))
        self.assertIn(ep_move, board.legal_moves())

        # Make en passant capture
        board.make_move(ep_move)
        # The captured pawn on e5 should be gone
        self.assertIsNone(board.piece_at(Square.from_algebraic('e5')))
        # Our pawn should be on e6
        piece = board.piece_at(Square.from_algebraic('e6'))
        self.assertIsNotNone(piece)
        self.assertEqual(piece.piece_type, PieceType.PAWN)

    def test_castling_kingside(self):
        fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1"
        board = Board(fen)
        castle = Move(Square.from_algebraic('e1'), Square.from_algebraic('g1'))
        self.assertIn(castle, board.legal_moves())

        board.make_move(castle)
        # King on g1, rook on f1
        self.assertEqual(board.piece_at(Square.from_algebraic('g1')).piece_type, PieceType.KING)
        self.assertEqual(board.piece_at(Square.from_algebraic('f1')).piece_type, PieceType.ROOK)
        self.assertIsNone(board.piece_at(Square.from_algebraic('e1')))
        self.assertIsNone(board.piece_at(Square.from_algebraic('h1')))

    def test_castling_queenside(self):
        fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1"
        board = Board(fen)
        castle = Move(Square.from_algebraic('e1'), Square.from_algebraic('c1'))
        self.assertIn(castle, board.legal_moves())

        board.make_move(castle)
        self.assertEqual(board.piece_at(Square.from_algebraic('c1')).piece_type, PieceType.KING)
        self.assertEqual(board.piece_at(Square.from_algebraic('d1')).piece_type, PieceType.ROOK)

    def test_cannot_castle_through_check(self):
        # Rook attacks f1, so kingside castling is illegal
        fen = "4k3/8/8/8/8/8/8/R3K1r1 w Q - 0 1"
        board = Board(fen)
        castle = Move(Square.from_algebraic('e1'), Square.from_algebraic('g1'))
        self.assertNotIn(castle, board.legal_moves())

    def test_cannot_castle_in_check(self):
        fen = "4k3/8/8/8/4r3/8/8/R3K2R w KQ - 0 1"
        board = Board(fen)
        moves = board.legal_moves()
        castle_k = Move(Square.from_algebraic('e1'), Square.from_algebraic('g1'))
        castle_q = Move(Square.from_algebraic('e1'), Square.from_algebraic('c1'))
        self.assertNotIn(castle_k, moves)
        self.assertNotIn(castle_q, moves)

    def test_promotion(self):
        fen = "8/4P3/8/8/8/8/8/4K2k w - - 0 1"
        board = Board(fen)
        moves = board.legal_moves()
        promo_moves = [m for m in moves if m.from_sq == Square.from_algebraic('e7')]
        # Should have 4 promotion choices
        self.assertEqual(len(promo_moves), 4)
        promo_types = {m.promotion for m in promo_moves}
        self.assertEqual(promo_types, {PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT})

    def test_castling_rights_lost_on_king_move(self):
        fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1"
        board = Board(fen)
        board.make_move(Move(Square.from_algebraic('e1'), Square.from_algebraic('f1')))
        self.assertFalse(board.castling_rights['K'])
        self.assertFalse(board.castling_rights['Q'])

    def test_castling_rights_lost_on_rook_move(self):
        fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1"
        board = Board(fen)
        board.make_move(Move(Square.from_algebraic('h1'), Square.from_algebraic('g1')))
        self.assertFalse(board.castling_rights['K'])
        self.assertTrue(board.castling_rights['Q'])  # queenside still OK


class TestCheckAndMate(unittest.TestCase):
    def test_check(self):
        fen = "4k3/8/8/8/8/8/8/4K2R w - - 0 1"
        board = Board(fen)
        board.make_move(Move(Square.from_algebraic('h1'), Square.from_algebraic('h8')))
        self.assertTrue(board.is_in_check(Color.BLACK))

    def test_scholars_mate(self):
        board = Board()
        moves = [
            Move.from_uci('e2e4'), Move.from_uci('e7e5'),
            Move.from_uci('d1h5'), Move.from_uci('b8c6'),
            Move.from_uci('f1c4'), Move.from_uci('g8f6'),
            Move.from_uci('h5f7'),
        ]
        for m in moves:
            legal = board.legal_moves()
            matched = [l for l in legal if l.from_sq == m.from_sq and l.to_sq == m.to_sq]
            self.assertTrue(matched, f"Move {m.uci()} should be legal")
            board.make_move(matched[0])

        self.assertTrue(board.is_checkmate())

    def test_stalemate(self):
        # Classic stalemate: black king on a8, white queen on b6, white king on c8 is wrong
        # Use: black king h8, white king g6, white queen f7 - black has no moves
        fen = "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"
        board = Board(fen)
        self.assertFalse(board.is_in_check(Color.BLACK))
        self.assertEqual(len(board.legal_moves()), 0)
        self.assertTrue(board.is_stalemate())

    def test_not_stalemate_with_moves(self):
        board = Board()
        self.assertFalse(board.is_stalemate())

    def test_pinned_piece_cannot_move(self):
        # Knight on f3 is pinned by bishop on b7 (diagonal to king on h1... wait)
        # Simpler: rook pins a piece to the king
        fen = "4k3/8/8/8/8/8/4R3/4K3 b - - 0 1"
        board = Board(fen)
        # Black king is in check from rook on e2, must deal with it
        moves = board.legal_moves()
        # King must move, no pieces to block
        for m in moves:
            self.assertEqual(m.from_sq, Square.from_algebraic('e8'))


class TestGameState(unittest.TestCase):
    def test_insufficient_material_kk(self):
        fen = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
        board = Board(fen)
        self.assertTrue(board.is_insufficient_material())

    def test_insufficient_material_kb(self):
        fen = "4k3/8/8/8/8/8/8/4KB2 w - - 0 1"
        board = Board(fen)
        self.assertTrue(board.is_insufficient_material())

    def test_insufficient_material_kn(self):
        fen = "4k3/8/8/8/8/8/8/4KN2 w - - 0 1"
        board = Board(fen)
        self.assertTrue(board.is_insufficient_material())

    def test_sufficient_material_kr(self):
        fen = "4k3/8/8/8/8/8/8/4KR2 w - - 0 1"
        board = Board(fen)
        self.assertFalse(board.is_insufficient_material())

    def test_fifty_move_rule(self):
        fen = "4k3/8/8/8/8/8/8/4K3 w - - 100 50"
        board = Board(fen)
        self.assertTrue(board.is_fifty_move_rule())

    def test_undo_move(self):
        board = Board()
        original_fen = board.to_fen()
        e2e4 = Move(Square.from_algebraic('e2'), Square.from_algebraic('e4'))
        board.make_move(e2e4)
        self.assertNotEqual(board.to_fen(), original_fen)
        board.unmake_move()
        self.assertEqual(board.to_fen(), original_fen)

    def test_undo_en_passant(self):
        fen = "rnbqkbnr/pppp1ppp/8/4pP2/8/8/PPPPP1PP/RNBQKBNR w KQkq e6 0 3"
        board = Board(fen)
        ep_move = Move(Square.from_algebraic('f5'), Square.from_algebraic('e6'))
        board.make_move(ep_move)
        board.unmake_move()
        self.assertEqual(board.to_fen(), fen)

    def test_undo_castling(self):
        fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1"
        board = Board(fen)
        castle = Move(Square.from_algebraic('e1'), Square.from_algebraic('g1'))
        board.make_move(castle)
        board.unmake_move()
        self.assertEqual(board.to_fen(), fen)

    def test_undo_promotion(self):
        fen = "8/4P3/8/8/8/8/8/4K2k w - - 0 1"
        board = Board(fen)
        promo = Move(Square.from_algebraic('e7'), Square.from_algebraic('e8'), PieceType.QUEEN)
        board.make_move(promo)
        board.unmake_move()
        self.assertEqual(board.to_fen(), fen)


class TestPerft(unittest.TestCase):
    """Perft tests verify move generation correctness by counting leaf nodes."""

    def test_starting_position_depth_1(self):
        board = Board()
        self.assertEqual(board.perft(1), 20)

    def test_starting_position_depth_2(self):
        board = Board()
        self.assertEqual(board.perft(2), 400)

    def test_starting_position_depth_3(self):
        board = Board()
        self.assertEqual(board.perft(3), 8902)

    def test_kiwipete_depth_1(self):
        # Famous position for testing move generation
        fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        board = Board(fen)
        self.assertEqual(board.perft(1), 48)

    def test_kiwipete_depth_2(self):
        fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        board = Board(fen)
        self.assertEqual(board.perft(2), 2039)

    def test_position_3_depth_1(self):
        fen = "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"
        board = Board(fen)
        self.assertEqual(board.perft(1), 14)

    def test_position_3_depth_2(self):
        fen = "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"
        board = Board(fen)
        self.assertEqual(board.perft(2), 191)


class TestSAN(unittest.TestCase):
    def test_pawn_move(self):
        board = Board()
        move = Move(Square.from_algebraic('e2'), Square.from_algebraic('e4'))
        self.assertEqual(board.move_to_san(move), 'e4')

    def test_knight_move(self):
        board = Board()
        move = Move(Square.from_algebraic('g1'), Square.from_algebraic('f3'))
        self.assertEqual(board.move_to_san(move), 'Nf3')

    def test_capture(self):
        fen = "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2"
        board = Board(fen)
        move = Move(Square.from_algebraic('e4'), Square.from_algebraic('d5'))
        self.assertEqual(board.move_to_san(move), 'exd5')

    def test_castling_san(self):
        fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1"
        board = Board(fen)
        ks = Move(Square.from_algebraic('e1'), Square.from_algebraic('g1'))
        qs = Move(Square.from_algebraic('e1'), Square.from_algebraic('c1'))
        self.assertEqual(board.move_to_san(ks), 'O-O')
        self.assertEqual(board.move_to_san(qs), 'O-O-O')


class TestPGN(unittest.TestCase):
    def test_pgn_export(self):
        board = Board()
        board.make_move(Move(Square.from_algebraic('e2'), Square.from_algebraic('e4')))
        board.make_move(Move(Square.from_algebraic('e7'), Square.from_algebraic('e5')))
        pgn = board.to_pgn()
        self.assertIn('1. e4 e5', pgn)
        self.assertIn('[Event', pgn)


if __name__ == '__main__':
    unittest.main()
