"""C1.* tests for board, FEN, and move representation."""

from oneshot_nocontext_engine.core.types import Color, Move, Piece, PieceType, Square

from helpers import Board, ClassicalTestCase, STARTING_FEN


class TestC1_1Representation(ClassicalTestCase):
    def test_square_piece_and_board_state_basics(self):
        self.assertEqual(Square.from_algebraic("e4").algebraic(), "e4")
        self.assertFalse(Square(9, 9).is_valid())
        self.assertEqual(Piece(Color.WHITE, PieceType.KNIGHT).symbol(), "N")
        self.assertEqual(Piece(Color.BLACK, PieceType.KNIGHT).symbol(), "n")
        board = Board()
        self.assertEqual(board.turn, Color.WHITE)
        self.assertEqual(board.copy().to_fen(), board.to_fen())


class TestC1_2FenParsing(ClassicalTestCase):
    def test_valid_and_invalid_fen_inputs(self):
        board = Board(STARTING_FEN)
        self.assertEqual(board.to_fen(), STARTING_FEN)
        with self.assertRaises(Exception):
            Board("not a fen")
        with self.assertRaises(Exception):
            Board("8/8/8/8/8/8/8/Z7 w - - 0 1")


class TestC1_3FenSerialization(ClassicalTestCase):
    def test_fen_round_trips_are_deterministic(self):
        fens = [
            STARTING_FEN,
            "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1",
            "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        ]
        for fen in fens:
            with self.subTest(fen=fen):
                self.assertFenRoundTrip(fen)


class TestC1_4UciMoveRepresentation(ClassicalTestCase):
    def test_uci_move_parser_and_serializer(self):
        self.assertEqual(Move.from_uci("e2e4").uci(), "e2e4")
        promotion = Move.from_uci("e7e8q")
        self.assertEqual(promotion.uci(), "e7e8q")
        self.assertEqual(promotion.promotion, PieceType.QUEEN)
        with self.assertRaises(Exception):
            Move.from_uci("e7e8x")


class TestC1_5StateFields(ClassicalTestCase):
    def test_fen_state_fields_are_preserved(self):
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 4 7"
        board = Board(fen)
        self.assertEqual(board.turn, Color.BLACK)
        self.assertEqual(board.en_passant, Square.from_algebraic("e3"))
        self.assertEqual(board.halfmove_clock, 4)
        self.assertEqual(board.fullmove_number, 7)
        self.assertTrue(board.castling_rights["K"])
        self.assertTrue(board.castling_rights["q"])
        self.assertEqual(board.to_fen(), fen)


class TestC1_6FullC1Gate(ClassicalTestCase):
    def test_core_fen_and_move_gate(self):
        board = Board()
        self.assertEqual(board.to_fen(), STARTING_FEN)
        self.assertEqual(Move.from_uci("a7a8n").uci(), "a7a8n")
