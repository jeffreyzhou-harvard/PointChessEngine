"""UCI command parser and dispatcher.

Implements the subset of UCI commands needed to plug the engine into a
GUI such as Cute Chess or Arena:

    uci, isready, ucinewgame, position, go, stop, quit, setoption

Configurable options exposed to the GUI:

    UCI_Elo (spin, 400..2400)   - playing strength
    Skill Level (spin, 0..20)   - alternative strength dial used by some GUIs
    Hash (spin, MB)             - transposition table cap (advisory only here)

The protocol layer runs the engine in a worker thread when ``go`` is issued
so the main thread can still process ``stop`` / ``quit`` while the engine
thinks.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import IO, Callable, List, Optional

from ..core.board import Board
from ..core.fen import STARTING_FEN
from ..core.move import Move
from ..engine.search import Engine, SearchInfo
from ..engine.strength import MAX_ELO, MIN_ELO, settings_for_elo


ID_NAME = "PointChess ReAct"
ID_AUTHOR = "PointChess ReAct Team"


def _skill_level_to_elo(skill: int) -> int:
    """Map UCI 'Skill Level' (0..20) to our ELO range."""
    skill = max(0, min(20, int(skill)))
    return int(MIN_ELO + (skill / 20.0) * (MAX_ELO - MIN_ELO))


class UCIProtocol:
    def __init__(
        self,
        out: Optional[Callable[[str], None]] = None,
        engine: Optional[Engine] = None,
    ) -> None:
        self._write = out if out is not None else self._default_write
        self.board = Board(STARTING_FEN)
        self.engine = engine if engine is not None else Engine(strength=settings_for_elo(1500))
        self._search_thread: Optional[threading.Thread] = None
        self._fixed_movetime_ms: Optional[int] = None
        self._fixed_depth: Optional[int] = None
        self._wtime: Optional[int] = None
        self._btime: Optional[int] = None

    # ------------------------------------------------------------------
    # Public API: feed lines

    def handle(self, line: str) -> bool:
        """Process one UCI input line.  Returns False if the engine should quit."""
        line = (line or "").strip()
        if not line:
            return True
        parts = line.split()
        cmd = parts[0]
        args = parts[1:]

        if cmd == "uci":
            self._cmd_uci()
        elif cmd == "isready":
            self._write("readyok")
        elif cmd == "ucinewgame":
            self.engine.reset()
            self.board = Board(STARTING_FEN)
        elif cmd == "position":
            self._cmd_position(args)
        elif cmd == "go":
            self._cmd_go(args)
        elif cmd == "stop":
            self._cmd_stop()
        elif cmd == "setoption":
            self._cmd_setoption(args)
        elif cmd == "quit":
            self._cmd_stop()
            return False
        elif cmd in ("d", "display"):
            self._write(str(self.board))
            self._write(f"FEN: {self.board.to_fen()}")
        # Unknown commands silently ignored per the UCI spec.
        return True

    # ------------------------------------------------------------------
    # Default IO

    @staticmethod
    def _default_write(s: str) -> None:
        sys.stdout.write(s + "\n")
        sys.stdout.flush()

    # ------------------------------------------------------------------
    # Command handlers

    def _cmd_uci(self) -> None:
        self._write(f"id name {ID_NAME}")
        self._write(f"id author {ID_AUTHOR}")
        self._write(
            f"option name UCI_Elo type spin default 1500 min {MIN_ELO} max {MAX_ELO}"
        )
        self._write("option name Skill Level type spin default 10 min 0 max 20")
        self._write("option name Hash type spin default 16 min 1 max 1024")
        self._write("uciok")

    def _cmd_position(self, args: List[str]) -> None:
        if not args:
            return
        if args[0] == "startpos":
            self.board = Board(STARTING_FEN)
            i = 1
        elif args[0] == "fen":
            # FEN is 6 tokens
            fen = " ".join(args[1:7])
            self.board = Board(fen)
            i = 7
        else:
            return

        if i < len(args) and args[i] == "moves":
            for uci_str in args[i + 1 :]:
                try:
                    move = Move.from_uci(uci_str)
                except Exception:
                    return
                if not self.board.make_move(move):
                    return

    def _cmd_setoption(self, args: List[str]) -> None:
        # Format: setoption name <name...> value <value>
        if "name" not in args or "value" not in args:
            return
        try:
            n_idx = args.index("name")
            v_idx = args.index("value")
        except ValueError:
            return
        name = " ".join(args[n_idx + 1 : v_idx]).strip()
        value = " ".join(args[v_idx + 1 :]).strip()
        lower = name.lower()
        if lower == "uci_elo":
            try:
                elo = int(value)
            except ValueError:
                return
            self.engine.set_elo(elo)
        elif lower == "skill level":
            try:
                skill = int(value)
            except ValueError:
                return
            self.engine.set_elo(_skill_level_to_elo(skill))
        elif lower == "hash":
            try:
                mb = int(value)
            except ValueError:
                return
            self.engine.tt.max_entries = max(1000, mb * 2000)

    def _cmd_go(self, args: List[str]) -> None:
        self._fixed_movetime_ms = None
        self._fixed_depth = None
        self._wtime = None
        self._btime = None
        winc = binc = 0

        i = 0
        while i < len(args):
            tok = args[i]
            if tok == "movetime" and i + 1 < len(args):
                self._fixed_movetime_ms = int(args[i + 1])
                i += 2
            elif tok == "depth" and i + 1 < len(args):
                self._fixed_depth = int(args[i + 1])
                i += 2
            elif tok == "wtime" and i + 1 < len(args):
                self._wtime = int(args[i + 1])
                i += 2
            elif tok == "btime" and i + 1 < len(args):
                self._btime = int(args[i + 1])
                i += 2
            elif tok == "winc" and i + 1 < len(args):
                winc = int(args[i + 1])
                i += 2
            elif tok == "binc" and i + 1 < len(args):
                binc = int(args[i + 1])
                i += 2
            elif tok == "infinite":
                i += 1
            else:
                i += 1

        movetime = self._compute_movetime(winc, binc)

        # Run the search in a background thread so we can still receive `stop`.
        self.engine._stop_requested = False

        def runner():
            def info_cb(info: SearchInfo) -> None:
                pv_str = " ".join(m.uci() for m in info.pv)
                msg = (
                    f"info depth {info.depth} nodes {info.nodes} time {info.elapsed_ms}"
                    f" nps {info.nps} score cp {info.score_cp}"
                )
                if pv_str:
                    msg += f" pv {pv_str}"
                self._write(msg)

            try:
                result = self.engine.search(
                    self.board,
                    movetime_ms=movetime,
                    max_depth=self._fixed_depth,
                    on_info=info_cb,
                )
            except Exception as exc:  # pragma: no cover - defensive
                self._write(f"info string error {exc}")
                self._write("bestmove 0000")
                return
            if result.best_move is None:
                self._write("bestmove 0000")
            else:
                self._write(f"bestmove {result.best_move.uci()}")

        self._search_thread = threading.Thread(target=runner, daemon=True)
        self._search_thread.start()

    def _cmd_stop(self) -> None:
        self.engine.request_stop()
        if self._search_thread is not None:
            self._search_thread.join(timeout=10.0)

    def _compute_movetime(self, winc: int, binc: int) -> Optional[int]:
        if self._fixed_movetime_ms is not None:
            return self._fixed_movetime_ms
        if self._fixed_depth is not None:
            return None  # depth-limited; no explicit time cap
        # Time controls: spend ~2.5% of remaining time + 50% of the increment
        remaining = self._wtime if self.board.turn.name == "WHITE" else self._btime
        if remaining is None:
            return self.engine.strength.movetime_ms or None
        inc = winc if self.board.turn.name == "WHITE" else binc
        return max(50, int(remaining * 0.025) + int(inc * 0.5))


def run_uci(stream_in: Optional[IO[str]] = None, stream_out: Optional[IO[str]] = None) -> None:
    """Run a blocking UCI loop.  Defaults to stdin/stdout."""
    stream_in = stream_in or sys.stdin
    stream_out = stream_out or sys.stdout

    def write(s: str) -> None:
        stream_out.write(s + "\n")
        stream_out.flush()

    proto = UCIProtocol(out=write)
    while True:
        line = stream_in.readline()
        if not line:
            break
        if not proto.handle(line):
            break
