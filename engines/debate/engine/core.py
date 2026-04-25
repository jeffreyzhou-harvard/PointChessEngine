"""EngineCore: singleton owning the board, search thread, and state snapshot.

Mutation flows through `cmd_queue`. Reads flow through `snapshot()` which returns
a deep-copied dict guarded by `_snapshot_lock`. A stop is signalled via
`stop_event`.
"""

from __future__ import annotations

import copy
import queue
import random
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Callable

from .board import Board, Move, STARTING_FEN, move_uci, move_from_uci
from .movegen import generate_legal_moves, in_check
from .search import iterative_deepening, select_strength_move, MATE
from .tt import TranspositionTable
from .strength import configure, StrengthConfig


# --- Command types --------------------------------------------------------

@dataclass
class CmdNewGame:
    pass


@dataclass
class CmdPosition:
    fen: str = STARTING_FEN
    moves: List[str] = field(default_factory=list)


@dataclass
class CmdGo:
    wtime: Optional[int] = None
    btime: Optional[int] = None
    winc: Optional[int] = None
    binc: Optional[int] = None
    depth: Optional[int] = None
    movetime: Optional[int] = None
    infinite: bool = False


@dataclass
class CmdStop:
    pass


@dataclass
class CmdQuit:
    pass


@dataclass
class CmdSetElo:
    elo: int


@dataclass
class CmdSetLimitStrength:
    enabled: bool


@dataclass
class CmdMakeUserMove:
    """UI-driven move from human player; applied to the position."""
    uci: str


@dataclass
class CmdSetSeed:
    seed: int


# --- EngineCore -----------------------------------------------------------

