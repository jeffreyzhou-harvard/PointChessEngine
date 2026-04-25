"""UCI command-handling tests.

We drive the protocol with in-memory streams and assert on the lines
written to the output stream. We avoid `go` here so tests are fast and
deterministic; `go` is exercised indirectly by test_search.
"""

import io
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uci.protocol import UCIEngine


def _drive(commands):
    """Run UCIEngine over a list of input commands and return stdout text."""
    in_stream = io.StringIO("\n".join(commands) + "\nquit\n")
    out_stream = io.StringIO()
    UCIEngine(in_stream=in_stream, out_stream=out_stream).run()
    return out_stream.getvalue()


class UCITest(unittest.TestCase):
    def test_uci_handshake(self):
        out = _drive(["uci"])
        self.assertIn("id name ", out)
        self.assertIn("id author ", out)
        self.assertIn("uciok", out)
        # Required options.
        for opt in ["Hash", "UCI_LimitStrength", "UCI_Elo",
                    "Skill Level", "MultiPV"]:
            self.assertIn(f"option name {opt}", out)

    def test_isready(self):
        out = _drive(["uci", "isready"])
        self.assertIn("readyok", out)

    def test_position_startpos_moves(self):
        # Should not error.
        out = _drive([
            "uci",
            "isready",
            "ucinewgame",
            "position startpos moves e2e4 e7e5",
            "isready",
        ])
        # No "info string error" lines.
        self.assertNotIn("info string error", out)

    def test_position_fen(self):
        out = _drive([
            "uci",
            "position fen 8/8/8/4k3/8/8/8/4K3 w - - 0 1",
            "isready",
        ])
        self.assertNotIn("info string error", out)
        self.assertIn("readyok", out)

    def test_setoption_round_trip(self):
        out = _drive([
            "uci",
            "setoption name UCI_LimitStrength value true",
            "setoption name UCI_Elo value 1200",
            "setoption name Hash value 4",
            "setoption name MultiPV value 3",
            "isready",
        ])
        self.assertNotIn("info string error", out)
        self.assertIn("readyok", out)

    def test_go_depth_bestmove(self):
        # Run a tiny depth-limited search and require a bestmove line.
        in_stream = io.StringIO(
            "uci\n"
            "ucinewgame\n"
            "position startpos\n"
            "go depth 2\n"
            "isready\n"
            "quit\n"
        )
        out_stream = io.StringIO()
        engine = UCIEngine(in_stream=in_stream, out_stream=out_stream)
        engine.run()
        out = out_stream.getvalue()
        self.assertRegex(out, r"\nbestmove [a-h][1-8][a-h][1-8]")


if __name__ == "__main__":
    unittest.main()
