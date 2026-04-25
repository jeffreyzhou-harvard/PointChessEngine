"""Tests for the chess engine search and evaluation."""

import unittest
from oneshot_nocontext_engine.core.board import Board
from oneshot_nocontext_engine.core.types import Color, PieceType, Move, Square
from oneshot_nocontext_engine.search.engine import Engine
from oneshot_nocontext_engine.search.evaluation import evaluate
from oneshot_nocontext_engine.search.elo import EloSettings


class TestEvaluation(unittest.TestCase):
    def test_starting_position_roughly_equal(self):
        board = Board()
        score = evaluate(board)
        # Starting position should be roughly equal (within ~50cp)
        self.assertAlmostEqual(score, 0, delta=50)

    def test_material_advantage(self):
        # White has extra queen
        fen = "4k3/8/8/8/8/8/8/4KQ2 w - - 0 1"
        board = Board(fen)
        score = evaluate(board)
        self.assertGreater(score, 800)

    def test_black_material_advantage(self):
        fen = "4kq2/8/8/8/8/8/8/4K3 w - - 0 1"
        board = Board(fen)
        score = evaluate(board)
        self.assertLess(score, -800)


class TestEngine(unittest.TestCase):
    def test_finds_mate_in_1(self):
        # White to move, Qh7# is mate
        fen = "6k1/5ppp/8/8/8/8/8/4K2Q w - - 0 1"
        board = Board(fen)
        engine = Engine(elo=2400)
        move, score = engine.search(board, max_depth=3, time_limit=5.0)
        self.assertIsNotNone(move)
        # Engine should find the mate
        board.make_move(move)
        # Check that it's checkmate or very high score
        if board.is_checkmate():
            pass  # Perfect
        else:
            self.assertGreater(score, 50000)  # Should still find winning move

    def test_captures_free_piece(self):
        # White queen can take undefended black rook
        fen = "4k3/8/8/8/3r4/8/8/3QK3 w - - 0 1"
        board = Board(fen)
        engine = Engine(elo=2400)
        move, score = engine.search(board, max_depth=3, time_limit=5.0)
        self.assertIsNotNone(move)
        # Should capture the rook
        self.assertEqual(move.to_sq, Square.from_algebraic('d4'))

    def test_does_not_hang_queen(self):
        # Starting-ish position, engine should not blunder queen
        board = Board()
        engine = Engine(elo=2400)
        move, score = engine.search(board, max_depth=3, time_limit=5.0)
        self.assertIsNotNone(move)
        # Score should be reasonable
        self.assertGreater(score, -200)

    def test_search_returns_move_in_any_position(self):
        board = Board()
        engine = Engine(elo=1000)
        move, _ = engine.search(board, max_depth=2, time_limit=2.0)
        self.assertIsNotNone(move)


class TestEloSettings(unittest.TestCase):
    def test_elo_range(self):
        for elo in [400, 800, 1200, 1600, 2000, 2400]:
            settings = EloSettings.from_elo(elo)
            self.assertEqual(settings.elo, elo)
            self.assertGreater(settings.max_depth, 0)
            self.assertGreaterEqual(settings.eval_noise, 0)
            self.assertGreaterEqual(settings.blunder_chance, 0)
            self.assertGreater(settings.time_limit, 0)

    def test_higher_elo_deeper_search(self):
        low = EloSettings.from_elo(400)
        high = EloSettings.from_elo(2400)
        self.assertGreater(high.max_depth, low.max_depth)

    def test_higher_elo_less_noise(self):
        low = EloSettings.from_elo(400)
        high = EloSettings.from_elo(2400)
        self.assertGreater(low.eval_noise, high.eval_noise)

    def test_higher_elo_fewer_blunders(self):
        low = EloSettings.from_elo(400)
        high = EloSettings.from_elo(2400)
        self.assertGreater(low.blunder_chance, high.blunder_chance)

    def test_describe(self):
        settings = EloSettings.from_elo(1500)
        desc = settings.describe()
        self.assertIn('1500', desc)
        self.assertIn('depth', desc)

    def test_clamp_elo(self):
        low = EloSettings.from_elo(100)
        self.assertEqual(low.elo, 400)
        high = EloSettings.from_elo(3000)
        self.assertEqual(high.elo, 2400)


if __name__ == '__main__':
    unittest.main()
