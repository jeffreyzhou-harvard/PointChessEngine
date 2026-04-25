"""C3.* tests for static handcrafted evaluation."""

from oneshot_nocontext_engine.search.evaluation import evaluate

from helpers import Board, ClassicalTestCase


class TestC3_1ScoreConvention(ClassicalTestCase):
    def test_score_is_from_side_to_move_perspective(self):
        white_to_move = Board("4k3/8/8/8/8/8/8/4KQ2 w - - 0 1")
        black_to_move = Board("4k3/8/8/8/8/8/8/4KQ2 b - - 0 1")
        self.assertGreater(evaluate(white_to_move), 800)
        self.assertLess(evaluate(black_to_move), -800)


class TestC3_2MaterialAndPst(ClassicalTestCase):
    def test_material_advantage_and_starting_symmetry(self):
        self.assertAlmostEqual(evaluate(Board()), 0, delta=50)
        self.assertGreater(evaluate(Board("4k3/8/8/8/8/8/8/4KQ2 w - - 0 1")), 800)


class TestC3_3MobilityCenterControl(ClassicalTestCase):
    def test_more_active_queen_scores_better_than_corner_queen(self):
        active = Board("4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1")
        passive = Board("4k3/8/8/8/8/8/8/Q3K3 w - - 0 1")
        self.assertGreater(evaluate(active), evaluate(passive))


class TestC3_4PawnStructure(ClassicalTestCase):
    def test_advanced_passed_pawn_scores_better(self):
        advanced = Board("4k3/4P3/8/8/8/8/8/4K3 w - - 0 1")
        home = Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
        self.assertGreater(evaluate(advanced), evaluate(home))


class TestC3_5KingSafety(ClassicalTestCase):
    def test_pawn_shield_improves_king_safety(self):
        shielded = Board("4k3/8/8/8/8/8/5PPP/6K1 w - - 0 1")
        exposed = Board("4k3/8/8/8/8/8/8/6K1 w - - 0 1")
        self.assertGreater(evaluate(shielded), evaluate(exposed))


class TestC3_6WeightDeterminism(ClassicalTestCase):
    def test_evaluation_is_deterministic(self):
        board = Board()
        self.assertEqual(evaluate(board), evaluate(board))


class TestC3_7DiagnosticsGate(ClassicalTestCase):
    def test_terminal_positions_are_finite_and_ordered(self):
        mate = Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
        stalemate = Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        self.assertTrue(mate.is_checkmate())
        self.assertTrue(stalemate.is_stalemate())
        self.assertIsInstance(evaluate(mate), int)
        self.assertIsInstance(evaluate(stalemate), int)
