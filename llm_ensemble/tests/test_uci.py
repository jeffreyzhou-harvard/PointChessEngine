"""Tests for the LLM Ensemble UCI protocol layer.

Uses mock ensemble engine and mock LLM clients — no real API calls.
"""

import sys
import os
import io
import threading
import time
import unittest
from typing import List
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from llm_ensemble.uci.protocol import UCIProtocol


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_protocol(lines: List[str]) -> List[str]:
    """Feed ``lines`` to a UCIProtocol and collect all output."""
    output: List[str] = []

    # Patch EnsembleEngine to avoid real LLM calls
    with patch('llm_ensemble.uci.protocol.EnsembleEngine') as MockEng:
        mock_engine_instance = MagicMock()
        MockEng.return_value = mock_engine_instance

        proto = UCIProtocol(out=output.append)
        # Inject the mock engine immediately so _get_engine() returns it
        proto._engine = mock_engine_instance

        for line in lines:
            if not proto.handle(line):
                break

    return output


# ---------------------------------------------------------------------------
# Tests: UCI handshake
# ---------------------------------------------------------------------------

class TestUCIHandshake(unittest.TestCase):
    def test_uci_command_produces_id_and_uciok(self):
        out = _run_protocol(["uci"])
        self.assertTrue(any("id name" in l for l in out), out)
        self.assertTrue(any("id author" in l for l in out), out)
        self.assertIn("uciok", out)

    def test_uci_exposes_elo_option(self):
        out = _run_protocol(["uci"])
        self.assertTrue(any("UCI_Elo" in l for l in out), out)

    def test_uci_exposes_voting_method_option(self):
        out = _run_protocol(["uci"])
        self.assertTrue(any("VotingMethod" in l for l in out), out)

    def test_uci_exposes_candidates_option(self):
        out = _run_protocol(["uci"])
        self.assertTrue(any("Candidates" in l for l in out), out)

    def test_isready_produces_readyok(self):
        out = _run_protocol(["uci", "isready"])
        self.assertIn("readyok", out)

    def test_quit_returns_false(self):
        output = []
        with patch('llm_ensemble.uci.protocol.EnsembleEngine'):
            proto = UCIProtocol(out=output.append)
            result = proto.handle("quit")
        self.assertFalse(result)

    def test_unknown_command_ignored(self):
        """Unknown commands should not crash or produce error output."""
        out = _run_protocol(["gobbledygook"])
        # Should be no output (UCI spec: ignore unknown commands)
        self.assertEqual(out, [])


# ---------------------------------------------------------------------------
# Tests: setoption
# ---------------------------------------------------------------------------

class TestSetOption(unittest.TestCase):
    def _proto(self):
        out = []
        with patch('llm_ensemble.uci.protocol.EnsembleEngine') as MockEng:
            mock_instance = MagicMock()
            MockEng.return_value = mock_instance
            proto = UCIProtocol(out=out.append)
            proto._engine = mock_instance
        return proto, out

    def test_setoption_uci_elo(self):
        proto, _ = self._proto()
        proto.handle("setoption name UCI_Elo value 1200")
        self.assertEqual(proto._elo, 1200)

    def test_setoption_elo_clamps_to_min(self):
        proto, _ = self._proto()
        proto.handle("setoption name UCI_Elo value 100")
        self.assertEqual(proto._elo, 400)

    def test_setoption_elo_clamps_to_max(self):
        proto, _ = self._proto()
        proto.handle("setoption name UCI_Elo value 9999")
        self.assertEqual(proto._elo, 2400)

    def test_setoption_skill_level(self):
        proto, _ = self._proto()
        proto.handle("setoption name Skill Level value 0")
        self.assertEqual(proto._elo, 400)
        proto.handle("setoption name Skill Level value 20")
        self.assertEqual(proto._elo, 2400)

    def test_setoption_voting_method(self):
        proto, _ = self._proto()
        proto.handle("setoption name VotingMethod value score_weighted")
        self.assertEqual(proto._voting_method, "score_weighted")

    def test_setoption_candidates(self):
        proto, _ = self._proto()
        proto.handle("setoption name Candidates value 8")
        self.assertEqual(proto._num_candidates, 8)

    def test_setoption_vote_timeout(self):
        proto, _ = self._proto()
        proto.handle("setoption name VoteTimeout value 60")
        self.assertAlmostEqual(proto._vote_timeout, 60.0)


# ---------------------------------------------------------------------------
# Tests: position parsing
# ---------------------------------------------------------------------------

class TestPositionParsing(unittest.TestCase):
    def _proto(self):
        with patch('llm_ensemble.uci.protocol.EnsembleEngine'):
            proto = UCIProtocol(out=lambda l: None)
            proto._engine = MagicMock()
        return proto

    def test_startpos_loads_starting_fen(self):
        proto = self._proto()
        proto.handle("position startpos")
        fen = proto.board.to_fen()
        self.assertIn("rnbqkbnr", fen)
        self.assertIn("PPPPPPPP", fen)

    def test_startpos_with_moves(self):
        proto = self._proto()
        proto.handle("position startpos moves e2e4")
        fen = proto.board.to_fen()
        # After e2e4, e4 pawn should be on rank 4
        self.assertIn(" b ", fen)  # Black to move

    def test_fen_position(self):
        proto = self._proto()
        kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        proto.handle(f"position fen {kiwipete}")
        self.assertEqual(proto.board.to_fen().split()[0], kiwipete.split()[0])

    def test_ucinewgame_resets_board(self):
        proto = self._proto()
        proto.handle("position startpos moves e2e4")
        proto.handle("ucinewgame")
        fen = proto.board.to_fen()
        # Board should be back to starting position
        self.assertIn("rnbqkbnr/pppppppp", fen)


# ---------------------------------------------------------------------------
# Tests: ELO settings mapping
# ---------------------------------------------------------------------------

class TestEloSettings(unittest.TestCase):
    def test_elo_settings_400(self):
        from llm_ensemble.ensemble.engine import elo_settings
        s = elo_settings(400)
        self.assertLessEqual(s.max_depth, 3)
        self.assertGreater(s.noise_cp, 0)
        self.assertGreater(s.blunder_pct, 0)

    def test_elo_settings_2400(self):
        from llm_ensemble.ensemble.engine import elo_settings
        s = elo_settings(2400)
        self.assertGreaterEqual(s.max_depth, 5)
        self.assertEqual(s.noise_cp, 0)
        self.assertLess(s.blunder_pct, 1.0)

    def test_elo_settings_monotone_depth(self):
        from llm_ensemble.ensemble.engine import elo_settings
        prev = None
        for elo in [400, 800, 1200, 1600, 2000, 2400]:
            s = elo_settings(elo)
            if prev is not None:
                self.assertGreaterEqual(s.max_depth, prev.max_depth)
            prev = s

    def test_elo_settings_monotone_noise_decreasing(self):
        from llm_ensemble.ensemble.engine import elo_settings
        prev = None
        for elo in [400, 800, 1200, 1600, 2000, 2400]:
            s = elo_settings(elo)
            if prev is not None:
                self.assertLessEqual(s.noise_cp, prev.noise_cp)
            prev = s

    def test_elo_clamped_below_400(self):
        from llm_ensemble.ensemble.engine import elo_settings
        s = elo_settings(100)
        self.assertEqual(s.elo, 400)

    def test_elo_clamped_above_2400(self):
        from llm_ensemble.ensemble.engine import elo_settings
        s = elo_settings(9999)
        self.assertEqual(s.elo, 2400)


if __name__ == "__main__":
    unittest.main()
