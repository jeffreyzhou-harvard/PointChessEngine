"""Perft (performance test) suite.

Perft is the *gold standard* for chess move-generation correctness.
``perft(position, depth)`` counts the number of leaf nodes reachable
in a full legal-move tree of the given depth. Every chess engine
has reference perft numbers for a small set of canonical positions;
matching those numbers is necessary (though not sufficient) for the
engine to be considered correct on:

  - simple piece moves
  - captures (including all victim/attacker pairings)
  - castling (kingside, queenside, blocked, through-check, after rook
    capture, after rook/king move)
  - en passant (including the diagonal-pin and discovered-check
    edge cases that trip naive implementations)
  - promotion (all four pieces, capture-promotions)
  - check evasion (single check, double check, king move only)
  - pinned-piece move filtering
  - mate / stalemate detection (zero-leaf branches)

A divergence in any of those would change the leaf count. So matching
perft to depth 4-5 across these six positions essentially certifies
the rule layer.

Reference values
----------------

These numbers are the published Chess Programming Wiki values
(https://www.chessprogramming.org/Perft_Results) and are *not* up
for negotiation; if a value here changes the engine has a bug.

Test selection / runtime
------------------------

Pure-Python movegen is slow (~100k nodes/sec). We pick depths to
keep the always-on suite under ~10 seconds wall-clock total:

  - all 6 positions to a "fast" depth (1-2 sec each)
  - one extra "medium" depth (~7-10 sec) gated behind the
    ``slow`` marker; opt in with ``pytest --runslow``.

Where to look when this file fails
----------------------------------

If a single position fails, run :func:`_perft_divide` interactively
on that position. It returns ``{root_move_uci: subtree_count}``;
diff against published divided-perft tables (also on the wiki) and
the offending move(s) point at the buggy generator.
"""

from __future__ import annotations

import pytest

from engines.chainofthought.core.board import Board
from engines.chainofthought.core.fen import parse_fen


# ---------------------------------------------------------------------------
# Standard reference positions.
#
# Tuple shape: (label, FEN, {depth: expected_leaf_count}).
# Depths beyond what we exercise are kept here as documentation.
# ---------------------------------------------------------------------------

POSITIONS: list[tuple[str, str, dict[int, int]]] = [
    (
        "startpos",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        {1: 20, 2: 400, 3: 8902, 4: 197281, 5: 4865609},
    ),
    (
        "kiwipete",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        {1: 48, 2: 2039, 3: 97862, 4: 4085603},
    ),
    (
        "pos3",  # endgame; lots of EP & promotion tactics
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
        {1: 14, 2: 191, 3: 2812, 4: 43238, 5: 674624},
    ),
    (
        "pos4",  # promotion + checks
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
        {1: 6, 2: 264, 3: 9467, 4: 422333},
    ),
    (
        "pos5",  # "Mirror" of pos4 (different setup); standard reference
        "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
        {1: 44, 2: 1486, 3: 62379, 4: 2103487},
    ),
    (
        "pos6",
        "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",
        {1: 46, 2: 2079, 3: 89890, 4: 3894594},
    ),
]


def _by_label(label: str) -> tuple[str, dict[int, int]]:
    for n, fen, expected in POSITIONS:
        if n == label:
            return fen, expected
    raise KeyError(label)


# ---------------------------------------------------------------------------
# perft helpers
# ---------------------------------------------------------------------------


def _perft(board: Board, depth: int) -> int:
    """Number of leaf nodes in the legal-move tree of ``board``."""
    if depth == 0:
        return 1
    total = 0
    for move in board.legal_moves():
        board.make_move(move)
        total += _perft(board, depth - 1)
        board.unmake_move()
    return total


def _perft_divide(board: Board, depth: int) -> dict[str, int]:
    """``{root_move_uci: leaves_below_it}``.

    Test suite doesn't strictly need this, but having it next to the
    failing position is essential when debugging a perft mismatch.
    """
    if depth <= 0:
        return {}
    out: dict[str, int] = {}
    for move in board.legal_moves():
        board.make_move(move)
        out[move.uci()] = _perft(board, depth - 1)
        board.unmake_move()
    return out


# ---------------------------------------------------------------------------
# 1. Always-on perft battery (~5-10 sec total)
# ---------------------------------------------------------------------------


# (label, depth) pairs. Picked so each takes < ~3s and the whole
# battery completes in well under 10s on a laptop.
ALWAYS_ON_CASES: list[tuple[str, int]] = [
    ("startpos", 1),
    ("startpos", 2),
    ("startpos", 3),
    ("startpos", 4),    # ~2s
    ("kiwipete", 1),
    ("kiwipete", 2),
    ("kiwipete", 3),    # ~1s
    ("pos3",     1),
    ("pos3",     2),
    ("pos3",     3),
    ("pos3",     4),    # ~0.5s
    ("pos4",     1),
    ("pos4",     2),
    ("pos4",     3),    # ~0.1s
    ("pos5",     1),
    ("pos5",     2),
    ("pos5",     3),    # ~0.6s
    ("pos6",     1),
    ("pos6",     2),
    ("pos6",     3),    # ~0.7s
]


