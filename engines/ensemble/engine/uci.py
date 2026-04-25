"""Minimal UCI loop."""
from __future__ import annotations

import sys
import threading
from typing import IO, List, Optional

from .core import Engine, GoParams


def _format_info(info: dict) -> str:
    parts = ["info"]
    if "depth" in info: parts.append(f"depth {info['depth']}")
    if "score" in info: parts.append(f"score cp {info['score']}")
    if "nodes" in info: parts.append(f"nodes {info['nodes']}")
    pv = info.get("pv")
    if pv: parts.append("pv " + " ".join(pv))
    return " ".join(parts)


def run_uci(stream_in: IO = None, stream_out: IO = None) -> None:
    if stream_in is None: stream_in = sys.stdin
    if stream_out is None: stream_out = sys.stdout

    def out(line: str) -> None:
        stream_out.write(line + "\n")
        stream_out.flush()

    engine = Engine()

    for raw in stream_in:
        line = raw.strip()
        if not line:
            continue
        toks = line.split()
        cmd = toks[0]
        if cmd == "uci":
            out("id name PyChess")
            out("id author Ensemble")
            out("option name UCI_Elo type spin default 2400 min 400 max 2400")
            out("option name Seed type string default 0")
            out("uciok")
        elif cmd == "isready":
            out("readyok")
        elif cmd == "ucinewgame":
            engine.new_game()
        elif cmd == "setoption":
            # setoption name X value Y
            try:
                name_idx = toks.index("name")
                value_idx = toks.index("value")
                name = " ".join(toks[name_idx + 1:value_idx])
                value = " ".join(toks[value_idx + 1:])
            except ValueError:
                continue
            if name == "UCI_Elo":
                try:
                    engine.set_elo(int(value))
                except ValueError:
                    pass
            elif name == "Seed":
                try:
                    s = int(value)
                    engine.set_seed(s if s != 0 else None)
                except ValueError:
                    pass
        elif cmd == "position":
            # position [startpos | fen <FEN>] [moves m1 m2 ...]
            fen: Optional[str] = None
            moves: List[str] = []
            i = 1
            if i < len(toks) and toks[i] == "startpos":
                fen = "startpos"
                i += 1
            elif i < len(toks) and toks[i] == "fen":
                fen_parts = toks[i + 1:i + 7]
                fen = " ".join(fen_parts)
                i += 7
            if i < len(toks) and toks[i] == "moves":
                moves = toks[i + 1:]
            engine.set_position(fen, moves)
        elif cmd == "go":
            params = GoParams()
            i = 1
            while i < len(toks):
                t = toks[i]
                if t == "depth": params.depth = int(toks[i + 1]); i += 2
                elif t == "movetime": params.movetime = int(toks[i + 1]); i += 2
                elif t == "wtime": params.wtime = int(toks[i + 1]); i += 2
                elif t == "btime": params.btime = int(toks[i + 1]); i += 2
                elif t == "winc": params.winc = int(toks[i + 1]); i += 2
                elif t == "binc": params.binc = int(toks[i + 1]); i += 2
                elif t == "nodes": params.nodes = int(toks[i + 1]); i += 2
                elif t == "infinite": params.infinite = True; i += 1
                else: i += 1

            def on_info(info):
                out(_format_info(info))

            def on_best(mv, res):
                if mv is None:
                    out("bestmove 0000")
                else:
                    out(f"bestmove {mv.uci()}")
            engine.go(params, on_bestmove=on_best, on_info=on_info)
        elif cmd == "stop":
            engine.stop()
            # If a worker had been running, on_bestmove already printed.
        elif cmd == "quit":
            engine.quit()
            return
        # ignore unknown commands silently per UCI spec.
