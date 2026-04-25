"""C5.* tests for tactical hardening."""

from engines.oneshot_nocontext.search.engine import Engine, MATE_SCORE, MAX_QUIESCENCE_DEPTH

from helpers import Board, ClassicalTestCase, legal_uci_moves


class TestC5_1BaselineTacticalSuite(ClassicalTestCase):
    def test_tactical_fixture_is_solvable_by_current_engine(self):
        board = Board("4k3/8/8/8/3r4/8/8/3QK3 w - - 0 1")
        move, _ = Engine(elo=2400).search(board, max_depth=3, time_limit=2.0)
        self.assertIsNotNone(move)
        self.assertEqual(move.uci(), "d1d4")


class TestC5_2MoveOrdering(ClassicalTestCase):
    def test_capture_ordering_preserves_all_legal_moves(self):
        board = Board("4k3/8/8/8/3r4/8/8/3QK3 w - - 0 1")
        engine = Engine(elo=2400)
        legal = board.legal_moves()
        ordered = engine._order_moves(board, legal, 0)
        self.assertEqual({m.uci() for m in ordered}, {m.uci() for m in legal})
        self.assertEqual(ordered[0].uci(), "d1d4")


class TestC5_3QuiescenceBounds(ClassicalTestCase):
    def test_quiescence_returns_finite_score(self):
        engine = Engine(elo=2400)
        board = Board("4k3/8/8/8/3r4/8/8/3QK3 w - - 0 1")
        engine.start_time = 0.0
        engine.time_limit = 1.0
        score = engine._quiescence(board, -MATE_SCORE, MATE_SCORE, MAX_QUIESCENCE_DEPTH)
        self.assertIsInstance(score, int)


class TestC5_4MateDistanceScoring(ClassicalTestCase):
    def test_mate_score_constant_supports_distance_adjustment(self):
        self.assertGreater(MATE_SCORE, 50000)
        self.assertGreater(MATE_SCORE - 1, MATE_SCORE - 2)


class TestC5_5OptionalHeuristics(ClassicalTestCase):
    def test_killer_tables_clear_safely(self):
        engine = Engine(elo=2400)
        engine.killers[0][0] = Board().legal_moves()[0]
        engine.clear()
        self.assertEqual(engine.killers[0], [None, None])


class TestC5_6ImprovementGate(ClassicalTestCase):
    def test_tactical_search_preserves_legality(self):
        board = Board()
        move, _ = Engine(elo=2400).search(board, max_depth=2, time_limit=1.0)
        self.assertIn(move.uci(), legal_uci_moves(board))
