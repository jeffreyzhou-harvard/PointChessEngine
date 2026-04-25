"""UCI command parser and dispatcher for the LLM Ensemble engine.

Implements the standard UCI subset:
    uci, isready, ucinewgame, position, go, stop, setoption, quit

Exposed UCI options:
    UCI_Elo         spin 400..2400    — playing strength
    Skill Level     spin 0..20        — alternative strength dial
    VotingMethod    combo             — plurality | score_weighted | consensus
    Candidates      spin 1..15        — number of candidates shown to LLMs
    VoteTimeout     spin 5..120       — seconds to wait for LLM votes
"""

from __future__ import annotations

import sys
import threading
from typing import Callable, List, Optional

from ..ensemble.engine import EnsembleEngine, EloSettings, elo_settings
from ..config import (
    DEFAULT_ELO,
    DEFAULT_VOTING_METHOD,
    DEFAULT_CANDIDATES,
    VOTE_TIMEOUT_SECONDS,
    VOTING_METHOD_PLURALITY,
    VOTING_METHOD_SCORE_WEIGHTED,
    VOTING_METHOD_CONSENSUS,
)

ID_NAME = "PointChess Ensemble"
ID_AUTHOR = "PointChess Ensemble Team"

MIN_ELO = 400
MAX_ELO = 2400


def _skill_to_elo(skill: int) -> int:
    skill = max(0, min(20, skill))
    return int(MIN_ELO + (skill / 20.0) * (MAX_ELO - MIN_ELO))