class EngineCore:
    def __init__(self, info_writer: Optional[Callable[[str], None]] = None,
                 bestmove_writer: Optional[Callable[[str], None]] = None):
        self.cmd_queue: "queue.Queue" = queue.Queue()
        self.stop_event = threading.Event()
        self.search_thread: Optional[threading.Thread] = None

        self.board: Board = Board.starting_position()
        self.tt = TranspositionTable()
        self.config: StrengthConfig = configure(2400, limit_strength=False)
        self.rng = random.Random()

        self._snapshot_lock = threading.RLock()
        self._snapshot: dict = {}
        self._update_snapshot(initial=True)

        self._running = False
        self._info_writer = info_writer
        self._bestmove_writer = bestmove_writer

        # Last bestmove (for snapshot)
        self._last_bestmove: Optional[str] = None

    # --- public API -----------------------------------------------------

    def submit(self, cmd) -> None:
        self.cmd_queue.put(cmd)

    def snapshot(self) -> dict:
        with self._snapshot_lock:
            return copy.deepcopy(self._snapshot)

    def run_forever(self) -> None:
        """Drain the command queue. Blocks until CmdQuit."""
        self._running = True
        while self._running:
            try:
                cmd = self.cmd_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            self._handle(cmd)

    def shutdown(self) -> None:
        self._stop_search(join=True)
        self._running = False

    # --- snapshot helpers ----------------------------------------------

    def _update_snapshot(self, initial: bool = False, **fields) -> None:
        with self._snapshot_lock:
            if initial:
                legal = generate_legal_moves(self.board, self.board.side_to_move)
                self._snapshot = {
                    "fen": self.board.to_fen(),
                    "turn": "white" if self.board.side_to_move == 0 else "black",
                    "legal_moves": [move_uci(m) for m in legal],
                    "last_bestmove": None,
                    "search_active": False,
                    "depth": 0,
                    "score_cp": 0,
                    "pv": [],
                    "elo": self.config.elo,
                    "limit_strength": self.config.limit_strength,
                    "in_check": in_check(self.board, self.board.side_to_move),
                    "game_over": False,
                    "result": None,
                }
            else:
                # update with full board state if asked
                if fields.get("refresh_board", False):
                    legal = generate_legal_moves(self.board, self.board.side_to_move)
                    self._snapshot["fen"] = self.board.to_fen()
                    self._snapshot["turn"] = "white" if self.board.side_to_move == 0 else "black"
                    self._snapshot["legal_moves"] = [move_uci(m) for m in legal]
                    self._snapshot["in_check"] = in_check(self.board, self.board.side_to_move)
                    # Game-over detection
                    if not legal:
                        if self._snapshot["in_check"]:
                            winner = "black" if self.board.side_to_move == 0 else "white"
                            self._snapshot["game_over"] = True
                            self._snapshot["result"] = f"{winner}_mates"
                        else:
                            self._snapshot["game_over"] = True
                            self._snapshot["result"] = "stalemate"
                    elif self.board.is_fifty_move_draw():
                        self._snapshot["game_over"] = True
                        self._snapshot["result"] = "fifty_move_draw"
                    elif self.board.is_repetition(3):
                        self._snapshot["game_over"] = True
                        self._snapshot["result"] = "threefold_repetition"
                    elif self.board.has_insufficient_material():
                        self._snapshot["game_over"] = True
                        self._snapshot["result"] = "insufficient_material"
                    else:
                        self._snapshot["game_over"] = False
                        self._snapshot["result"] = None
                for k, v in fields.items():
                    if k == "refresh_board":
                        continue
                    self._snapshot[k] = v
                self._snapshot["elo"] = self.config.elo
                self._snapshot["limit_strength"] = self.config.limit_strength

    # --- command handlers ----------------------------------------------

    def _handle(self, cmd) -> None:
        if isinstance(cmd, CmdQuit):
            self.shutdown()
        elif isinstance(cmd, CmdNewGame):
            self._stop_search(join=True)
            self.board = Board.starting_position()
            self.tt.clear()
            self._last_bestmove = None
            self._update_snapshot(refresh_board=True, last_bestmove=None,
                                  search_active=False, depth=0, score_cp=0, pv=[])
        elif isinstance(cmd, CmdPosition):
            self._stop_search(join=True)
            try:
                self.board = Board.from_fen(cmd.fen)
            except Exception:
                self.board = Board.starting_position()
            for u in cmd.moves:
                m = move_from_uci(self.board, u)
                if m is None:
                    break
                self.board.make_move(m)
            self._update_snapshot(refresh_board=True)
        elif isinstance(cmd, CmdGo):
            self._stop_search(join=True)
            self._launch_search(cmd)
        elif isinstance(cmd, CmdStop):
            self._stop_search(join=True)
        elif isinstance(cmd, CmdSetElo):
            self.config = configure(cmd.elo, limit_strength=self.config.limit_strength)
            self._update_snapshot()
        elif isinstance(cmd, CmdSetLimitStrength):
            self.config = configure(self.config.elo, limit_strength=cmd.enabled)
            self._update_snapshot()
        elif isinstance(cmd, CmdSetSeed):
            self.rng = random.Random(cmd.seed)
        elif isinstance(cmd, CmdMakeUserMove):
            m = move_from_uci(self.board, cmd.uci)
            if m is not None:
                self.board.make_move(m)
                self._update_snapshot(refresh_board=True)

    def _launch_search(self, cmd: CmdGo) -> None:
        self.stop_event = threading.Event()
        self._update_snapshot(search_active=True)

        def _info_cb(depth, score, nodes, elapsed_ms, best):
            pv = [move_uci(best)] if best is not None else []
            self._update_snapshot(depth=depth, score_cp=score, pv=pv,
                                  search_active=True)
            if self._info_writer:
                ms = max(1, int(elapsed_ms))
                nps = int(nodes * 1000 / ms)
                pv_str = " ".join(pv)
                line = (f"info depth {depth} score cp {score} nodes {nodes} "
                        f"nps {nps} time {ms} pv {pv_str}")
                try:
                    self._info_writer(line)
                except Exception:
                    pass

        def _worker():
            # Determine time budget
            cfg = self.config
            hard_time = None
            if cmd.movetime is not None:
                hard_time = int(cmd.movetime)
            elif cmd.wtime is not None or cmd.btime is not None:
                # crude: use side-to-move clock / 30 capped by cfg.hard_time_ms
                clock = cmd.wtime if self.board.side_to_move == 0 else cmd.btime
                if clock is not None:
                    hard_time = max(50, clock // 30)
            else:
                if cfg.limit_strength:
                    hard_time = cfg.hard_time_ms
                else:
                    hard_time = 5000

            max_depth = cmd.depth if cmd.depth is not None else (
                cfg.max_depth if cfg.limit_strength else 10
            )

            try:
                best, score, results = iterative_deepening(
                    self.board,
                    time_limit_ms=hard_time,
                    max_depth=max_depth,
                    stop_event=self.stop_event,
                    tt=self.tt,
                    config=cfg,
                    rng=self.rng,
                    info_callback=_info_cb,
                )
                chosen = select_strength_move(self.board, results, cfg, rng=self.rng) or best
            except Exception:
                chosen = None
                score = 0

            uci = move_uci(chosen) if chosen is not None else "0000"
            self._last_bestmove = uci
            self._update_snapshot(search_active=False, last_bestmove=uci, score_cp=score)
            if self._bestmove_writer:
                try:
                    self._bestmove_writer(f"bestmove {uci}")
                except Exception:
                    pass

        self.search_thread = threading.Thread(target=_worker, daemon=True)
        self.search_thread.start()

    def _stop_search(self, join: bool = True) -> None:
        if self.search_thread is not None and self.search_thread.is_alive():
            self.stop_event.set()
            if join:
                self.search_thread.join(timeout=10.0)
        self.search_thread = None
        self._update_snapshot(search_active=False)
