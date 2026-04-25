"""EngineCore tests."""

import threading
import time

from engine.core import (
    EngineCore, CmdNewGame, CmdPosition, CmdGo, CmdStop, CmdQuit,
    CmdSetElo, CmdMakeUserMove, CmdSetSeed,
)


def _start_core():
    c = EngineCore()
    t = threading.Thread(target=c.run_forever, daemon=True)
    t.start()
    return c, t


def _stop_core(c, t):
    c.submit(CmdQuit())
    t.join(timeout=5)


def _wait_for(predicate, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_core_initial_snapshot():
    c, t = _start_core()
    try:
        snap = c.snapshot()
        assert snap["turn"] == "white"
        assert len(snap["legal_moves"]) == 20
        assert snap["search_active"] is False
        assert snap["game_over"] is False
    finally:
        _stop_core(c, t)


def test_core_position_and_user_move():
    c, t = _start_core()
    try:
        c.submit(CmdNewGame())
        c.submit(CmdMakeUserMove("e2e4"))
        assert _wait_for(lambda: c.snapshot()["turn"] == "black")
        snap = c.snapshot()
        assert "e2" not in snap["fen"].split()[0]  # rough check
    finally:
        _stop_core(c, t)


def test_core_go_returns_bestmove():
    c, t = _start_core()
    try:
        c.submit(CmdSetElo(2000))
        c.submit(CmdNewGame())
        c.submit(CmdGo(movetime=300))
        assert _wait_for(lambda: c.snapshot()["last_bestmove"] is not None,
                         timeout=10.0)
        snap = c.snapshot()
        assert snap["last_bestmove"] is not None
        assert len(snap["last_bestmove"]) >= 4
    finally:
        _stop_core(c, t)


def test_core_stop_aborts():
    c, t = _start_core()
    try:
        c.submit(CmdSetElo(2400))
        c.submit(CmdNewGame())
        c.submit(CmdGo(movetime=10000))
        time.sleep(0.1)
        c.submit(CmdStop())
        assert _wait_for(lambda: c.snapshot()["search_active"] is False,
                         timeout=5.0)
    finally:
        _stop_core(c, t)


def test_core_game_over_detection():
    c, t = _start_core()
    try:
        # Fool's mate: 1.f3 e5 2.g4 Qh4#
        c.submit(CmdPosition(
            fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            moves=["f2f3", "e7e5", "g2g4", "d8h4"]
        ))
        assert _wait_for(lambda: c.snapshot()["game_over"] is True, timeout=5.0)
        snap = c.snapshot()
        assert snap["result"] == "black_mates"
    finally:
        _stop_core(c, t)
