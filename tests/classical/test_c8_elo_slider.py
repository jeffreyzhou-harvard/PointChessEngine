"""C8.* tests for approximate Elo / strength slider."""

import random

from oneshot_nocontext_engine.search.elo import EloSettings
from oneshot_nocontext_engine.search.engine import Engine

from helpers import Board, ClassicalTestCase, legal_uci_moves, run_in_memory_uci


class TestC8_1StrengthConfig(ClassicalTestCase):
    def test_strength_config_bounds_and_defaults(self):
        self.assertEqual(EloSettings.from_elo(100).elo, 400)
        self.assertEqual(EloSettings.from_elo(3000).elo, 2400)
        self.assertIn("depth", EloSettings.from_elo(1500).describe())


class TestC8_2DepthTimeScaling(ClassicalTestCase):
    def test_higher_strength_gets_larger_budget(self):
        low = EloSettings.from_elo(400)
        high = EloSettings.from_elo(2400)
        self.assertGreater(high.max_depth, low.max_depth)
        self.assertGreater(high.time_limit, low.time_limit)


class TestC8_3ControlledNoise(ClassicalTestCase):
    def test_noise_and_blunder_rate_decrease_with_strength(self):
        low = EloSettings.from_elo(400)
        high = EloSettings.from_elo(2400)
        self.assertGreater(low.eval_noise, high.eval_noise)
        self.assertGreater(low.blunder_chance, high.blunder_chance)


class TestC8_4TopKLegalSampling(ClassicalTestCase):
    def test_weaker_sampling_preserves_legality_with_seed(self):
        board = Board()
        random.seed(7)
        engine = Engine(elo=400)
        best = board.legal_moves()[0]
        chosen = engine._apply_elo_adjustments(board, best, board.legal_moves())
        self.assertIn(chosen.uci(), legal_uci_moves(board))


class TestC8_5UciExposure(ClassicalTestCase):
    def test_uci_skill_option_is_exposed_and_settable(self):
        output = run_in_memory_uci(["uci", "setoption name UCI_Elo value 800", "isready", "quit"])
        self.assertIn("option name UCI_Elo", output)
        self.assertIn("readyok", output)


class TestC8_6CalibrationSmoke(ClassicalTestCase):
    def test_low_and_high_strength_settings_differ(self):
        low = EloSettings.from_elo(400)
        high = EloSettings.from_elo(2400)
        self.assertNotEqual(low, high)


class TestC8_7BehaviorReportGate(ClassicalTestCase):
    def test_strength_behavior_fields_are_reportable(self):
        settings = EloSettings.from_elo(1200)
        report = {
            "elo": settings.elo,
            "max_depth": settings.max_depth,
            "eval_noise": settings.eval_noise,
            "blunder_chance": settings.blunder_chance,
            "time_limit": settings.time_limit,
        }
        self.assertEqual(set(report), {"elo", "max_depth", "eval_noise", "blunder_chance", "time_limit"})
