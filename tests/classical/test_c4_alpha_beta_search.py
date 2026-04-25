"""C4.* tests for alpha-beta search."""

from oneshot_nocontext_engine.search.engine import Engine

from helpers import Board, ClassicalTestCase, legal_uci_moves


class TestC4_1SearchApi(ClassicalTestCase):
    def test_search_returns_uci_ready_legal_move_and_score(self):
        board = Board()
        move, score = Engine(elo=2400).search(board, max_depth=1, time_limit=1.0)
        self.assertIsNotNone(move)
        self.assertIn(move.uci(), legal_uci_moves(board))
        self.assertIsInstance(score, int)


class TestC4_2FixedDepthTerminalHandling(ClassicalTestCase):
    def test_terminal_position_returns_no_move(self):
        board = Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
        move, score = Engine(elo=2400).search(board, max_depth=2, time_limit=1.0)
        self.assertIsNone(move)
        self.assertEqual(score, 0)


class TestC4_3AlphaBetaDeterminism(ClassicalTestCase):
    def test_fixed_depth_search_is_deterministic_at_full_strength(self):
        board = Board()
        engine = Engine(elo=2400)
        move1, score1 = engine.search(board, max_depth=2, time_limit=1.0)
        move2, score2 = engine.search(board, max_depth=2, time_limit=1.0)
        self.assertEqual(move1, move2)
        self.assertEqual(score1, score2)


class TestC4_4BoardStateSafety(ClassicalTestCase):
    def test_search_does_not_mutate_board(self):
        board = Board()
        original = board.to_fen()
        Engine(elo=2400).search(board, max_depth=2, time_limit=1.0)
        self.assertEqual(board.to_fen(), original)


class TestC4_5Diagnostics(ClassicalTestCase):
    def test_search_statistics_are_available(self):
        engine = Engine(elo=2400)
        engine.search(Board(), max_depth=2, time_limit=1.0)
        info = engine.get_info()
        self.assertGreater(info["nodes"], 0)
        self.assertIn("time_ms", info)
        self.assertIn("nps", info)


class TestC4_6TacticalSmoke(ClassicalTestCase):
    def test_finds_mate_in_one_or_decisive_score(self):
        board = Board("6k1/5ppp/8/8/8/8/8/4K2Q w - - 0 1")
        move, score = Engine(elo=2400).search(board, max_depth=3, time_limit=2.0)
        self.assertIsNotNone(move)
        board.make_move(move)
        self.assertTrue(board.is_checkmate() or score > 50000)


class TestC4_7RandomBaselineSmoke(ClassicalTestCase):
    def test_full_strength_search_returns_legal_move_against_random_baseline_position(self):
        board = Board()
        move, _ = Engine(elo=2400).search(board, max_depth=2, time_limit=1.0)
        self.assertIn(move.uci(), legal_uci_moves(board))
