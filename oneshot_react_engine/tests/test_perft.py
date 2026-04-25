"""Perft tests verifying move generation against known node counts.

Reference: https://www.chessprogramming.org/Perft_Results
"""

import pytest

from oneshot_react_engine.core import Board


@pytest.mark.parametrize(
    "depth,expected",
    [
        (1, 20),
        (2, 400),
        (3, 8902),
    ],
)
def test_perft_starting_position(depth, expected):
    b = Board()
    assert b.perft(depth) == expected


@pytest.mark.parametrize(
    "depth,expected",
    [
        (1, 48),
        (2, 2039),
    ],
)
def test_perft_kiwipete(depth, expected):
    b = Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
    assert b.perft(depth) == expected


def test_perft_position_3_endgame():
    # "Position 3" from chessprogramming.org
    b = Board("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1")
    assert b.perft(1) == 14
    assert b.perft(2) == 191
    assert b.perft(3) == 2812


def test_perft_position_5():
    b = Board("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8")
    assert b.perft(1) == 44
    assert b.perft(2) == 1486
