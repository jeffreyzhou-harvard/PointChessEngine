"""UCI adapter tests using io.StringIO streams."""

import io
import threading
import time

from engine.core import EngineCore
from engine.uci import handle_line, uci_loop, parse_go, parse_position


def test_parse_position_startpos():
    cmd = parse_position(["position", "startpos"])
    assert cmd.fen.startswith("rnbqkbnr")
    assert cmd.moves == []


def test_parse_position_startpos_with_moves():
    cmd = parse_position(["position", "startpos", "moves", "e2e4", "e7e5"])
    assert cmd.moves == ["e2e4", "e7e5"]


def test_parse_position_fen():
    fen = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
    parts = ["position", "fen"] + fen.split() + ["moves", "e1e2"]
    cmd = parse_position(parts)
    assert cmd.fen == fen
    assert cmd.moves == ["e1e2"]


def test_parse_go_movetime():
    cmd = parse_go(["go", "movetime", "1000"])
    assert cmd.movetime == 1000


def test_parse_go_clocks_and_depth():
    cmd = parse_go(["go", "wtime", "5000", "btime", "5000", "depth", "5"])
    assert cmd.wtime == 5000
    assert cmd.btime == 5000
    assert cmd.depth == 5


def test_uci_handshake():
    out_lines = []
    def w(s):
        out_lines.append(s)
    core = EngineCore()
    handle_line("uci", core, w)
    text = "\n".join(out_lines)
    assert "id name" in text
    assert "uciok" in text
    assert "UCI_Elo" in text


def test_uci_isready():
    out_lines = []
    def w(s): out_lines.append(s)
    core = EngineCore()
    handle_line("isready", core, w)
    assert "readyok" in out_lines


def test_uci_full_loop_bestmove():
    """Drive the UCI loop end-to-end with stdin/stdout streams."""
    inp = io.StringIO(
        "uci\n"
        "isready\n"
        "ucinewgame\n"
        "position startpos\n"
        "setoption name UCI_LimitStrength value true\n"
        "setoption name UCI_Elo value 1600\n"
        "go movetime 200\n"
    )
    out = io.StringIO()
    core = EngineCore()

    def run():
        uci_loop(core, in_stream=inp, out_stream=out)

    th = threading.Thread(target=run, daemon=True)
    th.start()
    # Wait for bestmove
    end = time.monotonic() + 8.0
    while time.monotonic() < end:
        if "bestmove" in out.getvalue():
            break
        time.sleep(0.05)
    # Trigger quit by closing stdin (StringIO is exhausted; loop ends).
    th.join(timeout=2.0)
    text = out.getvalue()
    assert "uciok" in text
    assert "readyok" in text
    assert "bestmove" in text