class UCIProtocol:
    """Drives the EnsembleEngine via UCI stdin/stdout."""

    def __init__(
        self,
        out: Optional[Callable[[str], None]] = None,
        engine: Optional[EnsembleEngine] = None,
    ) -> None:
        self._write = out if out is not None else self._default_write
        self._engine = engine  # lazy-init on first use to avoid slow import at startup
        self._elo = DEFAULT_ELO
        self._voting_method = DEFAULT_VOTING_METHOD
        self._vote_timeout = VOTE_TIMEOUT_SECONDS
        self._num_candidates = DEFAULT_CANDIDATES
        self._search_thread: Optional[threading.Thread] = None
        self._fixed_movetime_ms: Optional[int] = None
        self._fixed_depth: Optional[int] = None
        self._wtime: Optional[int] = None
        self._btime: Optional[int] = None

        # Board from the react engine core
        from oneshot_react_engine.core.board import Board
        from oneshot_react_engine.core.fen import STARTING_FEN
        self._Board = Board
        self._STARTING_FEN = STARTING_FEN
        self.board = Board(STARTING_FEN)

    @staticmethod
    def _default_write(line: str) -> None:
        print(line, flush=True)

    def _get_engine(self) -> EnsembleEngine:
        if self._engine is None:
            self._engine = EnsembleEngine(
                elo=self._elo,
                voting_method=self._voting_method,
                vote_timeout=self._vote_timeout,
            )
        return self._engine

    # ------------------------------------------------------------------
    # Main dispatch loop

    def handle(self, line: str) -> bool:
        """Process one UCI input line.  Returns False if engine should quit."""
        line = (line or "").strip()
        if not line:
            return True
        parts = line.split()
        cmd = parts[0]
        args = parts[1:]

        if cmd == "uci":
            self._cmd_uci()
        elif cmd == "isready":
            self._get_engine()  # trigger init
            self._write("readyok")
        elif cmd == "ucinewgame":
            self._get_engine().reset()
            self.board = self._Board(self._STARTING_FEN)
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
        # ignore unknown commands per UCI spec
        return True

    def run_loop(self, inp=None) -> None:
        """Read UCI commands from ``inp`` (defaults to sys.stdin)."""
        stream = inp or sys.stdin
        for raw_line in stream:
            if not self.handle(raw_line):
                break

    # ------------------------------------------------------------------
    # Command handlers

    def _cmd_uci(self) -> None:
        self._write(f"id name {ID_NAME}")
        self._write(f"id author {ID_AUTHOR}")
        self._write(f"option name UCI_Elo type spin default {DEFAULT_ELO} min {MIN_ELO} max {MAX_ELO}")
        self._write("option name Skill Level type spin default 10 min 0 max 20")
        self._write(
            f"option name VotingMethod type combo default {DEFAULT_VOTING_METHOD} "
            f"var {VOTING_METHOD_PLURALITY} "
            f"var {VOTING_METHOD_SCORE_WEIGHTED} "
            f"var {VOTING_METHOD_CONSENSUS}"
        )
        self._write(f"option name Candidates type spin default {DEFAULT_CANDIDATES} min 1 max 15")
        self._write(f"option name VoteTimeout type spin default {int(VOTE_TIMEOUT_SECONDS)} min 5 max 120")
        self._write("uciok")

    def _cmd_setoption(self, args: List[str]) -> None:
        # setoption name <Name> value <Value>
        if len(args) < 4 or args[0].lower() != "name":
            return
        try:
            val_idx = next(i for i, a in enumerate(args) if a.lower() == "value")
        except StopIteration:
            return
        name = " ".join(args[1:val_idx]).strip()
        value = " ".join(args[val_idx + 1:]).strip()

        if name.lower() == "uci_elo":
            self._elo = max(MIN_ELO, min(MAX_ELO, int(value)))
            if self._engine:
                self._engine.set_elo(self._elo)
        elif name.lower() == "skill level":
            self._elo = _skill_to_elo(int(value))
            if self._engine:
                self._engine.set_elo(self._elo)
        elif name.lower() == "votingmethod":
            self._voting_method = value
            if self._engine:
                self._engine._voting_method = value
        elif name.lower() == "candidates":
            self._num_candidates = max(1, min(15, int(value)))
            if self._engine:
                self._engine._settings.num_candidates = self._num_candidates
        elif name.lower() == "votetimeout":
            self._vote_timeout = max(5.0, min(120.0, float(value)))
            if self._engine:
                self._engine._vote_timeout = self._vote_timeout

    def _cmd_position(self, args: List[str]) -> None:
        from oneshot_react_engine.core.move import Move
        if not args:
            return
        if args[0] == "startpos":
            self.board = self._Board(self._STARTING_FEN)
            moves_start = 2 if len(args) > 1 and args[1] == "moves" else len(args)
        elif args[0] == "fen":
            # FEN ends at "moves" keyword or end of args
            fen_parts = []
            i = 1
            while i < len(args) and args[i] != "moves":
                fen_parts.append(args[i])
                i += 1
            fen = " ".join(fen_parts)
            self.board = self._Board(fen)
            moves_start = i + 1 if i < len(args) else len(args)
        else:
            return

        # Apply move sequence
        for uci in args[moves_start:]:
            legal = self.board.legal_moves()
            matched = next((m for m in legal if m.uci() == uci), None)
            if matched is None:
                break
            self.board._make_move_internal(matched)

    def _cmd_go(self, args: List[str]) -> None:
        self._parse_go_args(args)
        engine = self._get_engine()

        def _search():
            board_copy = self._Board(self.board.to_fen())
            # Replay move history is encoded in FEN; board_copy is authoritative

            from oneshot_react_engine.engine.search import SearchInfo

            def on_info(info: SearchInfo) -> None:
                pv_str = " ".join(m.uci() for m in info.pv)
                self._write(
                    f"info depth {info.depth} nodes {info.nodes} "
                    f"score cp {info.score_cp} "
                    f"time {info.elapsed_ms} nps {info.nps} "
                    f"pv {pv_str}"
                )

            try:
                result = engine.search_and_choose(
                    board_copy,
                    movetime_ms=self._fixed_movetime_ms,
                    max_depth=self._fixed_depth,
                    on_info=on_info,
                )
                # Emit voting summary as info strings
                tally = result.vote_tally
                for mv, cnt in tally.vote_counts.items():
                    self._write(f"info string vote {mv} {cnt}")
                if tally.fallback_used:
                    self._write(f"info string fallback {tally.fallback_reason}")
                self._write(f"bestmove {result.chosen_move}")
            except Exception as exc:  # noqa: BLE001
                self._write(f"info string error {exc}")
                # Emit a random legal move as emergency fallback
                legal = board_copy.legal_moves()
                if legal:
                    self._write(f"bestmove {legal[0].uci()}")

        self._search_thread = threading.Thread(target=_search, daemon=True)
        self._search_thread.start()

    def _cmd_stop(self) -> None:
        if self._engine:
            self._engine.request_stop()
        if self._search_thread and self._search_thread.is_alive():
            self._search_thread.join(timeout=2.0)

    def _parse_go_args(self, args: List[str]) -> None:
        self._fixed_movetime_ms = None
        self._fixed_depth = None
        self._wtime = None
        self._btime = None

        i = 0
        while i < len(args):
            tok = args[i].lower()
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
            elif tok == "infinite":
                self._fixed_movetime_ms = None
                self._fixed_depth = None
                i += 1
            else:
                i += 1

        # Time management: use wtime/btime if movetime not set
        if self._fixed_movetime_ms is None and self._fixed_depth is None:
            from oneshot_react_engine.core.pieces import Color
            remaining = self._wtime if self.board.turn.name == "WHITE" else self._btime
            if remaining is not None:
                self._fixed_movetime_ms = max(500, remaining // 30)
