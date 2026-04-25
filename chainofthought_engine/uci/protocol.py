"""UCI protocol loop.

A line-buffered driver that translates the UCI text protocol into
calls on a :class:`~chainofthought_engine.search.engine.Engine`. Two
audiences for this file:

  - **Real GUIs.** ``python -m chainofthought_engine --uci`` becomes
    a UCI engine that any Arena/Cute Chess/Banksia/lichess-bot
    setup can launch as a subprocess.
  - **Tests and the local UI.** Both consume :meth:`UCIProtocol.handle`
    directly with custom ``stdin``/``stdout`` streams, so we never
    spin up a subprocess to verify behaviour.

Supported commands
------------------

================  =============================================================
``uci``           identify, list options, ``uciok``
``isready``       ``readyok`` (always immediate, even mid-search)
``ucinewgame``    stop any running search, clear TT, reset board
``position``      ``startpos | fen <FEN>`` ``[moves <m1> <m2> ...]``
``go``            ``depth | movetime | wtime/btime/winc/binc | infinite``
``stop``          cooperative stop -> engine emits ``bestmove``
``quit``          stop and exit
``setoption``     ``UCI_Elo``, ``UCI_LimitStrength``
``debug``         accepted, no-op (we don't gate output on this)
================  =============================================================

Anything else is silently ignored as the spec requires; parse errors
inside a known command emit ``info string ...`` for diagnostics
(GUIs ignore those, humans see them).

Threading model
---------------

``go`` returns immediately and the actual search runs in a daemon
thread. ``stop`` flips the engine's stop flag; the search thread
unwinds, prints its ``info`` line, prints ``bestmove``, and exits.
``isready`` does NOT wait for the search -- the spec is explicit
that ``readyok`` must arrive promptly even mid-search. ``quit`` and
``ucinewgame`` join the search thread before continuing.

All writes to ``stdout`` go through a lock so the search thread and
the main loop never interleave a half-line.

Robustness
----------

The dispatcher in :meth:`handle` wraps every command in a
``try/except`` so a malformed line can never crash the loop. UCI
sessions are long-running; falling over on bad input would force
the GUI to relaunch the engine.
"""

from __future__ import annotations

import sys
import threading
from time import perf_counter
from typing import IO, Callable, Final, Optional

from .. import __version__
from ..core.board import Board
from ..core.move import Move
from ..core.types import PieceType
from ..search.elo import DEFAULT_ELO, MAX_ELO, MIN_ELO
from ..search.engine import Engine, SearchLimits, SearchResult


ENGINE_NAME: Final[str] = "Chain-of-Thought Engine"
ENGINE_AUTHOR: Final[str] = "PointChess Team"


# UCI null-move sentinel, used when the search reports no legal moves
# (mate / stalemate at the root). GUIs treat this as game-over.
_NULL_MOVE: Final[str] = "0000"

# Token mapping for ``go`` clock fields.
_GO_INT_FIELDS: Final[dict[str, str]] = {
    "depth": "depth",
    "movetime": "movetime_ms",
    "wtime": "wtime_ms",
    "btime": "btime_ms",
    "winc": "winc_ms",
    "binc": "binc_ms",
}


