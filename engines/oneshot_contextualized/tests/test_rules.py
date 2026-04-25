"""Rules and Game-wrapper tests."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
from engine.game import Game


class FENTest(unittest.TestCase):
    def test_round_trip(self):
        for fen in [
            chess.STARTING_FEN,
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
            "8/8/8/4k3/4P3/4K3/8/8 w - - 0 1",
        ]:
            with self.subTest(fen=fen):
                g = Game.from_fen(fen)
                self.assertEqual(g.fen, fen)


class CastlingTest(unittest.TestCase):
    def test_white_kingside(self):
        g = Game.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        g.push_uci("e1g1")
        self.assertEqual(g.fen.split()[0], "r3k2r/8/8/8/8/8/8/R4RK1")

    def test_black_queenside(self):
        g = Game.from_fen("r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1")
        g.push_uci("e8c8")
        self.assertEqual(g.fen.split()[0], "2kr3r/8/8/8/8/8/8/R3K2R")


class EnPassantTest(unittest.TestCase):
    def test_en_passant(self):
        g = Game.from_fen("rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3")
        g.push_uci("e5d6")  # ep capture
        # The d-pawn should be gone.
        self.assertEqual(g.board.piece_at(chess.D5), None)
        self.assertEqual(g.board.piece_at(chess.D6), chess.Piece(chess.PAWN, chess.WHITE))


class PromotionTest(unittest.TestCase):
    def test_underpromotion(self):
        g = Game.from_fen("8/P7/8/8/8/8/8/k1K5 w - - 0 1")
        g.push_uci("a7a8n")
        self.assertEqual(g.board.piece_at(chess.A8),
                         chess.Piece(chess.KNIGHT, chess.WHITE))


class TerminalTest(unittest.TestCase):
    def test_fools_mate(self):
        g = Game()
        for uci in ["f2f3", "e7e5", "g2g4", "d8h4"]:
            g.push_uci(uci)
        self.assertTrue(g.board.is_checkmate())
        self.assertEqual(g.result, "0-1")

    def test_stalemate(self):
        g = Game.from_fen("k7/2K5/1Q6/8/8/8/8/8 b - - 0 1")
        # Black has no legal moves and is not in check.
        self.assertTrue(g.board.is_stalemate())

    def test_insufficient_material(self):
        g = Game.from_fen("8/8/8/4k3/8/8/8/4K3 w - - 0 1")
        self.assertTrue(g.board.is_insufficient_material())


class UndoTest(unittest.TestCase):
    def test_undo_restores_state(self):
        g = Game()
        before = g.fen
        g.push_uci("e2e4")
        g.undo()
        self.assertEqual(g.fen, before)
        self.assertEqual(g.move_history, [])


class PGNTest(unittest.TestCase):
    def test_pgn_export(self):
        g = Game()
        for uci in ["e2e4", "e7e5", "g1f3"]:
            g.push_uci(uci)
        pgn = g.to_pgn()
        self.assertIn("1. e4 e5 2. Nf3", pgn)
        self.assertIn("[Event ", pgn)


if __name__ == "__main__":
    unittest.main()
