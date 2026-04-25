"""UCI protocol layer.

Implements just enough UCI to run inside CuteChess, Arena, c-chess-cli, or
any other UCI-compatible host. Commands supported:

    uci, isready, ucinewgame, quit
    position [startpos | fen <FEN>] [moves ...]
    go [depth N] [movetime MS]
       [wtime MS btime MS [winc MS] [binc MS] [movestogo N]]
       [infinite]
    stop

Options:
    Hash             (spin, 1..1024, default 16)
    UCI_LimitStrength (check, default false)
    UCI_Elo          (spin, 400..2400, default 1500)
    Skill Level      (spin, 0..20, default 20)
    MoveOverhead     (spin, 0..5000, default 30)
    MultiPV          (spin, 1..10, default 1)
    Threads          (spin, 1..1, default 1)   # single-threaded engine

Search runs in a worker thread so `stop` and `isready` are responsive.
"""

from __future__ import annotations

import sys
import threading
from typing import IO, List, Optional

import chess

from engine.engine import Engine
from engine.search import MATE, SearchInfo


ENGINE_NAME = "ContextualizedEngine 0.1"
ENGINE_AUTHOR = "PointChessEngine project"


def _format_score(info: SearchInfo) -> str:
    if info.mate_in is not None:
        return f"mate {info.mate_in}"
    return f"cp {info.score_cp}"


def _format_pv(info: SearchInfo) -> str:
    return " ".join(m.uci() for m in info.pv)


