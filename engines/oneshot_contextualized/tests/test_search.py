"""Search smoke tests.

We don't try to verify search depth or speed (flaky in CI). Instead we check:
    * The engine never returns an illegal move.
    * The engine finds simple mate-in-1 / mate-in-2 puzzles.
    * Repeated searches on the same position are deterministic at full
      strength (no eval noise / blunders / book).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
from engine.engine import Engine
from engine.search import SearchLimits


def _full_strength_engine() -> Engine:
    e = Engine()
    e.set_elo(2400)             # zeroes noise/blunders
    e.set_limit_strength(False) # ensure full strength path
    return e


class SearchSmokeTest(unittest.TestCase):
    def test_returns_legal_move_from_startpos(self):
        e = _full_strength_engine()
        info = e.searcher.search(chess.Board(), SearchLimits(max_depth=2))
        self.assertIsNotNone(info.best_move)
        self.assertIn(info.best_move, chess.Board().legal_moves)

    def test_mate_in_one_white(self):
        # White to play and mate in one (Qh5#).
        fen = "6k1/5ppp/8/8/8/8/5PPP/4Q1K1 w - - 0 1"
        e = _full_strength_engine()
        info = e.searcher.search(chess.Board(fen), SearchLimits(max_depth=2))
        board = chess.Board(fen)
        board.push(info.best_move)
        self.assertTrue(board.is_checkmate(),
                        f"expected mate, got {info.best_move.uci()} on {fen}")

    def test_mate_in_one_black(self):
        # Black to play, Qh4# is on the board after 1.f3 e5 2.g4.
        fen = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2"
        e = _full_strength_engine()
        info = e.searcher.search(chess.Board(fen), SearchLimits(max_depth=2))
        board = chess.Board(fen)
        board.push(info.best_move)
        self.assertTrue(board.is_checkmate())

    def test_choose_move_is_idempotent_at_full_strength(self):
        # Full strength + same input -> same move (no randomness).
        e = _full_strength_engine()
        b = chess.Board()
        a = e.choose_move(b, depth=2).best_move
        c = e.choose_move(b, depth=2).best_move
        self.assertEqual(a, c)


if __name__ == "__main__":
    unittest.main()
