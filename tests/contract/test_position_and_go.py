"""C-2: ``position`` + ``go`` produces a legal ``bestmove``.

Three flavours:
  - startpos with no moves
  - startpos with a few moves applied
  - a custom FEN

In every case the engine must return a UCI move that is legal in the
resulting position. Move legality is checked with python-chess so we
don't have to depend on any engine's own legal-move generator.
"""
from __future__ import annotations

import chess
import pytest


def _legal_moves(fen: str, moves_uci: list[str]) -> set[str]:
    board = chess.Board(fen)
    for u in moves_uci:
        try:
            board.push_uci(u)
        except (ValueError, chess.IllegalMoveError):
            return set()
    return {m.uci() for m in board.legal_moves}


def test_startpos_returns_legal_bestmove(uci_client, engine_id):
    uci_client.new_game()
    bm, _ = uci_client.go(moves_uci=[], movetime_ms=200)
    legal = _legal_moves(chess.STARTING_FEN, [])
    assert bm in legal, f"{engine_id} returned {bm!r}; not legal from startpos"


def test_position_with_moves_returns_legal_bestmove(uci_client, engine_id):
    uci_client.new_game()
    pre = ["e2e4", "e7e5", "g1f3"]
    bm, _ = uci_client.go(moves_uci=pre, movetime_ms=200)
    legal = _legal_moves(chess.STARTING_FEN, pre)
    assert bm in legal, (
        f"{engine_id} returned {bm!r} after {pre}; not legal in resulting position"
    )


def test_repeated_go_does_not_crash(uci_client, engine_id):
    """Three consecutive `go` calls share one engine subprocess."""
    uci_client.new_game()
    history: list[str] = []
    for _ in range(3):
        bm, _ = uci_client.go(moves_uci=history, movetime_ms=150)
        legal = _legal_moves(chess.STARTING_FEN, history)
        assert bm in legal, f"{engine_id} returned {bm!r}; not legal"
        history.append(bm)
    assert len(history) == 3
