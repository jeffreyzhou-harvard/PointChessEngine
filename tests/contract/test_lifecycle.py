"""C-4: ucinewgame is idempotent and resets enough state to be usable.

After ``ucinewgame`` the engine must accept ``position startpos`` and
``go`` again; it must not retain any move history that would cause it
to reject the new starting position.
"""
from __future__ import annotations

import chess


def _legal_from_startpos() -> set[str]:
    return {m.uci() for m in chess.Board().legal_moves}


def test_ucinewgame_between_searches_works(uci_client, engine_id):
    uci_client.new_game()
    bm1, _ = uci_client.go(moves_uci=[], movetime_ms=150)
    assert bm1 in _legal_from_startpos()

    # Reset, search again - same position, must still get a legal move.
    uci_client.new_game()
    bm2, _ = uci_client.go(moves_uci=[], movetime_ms=150)
    assert bm2 in _legal_from_startpos()


def test_ucinewgame_then_position_with_moves(uci_client, engine_id):
    """After a reset, supplying a new move history must work."""
    uci_client.new_game()
    pre = ["d2d4", "d7d5"]
    bm, _ = uci_client.go(moves_uci=pre, movetime_ms=150)
    board = chess.Board()
    for u in pre:
        board.push_uci(u)
    legal = {m.uci() for m in board.legal_moves}
    assert bm in legal, f"{engine_id}: {bm!r} illegal after {pre} from a fresh game"
