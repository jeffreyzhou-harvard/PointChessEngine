import io
import threading

from engine.uci import run_uci


def _run(commands):
    inp = io.StringIO("\n".join(commands) + "\n")
    out = io.StringIO()
    run_uci(inp, out)
    return out.getvalue()


def test_uci_handshake():
    out = _run(["uci", "isready", "quit"])
    assert "id name PyChess" in out
    assert "uciok" in out
    assert "readyok" in out


def test_uci_setoption_elo():
    out = _run(["uci", "setoption name UCI_Elo value 800", "isready", "quit"])
    assert "readyok" in out


def test_uci_position_and_go_depth():
    cmds = [
        "uci",
        "ucinewgame",
        "position startpos",
        "go depth 2",
        # `go` is async; wait via isready (but UCI loop processes commands sequentially
        # so isready after go will respond before bestmove is ready). To force completion,
        # use 'stop' then 'isready' won't help — we need to busy-wait.
    ]
    inp = io.StringIO("\n".join(cmds) + "\n")
    out = io.StringIO()
    # Run in a thread; after starting go, wait until "bestmove" appears in output.
    t = threading.Thread(target=run_uci, args=(inp, out))
    t.start()
    # Wait up to 10 s for bestmove.
    import time
    for _ in range(200):
        if "bestmove" in out.getvalue():
            break
        time.sleep(0.05)
    # Now feed quit by appending? StringIO is exhausted; the loop already exited or is blocked.
    # Since input ends after `go depth 2`, the loop will exit once stdin EOF reached.
    t.join(timeout=10.0)
    assert "bestmove" in out.getvalue(), out.getvalue()


def test_uci_position_with_moves():
    cmds = [
        "uci",
        "position startpos moves e2e4 e7e5",
        "isready",
        "quit",
    ]
    out = _run(cmds)
    assert "readyok" in out