class UCIProtocol:
    """Stateful UCI driver.

    Construction parameters all default to sensible values so a real
    UCI launch is just ``UCIProtocol().run()``. Tests construct with
    explicit ``stdin``/``stdout`` (e.g. ``io.StringIO``) and an
    engine pinned to known options.
    """

    def __init__(
        self,
        engine: Engine | None = None,
        stdin: IO[str] | None = None,
        stdout: IO[str] | None = None,
    ) -> None:
        self.engine = engine if engine is not None else Engine(elo=DEFAULT_ELO)
        self.stdin = stdin if stdin is not None else sys.stdin
        self.stdout = stdout if stdout is not None else sys.stdout

        # Current position the next ``go`` will search from.
        self._board: Board = Board.starting_position()

        # Background search machinery.
        self._search_thread: Optional[threading.Thread] = None
        self._out_lock = threading.Lock()

        # Set when ``quit`` is processed so ``run`` can exit cleanly.
        self._quit_requested = False

    # ------------------------------------------------------------------
    # static surface (also consulted by tests and the UI)
    # ------------------------------------------------------------------

    @staticmethod
    def options() -> list[dict]:
        """Spec for the options the engine advertises."""
        return [
            {
                "name": "UCI_Elo",
                "type": "spin",
                "default": DEFAULT_ELO,
                "min": MIN_ELO,
                "max": MAX_ELO,
            },
            {
                "name": "UCI_LimitStrength",
                "type": "check",
                "default": True,
            },
        ]

    # ------------------------------------------------------------------
    # main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Read commands from ``stdin`` until ``quit`` or EOF."""
        for raw in self.stdin:
            line = raw.strip()
            if not line:
                continue
            self.handle(line)
            if self._quit_requested:
                break
        # EOF or ``quit`` -- in either case stop & join the search so
        # we don't leak a daemon thread holding the engine.
        self._stop_and_join()

    def handle(self, line: str) -> None:
        """Dispatch one command line. Exposed for tests and the UI.

        Never raises -- malformed input is reported as an
        ``info string`` line and the loop continues.
        """
        tokens = line.strip().split()
        if not tokens:
            return
        cmd, args = tokens[0], tokens[1:]
        handler = self._HANDLERS.get(cmd)
        if handler is None:
            # Spec: ignore unknown commands silently.
            return
        try:
            handler(self, args)
        except Exception as exc:  # noqa: BLE001
            self._println(f"info string error in {cmd!r}: {exc}")

    # ------------------------------------------------------------------
    # output helpers (lock-protected so the search thread can't tear)
    # ------------------------------------------------------------------

    def _println(self, line: str) -> None:
        with self._out_lock:
            self.stdout.write(line + "\n")
            self.stdout.flush()

    # ------------------------------------------------------------------
    # background search
    # ------------------------------------------------------------------

    def is_searching(self) -> bool:
        """True iff a ``go`` is currently executing in the background."""
        t = self._search_thread
        return t is not None and t.is_alive()

    def wait_for_search(self, timeout: Optional[float] = None) -> bool:
        """Block until the current search (if any) finishes.

        Returns True if no search is running or it finished within
        the timeout, False if it timed out. Public for tests.
        """
        t = self._search_thread
        if t is None:
            return True
        t.join(timeout)
        return not t.is_alive()

    def _stop_and_join(self) -> None:
        """Cooperative stop + join. Idempotent."""
        if self._search_thread is None:
            return
        self.engine.stop()
        self._search_thread.join()
        self._search_thread = None

    def _start_search(self, limits: SearchLimits) -> None:
        # Snapshot the board so the search thread can't be racing the
        # main loop's next ``position`` command.
        snapshot = Board.from_fen(self._board.fen())

        def _do_search() -> None:
            t0 = perf_counter()
            try:
                result = self.engine.search(snapshot, limits)
            except Exception as exc:  # noqa: BLE001
                # Last-ditch: tell the GUI something so it doesn't hang.
                self._println(f"info string search error: {exc}")
                self._println(f"bestmove {_NULL_MOVE}")
                return
            self._emit_info(result, perf_counter() - t0)
            self._emit_bestmove(result)

        self._stop_and_join()
        thread = threading.Thread(
            target=_do_search, name="uci-search", daemon=True
        )
        self._search_thread = thread
        thread.start()

    # ------------------------------------------------------------------
    # output formatters
    # ------------------------------------------------------------------

    def _emit_info(self, result: SearchResult, elapsed_s: float) -> None:
        # Prefer the result's own time/nodes if populated; fall back
        # to the wall-clock we measured here (covers an aborted search).
        time_ms = result.time_ms or int(elapsed_s * 1000)
        parts = [f"info depth {max(result.depth, 0)}"]
        if result.mate_in is not None:
            parts.append(f"score mate {result.mate_in}")
        elif result.score_cp is not None:
            parts.append(f"score cp {result.score_cp}")
        parts.append(f"nodes {result.nodes}")
        if time_ms > 0:
            nps = int(result.nodes * 1000 / time_ms)
            parts.append(f"nps {nps}")
        parts.append(f"time {time_ms}")
        if result.pv:
            pv_uci = " ".join(m.uci() for m in result.pv)
            parts.append(f"pv {pv_uci}")
        self._println(" ".join(parts))

    def _emit_bestmove(self, result: SearchResult) -> None:
        if result.best_move is None:
            self._println(f"bestmove {_NULL_MOVE}")
            return
        self._println(f"bestmove {result.best_move.uci()}")

    # ==================================================================
    # command handlers
    # ==================================================================

    def _cmd_uci(self, args: list[str]) -> None:
        self._println(f"id name {ENGINE_NAME} {__version__}")
        self._println(f"id author {ENGINE_AUTHOR}")
        for opt in self.options():
            self._println(_format_option(opt))
        self._println("uciok")

    def _cmd_isready(self, args: list[str]) -> None:
        # Spec: must reply readyok immediately, EVEN if a search is
        # in progress. Do not join.
        self._println("readyok")

    def _cmd_ucinewgame(self, args: list[str]) -> None:
        self._stop_and_join()
        self.engine.new_game()
        self._board = Board.starting_position()

    def _cmd_position(self, args: list[str]) -> None:
        if not args:
            raise ValueError("expected 'startpos' or 'fen'")

        if args[0] == "startpos":
            board = Board.starting_position()
            cursor = 1
        elif args[0] == "fen":
            if len(args) < 7:
                raise ValueError("'fen' needs 6 fields")
            fen = " ".join(args[1:7])
            board = Board.from_fen(fen)
            cursor = 7
        else:
            raise ValueError(
                f"expected 'startpos' or 'fen', got {args[0]!r}"
            )

        if cursor < len(args):
            if args[cursor] != "moves":
                raise ValueError(
                    f"expected 'moves', got {args[cursor]!r}"
                )
            for uci in args[cursor + 1 :]:
                move = _resolve_move(board, uci)
                board.make_move(move)

        # Only commit the new board once parsing fully succeeds, so a
        # malformed ``position`` doesn't corrupt our state.
        self._board = board

    def _cmd_go(self, args: list[str]) -> None:
        kwargs: dict[str, object] = {}
        i = 0
        while i < len(args):
            tok = args[i]
            if tok in _GO_INT_FIELDS:
                if i + 1 >= len(args):
                    raise ValueError(f"'{tok}' missing value")
                try:
                    kwargs[_GO_INT_FIELDS[tok]] = int(args[i + 1])
                except ValueError as exc:
                    raise ValueError(
                        f"'{tok}' value not an int: {args[i+1]!r}"
                    ) from exc
                i += 2
            elif tok == "infinite":
                kwargs["infinite"] = True
                i += 1
            elif tok in ("ponder", "mate", "nodes", "movestogo",
                         "searchmoves"):
                # Recognised but not yet implemented. Skip the
                # following arg too if there is one (best-effort).
                i += 2 if i + 1 < len(args) else 1
            else:
                # Unknown go subtoken; skip just it.
                i += 1
        limits = SearchLimits(**kwargs)
        self._start_search(limits)

    def _cmd_stop(self, args: list[str]) -> None:
        # The thread itself prints ``bestmove`` once the engine
        # returns; we just nudge it.
        self._stop_and_join()

    def _cmd_quit(self, args: list[str]) -> None:
        self._stop_and_join()
        self._quit_requested = True

    def _cmd_setoption(self, args: list[str]) -> None:
        if not args or args[0] != "name":
            raise ValueError("setoption: expected 'name'")
        # 'value' may be absent for button-type options.
        try:
            value_idx = args.index("value", 1)
            name = " ".join(args[1:value_idx])
            value = " ".join(args[value_idx + 1 :])
        except ValueError:
            name = " ".join(args[1:])
            value = ""

        if not name:
            raise ValueError("setoption: empty name")

        if name == "UCI_Elo":
            try:
                self.engine.set_elo(int(value))
            except ValueError as exc:
                raise ValueError(
                    f"UCI_Elo: not an int: {value!r}"
                ) from exc
        elif name == "UCI_LimitStrength":
            # Boolean knob. We always limit strength via UCI_Elo, so
            # this is acknowledged but has no internal effect; the
            # engine.set_elo path already drives weakening.
            _parsed = _parse_bool(value)  # validates input
            del _parsed
        else:
            self._println(f"info string unknown option: {name!r}")

    def _cmd_debug(self, args: list[str]) -> None:
        # Accepted but no-op. We don't gate output on debug mode.
        return

    # ------------------------------------------------------------------
    # dispatch table
    # ------------------------------------------------------------------

    _HANDLERS: dict[str, Callable[["UCIProtocol", list[str]], None]] = {
        "uci": _cmd_uci,
        "isready": _cmd_isready,
        "ucinewgame": _cmd_ucinewgame,
        "position": _cmd_position,
        "go": _cmd_go,
        "stop": _cmd_stop,
        "quit": _cmd_quit,
        "setoption": _cmd_setoption,
        "debug": _cmd_debug,
    }


