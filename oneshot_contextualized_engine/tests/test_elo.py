"""ELO mapping tests."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.elo import config_from_elo, config_from_skill


class EloMappingTest(unittest.TestCase):
    def test_clamping(self):
        self.assertEqual(config_from_elo(50).elo, 400)
        self.assertEqual(config_from_elo(9999).elo, 2400)

    def test_monotonic_depth_and_time(self):
        elos = list(range(400, 2401, 100))
        depths = [config_from_elo(e).max_depth for e in elos]
        times  = [config_from_elo(e).move_time_ms for e in elos]
        for a, b in zip(depths, depths[1:]):
            self.assertLessEqual(a, b)
        for a, b in zip(times, times[1:]):
            self.assertLessEqual(a, b)

    def test_noise_decreases(self):
        elos = list(range(400, 2401, 100))
        noise = [config_from_elo(e).eval_noise_cp for e in elos]
        for a, b in zip(noise, noise[1:]):
            self.assertGreaterEqual(a, b)

    def test_full_strength_is_clean(self):
        cfg = config_from_elo(2400)
        self.assertEqual(cfg.eval_noise_cp, 0)
        self.assertEqual(cfg.blunder_prob, 0.0)

    def test_skill_level_mapping(self):
        # 0 maps near min, 20 maps near max.
        self.assertLessEqual(config_from_skill(0).elo, 500)
        self.assertGreaterEqual(config_from_skill(20).elo, 2300)


if __name__ == "__main__":
    unittest.main()