class UCIEngine:
    def __init__(self, in_stream: Optional[IO[str]] = None,
                 out_stream: Optional[IO[str]] = None):
        self.in_stream = in_stream or sys.stdin
        self.out_stream = out_stream or sys.stdout
        self.engine = Engine()
        self.board = chess.Board()
        self._search_thread: Optional[threading.Thread] = None

        # Options
        self.hash_mb = 16
        self.move_overhead_ms = 30
        self.multipv = 1
        self.skill_level = 20
        self.uci_elo = 1500
        self.limit_strength = False

    # ---- main loop -----------------------------------------------------

    def run(self) -> None:
        for line in self.in_stream:
            line = line.strip()
            if not line:
                continue
            try:
                if not self._handle(line):
                    break
            except Exception as e:  # noqa: BLE001
                self._send(f"info string error {e}")

    def _handle(self, line: str) -> bool:
        """Returns False to terminate the loop."""
        tokens = line.split()
        cmd = tokens[0]

        if cmd == "uci":
            self._cmd_uci()
        elif cmd == "isready":
            self._send("readyok")
        elif cmd == "ucinewgame":
            self._stop_search()
            self.engine.new_game()
            self.board = chess.Board()
        elif cmd == "setoption":
            self._cmd_setoption(tokens[1:])
        elif cmd == "position":
            self._cmd_position(tokens[1:])
        elif cmd == "go":
            self._cmd_go(tokens[1:])
        elif cmd == "stop":
            self._stop_search()
        elif cmd == "ponderhit":
            pass  # not implemented; ignored
        elif cmd == "quit":
            self._stop_search()
            return False
        elif cmd == "d":  # debug aid: print the board
            self._send(f"info string\n{self.board}")
        else:
            self._send(f"info string unknown command: {cmd}")
        return True

    # ---- output --------------------------------------------------------

    def _send(self, msg: str) -> None:
        self.out_stream.write(msg + "\n")
        self.out_stream.flush()

    # ---- command handlers ----------------------------------------------

    def _cmd_uci(self) -> None:
        self._send(f"id name {ENGINE_NAME}")
        self._send(f"id author {ENGINE_AUTHOR}")
        self._send("option name Hash type spin default 16 min 1 max 1024")
        self._send("option name UCI_LimitStrength type check default false")
        self._send("option name UCI_Elo type spin default 1500 min 400 max 2400")
        self._send("option name Skill Level type spin default 20 min 0 max 20")
        self._send("option name MoveOverhead type spin default 30 min 0 max 5000")
        self._send("option name MultiPV type spin default 1 min 1 max 10")
        self._send("option name Threads type spin default 1 min 1 max 1")
        self._send("uciok")

    def _cmd_setoption(self, tokens: List[str]) -> None:
        # Format: name <NAME...> value <VALUE>
        if "name" not in tokens:
            return
        name_idx = tokens.index("name") + 1
        value_idx = tokens.index("value") if "value" in tokens else len(tokens)
        name = " ".join(tokens[name_idx:value_idx])
        value = " ".join(tokens[value_idx + 1:]) if value_idx < len(tokens) else ""

        try:
            if name == "Hash":
                self.hash_mb = int(value)
                self.engine.set_hash_mb(self.hash_mb)
            elif name == "UCI_LimitStrength":
                self.limit_strength = value.lower() == "true"
                self.engine.set_limit_strength(self.limit_strength)
                if self.limit_strength:
                    self.engine.set_elo(self.uci_elo)
            elif name == "UCI_Elo":
                self.uci_elo = int(value)
                if self.limit_strength:
                    self.engine.set_elo(self.uci_elo)
            elif name == "Skill Level":
                self.skill_level = int(value)
                self.engine.set_skill_level(self.skill_level)
                # Skill Level being touched implies the user wants weaker.
                self.engine.set_limit_strength(self.skill_level < 20)
            elif name == "MoveOverhead":
                self.move_overhead_ms = max(0, int(value))
            elif name == "MultiPV":
                self.multipv = max(1, min(10, int(value)))
            elif name == "Threads":
                pass  # always 1
            else:
                self._send(f"info string unknown option: {name}")
        except ValueError:
            self._send(f"info string bad value for {name}: {value!r}")

    def _cmd_position(self, tokens: List[str]) -> None:
        if not tokens:
            return
        i = 0
        if tokens[i] == "startpos":
            self.board = chess.Board()
            i += 1
        elif tokens[i] == "fen":
            # The FEN is the next 6 tokens.
            fen = " ".join(tokens[i + 1:i + 7])
            self.board = chess.Board(fen)
            i += 7
        else:
            return

        if i < len(tokens) and tokens[i] == "moves":
            for uci in tokens[i + 1:]:
                move = chess.Move.from_uci(uci)
                if move in self.board.legal_moves:
                    self.board.push(move)
                else:
                    self._send(f"info string illegal move in position: {uci}")
                    break

    def _cmd_go(self, tokens: List[str]) -> None:
        self._stop_search()  # cancel any in-flight search

        depth: Optional[int] = None
        movetime: Optional[int] = None
        wtime = btime = winc = binc = movestogo = None
        infinite = False

        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t == "depth" and i + 1 < len(tokens):
                depth = int(tokens[i + 1]); i += 2
            elif t == "movetime" and i + 1 < len(tokens):
                movetime = int(tokens[i + 1]); i += 2
            elif t == "wtime" and i + 1 < len(tokens):
                wtime = int(tokens[i + 1]); i += 2
            elif t == "btime" and i + 1 < len(tokens):
                btime = int(tokens[i + 1]); i += 2
            elif t == "winc" and i + 1 < len(tokens):
                winc = int(tokens[i + 1]); i += 2
            elif t == "binc" and i + 1 < len(tokens):
                binc = int(tokens[i + 1]); i += 2
            elif t == "movestogo" and i + 1 < len(tokens):
                movestogo = int(tokens[i + 1]); i += 2
            elif t == "infinite":
                infinite = True; i += 1
            else:
                i += 1

        # Time budget calculation.
        time_ms: Optional[int] = movetime
        if time_ms is None and not infinite and (wtime is not None or btime is not None):
            stm_time = wtime if self.board.turn == chess.WHITE else btime
            stm_inc = (winc if self.board.turn == chess.WHITE else binc) or 0
            if stm_time is not None:
                # Conservative: time / (movestogo or 30) + 80% of increment.
                slots = movestogo if movestogo and movestogo > 0 else 30
                time_ms = max(20, stm_time // slots + (stm_inc * 4) // 5
                              - self.move_overhead_ms)

        if infinite:
            time_ms = None
            depth = depth if depth is not None else 64

        # Run the search in a worker so we can answer `stop` and `isready`.
        self._search_thread = threading.Thread(
            target=self._search_worker,
            args=(time_ms, depth),
            daemon=True,
        )
        self._search_thread.start()

    def _search_worker(self, time_ms: Optional[int], depth: Optional[int]) -> None:
        def info_cb(info: SearchInfo) -> None:
            score = _format_score(info)
            pv = _format_pv(info)
            nps = (info.nodes * 1000 // info.time_ms) if info.time_ms else 0
            self._send(
                f"info depth {info.depth} seldepth {info.seldepth} "
                f"score {score} nodes {info.nodes} nps {nps} "
                f"time {info.time_ms} pv {pv}"
            )

        info = self.engine.choose_move(
            self.board, time_ms=time_ms, depth=depth, info_callback=info_cb,
        )

        if info.best_move is None:
            # No legal moves; report a null move so the host doesn't hang.
            self._send("bestmove 0000")
        else:
            self._send(f"bestmove {info.best_move.uci()}")

    def _stop_search(self) -> None:
        self.engine.stop()
        t = self._search_thread
        if t is not None:
            t.join(timeout=2.0)
            self._search_thread = None
