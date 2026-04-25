from __future__ import annotations

import io

import chess

from engines.rlm.uci import run_uci


def _run_uci_script(script: str) -> list[str]:
    output = io.StringIO()
    run_uci(io.StringIO(script), output)
    return [line.strip() for line in output.getvalue().splitlines() if line.strip()]


def test_uci_handshake() -> None:
    lines = _run_uci_script("uci\nisready\nquit\n")

    assert "uciok" in lines
    assert "readyok" in lines
    assert any(line.startswith("id name PointChess RLM") for line in lines)


def test_go_depth_returns_legal_bestmove_from_startpos() -> None:
    lines = _run_uci_script("uci\nposition startpos\ngo depth 1\nquit\n")
    bestmove = next(line.split()[1] for line in lines if line.startswith("bestmove "))

    assert chess.Move.from_uci(bestmove) in chess.Board().legal_moves


def test_position_startpos_moves_is_accepted() -> None:
    lines = _run_uci_script("position startpos moves e2e4 e7e5\ngo depth 1\nquit\n")

    assert any(line.startswith("bestmove ") for line in lines)


def test_position_fen_is_accepted() -> None:
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    lines = _run_uci_script(f"position fen {fen}\ngo movetime 50\nquit\n")

    assert any(line.startswith("bestmove ") for line in lines)