@pytest.mark.parametrize(
    "label,depth", ALWAYS_ON_CASES,
    ids=[f"{lbl}-d{d}" for lbl, d in ALWAYS_ON_CASES],
)
def test_perft_matches_reference(label: str, depth: int) -> None:
    fen, expected = _by_label(label)
    board = parse_fen(fen)
    actual = _perft(board, depth)
    assert actual == expected[depth], (
        f"perft({label}, depth={depth}) = {actual}, "
        f"expected {expected[depth]}. Run "
        f"_perft_divide(parse_fen({fen!r}), {depth}) and diff "
        f"against the published divided-perft for this position."
    )


# ---------------------------------------------------------------------------
# 2. Slow / deep perft (--runslow)
# ---------------------------------------------------------------------------


SLOW_CASES: list[tuple[str, int]] = [
    ("startpos", 5),    # ~40s
    ("kiwipete", 4),    # ~30-40s; exercises the full tactical zoo
    ("pos3",     5),    # ~7s
    ("pos5",     4),    # ~15s
]


@pytest.mark.slow
@pytest.mark.parametrize(
    "label,depth", SLOW_CASES,
    ids=[f"{lbl}-d{d}" for lbl, d in SLOW_CASES],
)
def test_perft_deep(label: str, depth: int) -> None:
    fen, expected = _by_label(label)
    board = parse_fen(fen)
    actual = _perft(board, depth)
    assert actual == expected[depth], (
        f"deep perft({label}, depth={depth}) = {actual}, "
        f"expected {expected[depth]}"
    )


# ---------------------------------------------------------------------------
# 3. Self-consistency: divided perft sums to total
#
# Sanity check on _perft_divide itself, but also a useful guard
# against subtle "the iteration order matters" bugs in legal_moves.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,depth",
    [("kiwipete", 2), ("pos3", 3), ("startpos", 3)],
)
def test_divided_perft_sums_to_total(label: str, depth: int) -> None:
    fen, expected = _by_label(label)
    board = parse_fen(fen)
    divided = _perft_divide(board, depth)
    assert sum(divided.values()) == expected[depth]
    # Each root move must produce a non-negative count; zero is
    # legal (mating sequence) but negative is a bug.
    assert all(v >= 0 for v in divided.values())


# ---------------------------------------------------------------------------
# 4. Make / unmake invariant via the perft tree
#
# After EVERY ``unmake_move`` the board's ``position_key()`` and
# ``fen()`` must be byte-identical to what they were before the
# corresponding ``make_move``. We walk a small perft tree and check
# this at every node. This catches:
#   - castling rights or EP square not restored on unmake
#   - halfmove / fullmove counter drift
#   - captured-piece restoration bugs
# ---------------------------------------------------------------------------


def _walk_invariants(board: Board, depth: int) -> int:
    """Walk the legal tree, asserting state restoration.

    Returns the number of nodes visited so the caller can assert it
    actually walked something.
    """
    if depth == 0:
        return 1
    visited = 1
    snapshot_key = board.position_key()
    snapshot_fen = board.fen()
    for move in board.legal_moves():
        board.make_move(move)
        visited += _walk_invariants(board, depth - 1)
        board.unmake_move()
        # Both the cheap key and the canonical FEN must match.
        assert board.position_key() == snapshot_key, (
            f"position_key drift after {move.uci()} from {snapshot_fen}"
        )
        assert board.fen() == snapshot_fen, (
            f"FEN drift after {move.uci()}: "
            f"{board.fen()!r} != {snapshot_fen!r}"
        )
    return visited


@pytest.mark.parametrize("label,depth", [
    ("startpos", 3),
    ("kiwipete", 2),
    ("pos3",     3),
    ("pos4",     2),
    ("pos5",     2),
])
def test_make_unmake_state_invariant(label: str, depth: int) -> None:
    fen, _ = _by_label(label)
    board = parse_fen(fen)
    visited = _walk_invariants(board, depth)
    assert visited > 1


# ---------------------------------------------------------------------------
# 5. FEN round-trip survives the whole tree
#
# parse(serialize(b)) must reproduce ``b`` for every position visited
# inside a perft tree -- not just for the canonical reference FENs.
# Catches FEN serializer bugs in rare sub-positions (after EP, after
# promotion, after castling rights drop, etc.).
# ---------------------------------------------------------------------------


def _walk_fen_roundtrip(board: Board, depth: int) -> int:
    if depth == 0:
        return 1
    visited = 1
    for move in board.legal_moves():
        board.make_move(move)
        # parse(serialize(...)) should produce a board with the same
        # FEN. We don't require Board.__eq__ because legal_moves
        # comparison would cost more than the test saves.
        roundtripped = parse_fen(board.fen())
        assert roundtripped.fen() == board.fen()
        visited += _walk_fen_roundtrip(board, depth - 1)
        board.unmake_move()
    return visited


@pytest.mark.parametrize("label,depth", [
    ("startpos", 2),
    ("kiwipete", 2),
    ("pos3",     2),
    ("pos4",     2),
])
def test_fen_roundtrip_across_perft_tree(label: str, depth: int) -> None:
    fen, _ = _by_label(label)
    board = parse_fen(fen)
    visited = _walk_fen_roundtrip(board, depth)
    assert visited > 1