# ----------------------------------------------------------------------
# helpers (module-level so tests can hit them directly if useful)
# ----------------------------------------------------------------------


def _format_option(opt: dict) -> str:
    """Format a single ``option name ...`` line."""
    parts = [f"option name {opt['name']}", f"type {opt['type']}"]
    if "default" in opt:
        default = opt["default"]
        if isinstance(default, bool):
            default = "true" if default else "false"
        parts.append(f"default {default}")
    if "min" in opt:
        parts.append(f"min {opt['min']}")
    if "max" in opt:
        parts.append(f"max {opt['max']}")
    return " ".join(parts)


def _parse_bool(text: str) -> bool:
    s = text.strip().lower()
    if s in ("true", "1", "yes", "on"):
        return True
    if s in ("false", "0", "no", "off"):
        return False
    raise ValueError(f"not a boolean: {text!r}")


def _resolve_move(board: Board, uci: str) -> Move:
    """Parse a UCI move string and validate it against ``board``.

    The promotion piece in the parsed move may be ``None`` when the
    GUI sends a 4-char string for what is actually a promotion (some
    GUIs do this when offering only a queen-promotion). We recover
    by promoting to queen in that case if the move would otherwise
    be illegal.

    Raises ``ValueError`` if no legal interpretation exists.
    """
    parsed = Move.from_uci(uci)
    legal = board.legal_moves()
    if parsed in legal:
        return parsed
    # Try queen promotion as a fallback for under-specified strings.
    if parsed.promotion is None:
        promoted = Move(
            from_sq=parsed.from_sq,
            to_sq=parsed.to_sq,
            promotion=PieceType.QUEEN,
        )
        if promoted in legal:
            return promoted
    raise ValueError(f"illegal move {uci!r} in current position")
