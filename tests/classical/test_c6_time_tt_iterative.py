"""C6.* tests for time management, iterative deepening, and transposition table."""

import time

from engines.oneshot_nocontext.search.engine import Engine, TT_ALPHA, TT_BETA, TT_EXACT, TTEntry

from helpers import Board, ClassicalTestCase, legal_uci_moves, run_in_memory_uci


class TestC6_1TimeControlModel(ClassicalTestCase):
    def test_search_accepts_depth_and_time_limits(self):
        board = Board()
        move, _ = Engine(elo=2400).search(board, max_depth=1, time_limit=0.2)
        self.assertIn(move.uci(), legal_uci_moves(board))


class TestC6_2IterativeDeepening(ClassicalTestCase):
    def test_more_time_allows_nonzero_search_statistics(self):
        engine = Engine(elo=2400)
        engine.search(Board(), max_depth=3, time_limit=1.0)
        self.assertGreater(engine.nodes_searched, 0)


class TestC6_3SearchInterruption(ClassicalTestCase):
    def test_movetime_returns_within_tolerance(self):
        board = Board()
        start = time.monotonic()
        move, _ = Engine(elo=2400).search(board, max_depth=5, time_limit=0.05)
        elapsed = time.monotonic() - start
        self.assertIn(move.uci(), legal_uci_moves(board))
        self.assertLess(elapsed, 1.0)


class TestC6_4TranspositionTable(ClassicalTestCase):
    def test_tt_entries_store_depth_score_flag_and_best_move(self):
        board = Board()
        move = board.legal_moves()[0]
        entry = TTEntry(board.to_fen(), 2, 10, TT_EXACT, move)
        self.assertEqual(entry.depth, 2)
        self.assertEqual(entry.score, 10)
        self.assertIn(entry.flag, {TT_EXACT, TT_ALPHA, TT_BETA})
        self.assertEqual(entry.best_move, move)


class TestC6_5TimedDiagnostics(ClassicalTestCase):
    def test_engine_info_reports_nodes_time_and_nps(self):
        engine = Engine(elo=2400)
        engine.search(Board(), max_depth=2, time_limit=1.0)
        info = engine.get_info()
        self.assertGreater(info["nodes"], 0)
        self.assertGreaterEqual(info["time_ms"], 0)
        self.assertGreaterEqual(info["nps"], 0)


class TestC6_6TimedComparisonGate(ClassicalTestCase):
    def test_uci_movetime_smoke_returns_bestmove(self):
        output = run_in_memory_uci(["position startpos", "go movetime 50", "quit"], timeout=2.0)
        self.assertIn("bestmove", output)
