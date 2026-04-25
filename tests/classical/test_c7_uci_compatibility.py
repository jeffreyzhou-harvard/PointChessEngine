"""C7.* tests for production UCI compatibility."""

from helpers import ClassicalTestCase, run_in_memory_uci


class TestC7_1Entrypoint(ClassicalTestCase):
    def test_uci_startup_banner_and_quit(self):
        output = run_in_memory_uci(["uci", "quit"])
        self.assertIn("id name PointChess", output)
        self.assertIn("uciok", output)


class TestC7_2CommandParser(ClassicalTestCase):
    def test_ready_newgame_and_unknown_command_do_not_crash(self):
        output = run_in_memory_uci(["unknown", "ucinewgame", "isready", "quit"])
        self.assertIn("readyok", output)


class TestC7_3PositionLoading(ClassicalTestCase):
    def test_position_startpos_moves_and_fen_are_accepted(self):
        output = run_in_memory_uci(
            [
                "position startpos moves e2e4 e7e5",
                "position fen rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
                "isready",
                "quit",
            ]
        )
        self.assertIn("readyok", output)


class TestC7_4GoDepth(ClassicalTestCase):
    def test_go_depth_returns_bestmove(self):
        output = run_in_memory_uci(["position startpos", "go depth 1", "quit"], timeout=2.0)
        self.assertIn("bestmove", output)


class TestC7_5GoMovetimeAndStop(ClassicalTestCase):
    def test_go_movetime_returns_bestmove(self):
        output = run_in_memory_uci(["position startpos", "go movetime 50", "quit"], timeout=2.0)
        self.assertIn("bestmove", output)


class TestC7_6OutputFormat(ClassicalTestCase):
    def test_info_and_bestmove_are_parseable(self):
        output = run_in_memory_uci(["position startpos", "go depth 1", "quit"], timeout=2.0)
        self.assertRegex(output, r"info .*nodes .*score cp -?\d+")
        bestmove_lines = [line for line in output.splitlines() if line.startswith("bestmove ")]
        self.assertEqual(len(bestmove_lines), 1)
        self.assertLegalUci(bestmove_lines[0].split()[1])


class TestC7_7ComplianceGate(ClassicalTestCase):
    def test_core_uci_compliance_transcript(self):
        output = run_in_memory_uci(
            [
                "uci",
                "isready",
                "ucinewgame",
                "position startpos moves e2e4 e7e5",
                "go depth 1",
                "quit",
            ],
            timeout=2.0,
        )
        self.assertIn("uciok", output)
        self.assertIn("readyok", output)
        self.assertIn("bestmove", output)
