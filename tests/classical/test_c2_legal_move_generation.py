"""C2.* tests for legal move generation and rule correctness."""

from oneshot_nocontext_engine.core.types import Color, Move, PieceType, Square

from tests.classical.helpers import Board, ClassicalTestCase, legal_uci_moves


class TestC2_1AttackDetection(ClassicalTestCase):
    def test_attacks_and_check_detection_from_major_piece(self):
        board = Board("4k3/8/8/8/8/8/8/4K2R w - - 0 1")
        board.make_move(Move.from_uci("h1h8"))
        self.assertTrue(board.is_square_attacked(Square.from_algebraic("e8"), Color.WHITE))
        self.assertTrue(board.is_in_check(Color.BLACK))


class TestC2_2PseudoLegalGeneration(ClassicalTestCase):
    def test_starting_position_has_expected_basic_moves(self):
        board = Board()
        moves = legal_uci_moves(board)
        self.assertEqual(len(moves), 20)
        self.assertIn("e2e4", moves)
        self.assertIn("g1f3", moves)


class TestC2_3SpecialRules(ClassicalTestCase):
    def test_castling_en_passant_and_promotion_are_generated(self):
        castle_board = Board("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1")
        self.assertIn("e1g1", legal_uci_moves(castle_board))
        ep_board = Board("rnbqkbnr/pppp1ppp/8/4pP2/8/8/PPPPP1PP/RNBQKBNR w KQkq e6 0 3")
        self.assertIn("f5e6", legal_uci_moves(ep_board))
        promo_board = Board("8/4P3/8/8/8/8/8/4K2k w - - 0 1")
        self.assertEqual(
            {move.uci() for move in promo_board.legal_moves() if move.from_sq == Square.from_algebraic("e7")},
            {"e7e8q", "e7e8r", "e7e8b", "e7e8n"},
        )


class TestC2_4StateRestoration(ClassicalTestCase):
    def test_make_unmake_restores_special_move_state(self):
        for fen, uci in [
            ("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1", "e1g1"),
            ("rnbqkbnr/pppp1ppp/8/4pP2/8/8/PPPPP1PP/RNBQKBNR w KQkq e6 0 3", "f5e6"),
            ("8/4P3/8/8/8/8/8/4K2k w - - 0 1", "e7e8q"),
        ]:
            with self.subTest(fen=fen, move=uci):
                board = Board(fen)
                original = board.to_fen()
                move = next(m for m in board.legal_moves() if m.uci() == uci)
                self.assertTrue(board.make_move(move))
                board.unmake_move()
                self.assertEqual(board.to_fen(), original)


class TestC2_5LegalFiltering(ClassicalTestCase):
    def test_pins_and_en_passant_discovered_check_are_filtered(self):
        pinned = Board("4k3/8/8/8/8/8/4R3/4K3 b - - 0 1")
        for move in pinned.legal_moves():
            self.assertEqual(move.from_sq, Square.from_algebraic("e8"))
        ep_pin = Board("k3r3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
        self.assertNotIn("e5d6", legal_uci_moves(ep_pin))


class TestC2_6TerminalDetection(ClassicalTestCase):
    def test_checkmate_and_stalemate_detection(self):
        mate = Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
        self.assertTrue(mate.is_checkmate())
        stale = Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        self.assertTrue(stale.is_stalemate())


class TestC2_7PerftHooks(ClassicalTestCase):
    def test_starting_position_perft_depths(self):
        board = Board()
        self.assertEqual(board.perft(1), 20)
        self.assertEqual(board.perft(2), 400)
        self.assertEqual(board.perft(3), 8902)
