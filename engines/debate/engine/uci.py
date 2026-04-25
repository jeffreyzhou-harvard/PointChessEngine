"""UCI adapter. Reads commands from stdin, writes responses to stdout."""

from __future__ import annotations

import sys
import threading
from typing import Optional, TextIO

from .core import (
    EngineCore, CmdNewGame, CmdPosition, CmdGo, CmdStop, CmdQuit,
    CmdSetElo, CmdSetLimitStrength,
)
from .strength import configure


ENGINE_NAME = "CouncilEngine 1.0"
ENGINE_AUTHOR = "Claude (lead architect)"


def _writer(out: TextIO):
    def w(s: str) -> None:
        out.write(s + "\n")
        out.flush()
    return w


def parse_go(parts):
    """Parse 'go ...' arguments into a CmdGo."""
    args = parts[1:]
    cmd = CmdGo()
    i = 0
    while i < len(args):
        a = args[i]
        if a == "wtime" and i + 1 < len(args):
            cmd.wtime = int(args[i + 1]); i += 2
        elif a == "btime" and i + 1 < len(args):
            cmd.btime = int(args[i + 1]); i += 2
        elif a == "winc" and i + 1 < len(args):
            cmd.winc = int(args[i + 1]); i += 2
        elif a == "binc" and i + 1 < len(args):
            cmd.binc = int(args[i + 1]); i += 2
        elif a == "depth" and i + 1 < len(args):
            cmd.depth = int(args[i + 1]); i += 2
        elif a == "movetime" and i + 1 < len(args):
            cmd.movetime = int(args[i + 1]); i += 2
        elif a == "infinite":
            cmd.infinite = True; i += 1
        else:
            i += 1
    return cmd


def parse_position(parts):
    """Parse 'position [startpos | fen ...] [moves ...]'."""
    args = parts[1:]
    if not args:
        return CmdPosition()
    moves: list = []
    if args[0] == "startpos":
        from .board import STARTING_FEN
        fen = STARTING_FEN
        rest = args[1:]
    elif args[0] == "fen":
        # FEN is 6 fields
        if len(args) < 7:
            return CmdPosition()
        fen = " ".join(args[1:7])
        rest = args[7:]
    else:
        return CmdPosition()
    if rest and rest[0] == "moves":
        moves = rest[1:]
    return CmdPosition(fen=fen, moves=moves)


def parse_setoption(parts):
    """Parse 'setoption name X value Y'."""
    s = " ".join(parts)
    # crude but works
    name = ""
    value = ""
    if "name" in parts:
        ni = parts.index("name") + 1
        if "value" in parts:
            vi = parts.index("value")
            name = " ".join(parts[ni:vi]).strip()
            value = " ".join(parts[vi + 1:]).strip()
        else:
            name = " ".join(parts[ni:]).strip()
    return name, value


def handle_line(line: str, core: EngineCore, write) -> bool:
    """Handle one UCI line. Return False to terminate the loop."""
    line = line.strip()
    if not line:
        return True
    parts = line.split()
    cmd = parts[0]

    if cmd == "uci":
        write(f"id name {ENGINE_NAME}")
        write(f"id author {ENGINE_AUTHOR}")
        write("option name UCI_LimitStrength type check default false")
        write("option name UCI_Elo type spin default 2400 min 400 max 2400")
        write("uciok")
    elif cmd == "isready":
        write("readyok")
    elif cmd == "ucinewgame":
        core.submit(CmdNewGame())
    elif cmd == "position":
        core.submit(parse_position(parts))
    elif cmd == "go":
        core.submit(parse_go(parts))
    elif cmd == "stop":
        core.submit(CmdStop())
    elif cmd == "quit":
        core.submit(CmdStop())
        core.submit(CmdQuit())
        return False
    elif cmd == "setoption":
        name, value = parse_setoption(parts)
        nl = name.lower()
        if nl == "uci_elo":
            try:
                core.submit(CmdSetElo(int(value)))
            except ValueError:
                pass
        elif nl == "uci_limitstrength":
            core.submit(CmdSetLimitStrength(value.lower() in ("true", "1", "yes")))
    return True


def uci_loop(core: EngineCore, in_stream: Optional[TextIO] = None,
             out_stream: Optional[TextIO] = None) -> None:
    """Run the UCI input loop. Spawns a worker thread for the core."""
    if in_stream is None:
        in_stream = sys.stdin
    if out_stream is None:
        out_stream = sys.stdout
    try:
        out_stream.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass
    write = _writer(out_stream)

    # Hook the core's writers
    core._info_writer = write
    core._bestmove_writer = write

    worker = threading.Thread(target=core.run_forever, daemon=True)
    worker.start()

    for line in in_stream:
        if not handle_line(line, core, write):
            break

    core.submit(CmdQuit())
    worker.join(timeout=5.0)
