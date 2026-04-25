"""Perft tests.

Reference node counts come from the chessprogramming wiki's "Perft Results"
page (one of the supplied context sources). We only run shallow depths to
keep CI runtime tolerable; the python-chess library is the move generator,
so what we're really verifying is that we hand it positions correctly.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess


def perft(board: chess.Board, depth: int) -> int:
    if depth == 0:
        return 1
    n = 0
    for move in board.legal_moves:
        board.push(move)
        n += perft(board, depth - 1)
        board.pop()
    return n


# (name, fen, expected per-depth list starting at depth 1)
PERFT_CASES = [
    ("startpos",
     chess.STARTING_FEN,
     [20, 400, 8902, 197281]),
    ("kiwipete",
     "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
     [48, 2039, 97862]),
    ("position3",
     "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
     [14, 191, 2812, 43238]),
    ("position4_mirrored",
     # The chessprogramming wiki's "Position 4" perft values (6/264/9467)
     # are for the mirrored FEN; the unmirrored partner gives different
     # numbers despite being equivalent up to color symmetry on paper.
     "r2q1rk1/pP1p2pp/Q4n2/bbp1p3/Np6/1B3NBn/pPPP1PPP/R3K2R b KQ - 0 1",
     [6, 264, 9467]),
    ("position5",
     "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
     [44, 1486, 62379]),
]


class PerftTest(unittest.TestCase):
    def test_perft(self):
        for name, fen, depths in PERFT_CASES:
            for d, expected in enumerate(depths, start=1):
                with self.subTest(position=name, depth=d):
                    board = chess.Board(fen)
                    self.assertEqual(perft(board, d), expected,
                                     f"perft mismatch at {name} d={d}")


if __name__ == "__main__":
    unittest.main()
