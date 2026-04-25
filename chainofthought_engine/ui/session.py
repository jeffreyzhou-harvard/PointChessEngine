"""UI-side game session.

The browser frontend should never touch ``Engine``, ``Board``, or
``GameState`` directly: it just renders whatever ``Session.state_dict``
returns and POSTs commands. All chess logic lives below this line.

Why a dedicated class instead of "just put it in the HTTP handler":

  - The handler is concerned with HTTP wire format (status codes,
    JSON serialization, request validation). The session is
    concerned with game state (whose turn, what's legal, did the
    user resign).
  - Tests of the *game flow* (you start a game, you play, the
    engine replies, the game ends) become trivial: construct a
    ``Session``, drive it with method calls, assert on
    ``state_dict``. No HTTP machinery needed.
  - Future surfaces (a CLI prompt, a TUI, a desktop wrapper) reuse
    the same session.

Threading
---------

A :class:`Session` is **not** internally thread-safe. The HTTP
server holds a single mutex around it for the lifetime of each
request. The mutex is held across :meth:`play_engine_move`, which
can take seconds. That's deliberate: while the engine is searching,
other requests (state polls, new-game, resign) wait. Trying to
interleave them would require a substantially more complex
state machine for very little gain on a single-user UI.
"""

from __future__ import annotations

from typing import Optional

from ..core.board import Board
from ..core.game import GameState
from ..core.move import Move
from ..core.types import Color, PieceType, square_to_algebraic
from ..search.elo import DEFAULT_ELO, MAX_ELO, MIN_ELO
from ..search.engine import Engine, SearchLimits, SearchResult


_COLOR_NAMES = {Color.WHITE: "white", Color.BLACK: "black"}


def _color_from_name(name: str) -> Color:
    if name == "white":
        return Color.WHITE
    if name == "black":
        return Color.BLACK
    raise ValueError(f"unknown color: {name!r}")


def _resolve_move(board: Board, uci: str) -> Move:
    """Parse a UCI string and validate against ``board``.

    Mirrors the logic in :func:`uci.protocol._resolve_move`: a 4-char
    string for what is actually a promotion is auto-promoted to
    queen. Raises ``ValueError`` if no legal interpretation exists.
    """
    parsed = Move.from_uci(uci)
    legal = board.legal_moves()
    if parsed in legal:
        return parsed
    if parsed.promotion is None:
        promoted = Move(
            from_sq=parsed.from_sq,
            to_sq=parsed.to_sq,
            promotion=PieceType.QUEEN,
        )
        if promoted in legal:
            return promoted
    raise ValueError(f"illegal move: {uci!r}")


class Session:
    """A single player's game against the engine.

    Public surface:

      - :meth:`start_new_game` -- reset board, color, ELO.
      - :meth:`set_elo`, :meth:`set_user_color`.
      - :meth:`play_user_move` (UCI string).
      - :meth:`play_engine_move` -- search and apply.
      - :meth:`resign`.
      - :meth:`state_dict` -- all the data the UI needs to render.
      - :meth:`pgn` -- PGN export of the current game.

    All errors raised here are :class:`ValueError`; the HTTP layer
    maps them to 400 responses.
    """

    def __init__(
        self,
        user_color: Color = Color.WHITE,
        elo: int = DEFAULT_ELO,
        seed: Optional[int] = None,
    ) -> None:
        self._user_color: Color = user_color
        self._elo: int = max(MIN_ELO, min(MAX_ELO, int(elo)))
        self._engine: Engine = Engine(elo=self._elo, seed=seed)
        self._game: GameState = GameState.new_game()
        self._resigned: bool = False
        # Diagnostics from the most recent engine move (depth, score,
        # nodes, pv) so the UI can show what the engine "thought".
        self._last_engine_info: Optional[dict] = None

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------

    def start_new_game(
        self,
        user_color: Optional[Color] = None,
        elo: Optional[int] = None,
    ) -> None:
        """Reset to the standard starting position.

        Both arguments are optional: omitting them keeps the current
        user color / ELO. Always wipes the engine's TT and resigns
        nothing -- it's a brand-new game.
        """
        if user_color is not None:
            self._user_color = user_color
        if elo is not None:
            self.set_elo(elo)
        self._game = GameState.new_game()
        self._resigned = False
        self._last_engine_info = None
        self._engine.new_game()

    def set_user_color(self, color: Color) -> None:
        """Mid-game color swap. Mostly useful in tests; the UI should
        usually start a new game instead."""
        self._user_color = color

    def set_elo(self, elo: int) -> None:
        """Update strength. Clamped to ``[MIN_ELO, MAX_ELO]``."""
        self._elo = max(MIN_ELO, min(MAX_ELO, int(elo)))
        self._engine.set_elo(self._elo)

    # ------------------------------------------------------------------
    # introspection
    # ------------------------------------------------------------------

    @property
    def board(self) -> Board:
        return self._game.board

    @property
    def user_color(self) -> Color:
        return self._user_color

    @property
    def elo(self) -> int:
        return self._elo

    @property
    def to_move(self) -> Color:
        return self._game.board.turn

    def is_game_over(self) -> bool:
        return self._resigned or self._game.is_game_over()

    def is_user_turn(self) -> bool:
        return (
            not self.is_game_over()
            and self.to_move is self._user_color
        )

    def is_engine_turn(self) -> bool:
        return (
            not self.is_game_over()
            and self.to_move is not self._user_color
        )

    # ------------------------------------------------------------------
    # gameplay
    # ------------------------------------------------------------------

    def play_user_move(self, uci: str) -> None:
        """Apply a user move described by a UCI string.

        Raises ``ValueError`` if the game is over, it isn't the
        user's turn, or the move is illegal.
        """
        if self.is_game_over():
            raise ValueError("game is over")
        if not self.is_user_turn():
            raise ValueError("not your turn")
        move = _resolve_move(self._game.board, uci)
        self._game.play(move)

    def play_engine_move(self) -> Optional[dict]:
        """Run the engine and apply its move.

        Returns the engine's diagnostic info dict (uci, san, depth,
        score_cp / mate_in, nodes, time_ms) or ``None`` when there
        was no legal move at all (mate / stalemate).

        Raises ``ValueError`` if the game is over or it isn't the
        engine's turn.
        """
        if self.is_game_over():
            raise ValueError("game is over")
        if not self.is_engine_turn():
            raise ValueError("not engine's turn")
        result: SearchResult = self._engine.search(
            self._game.board, SearchLimits()
        )
        if result.best_move is None:
            # The board IS terminal (mate/stalemate) but we got past
            # the is_game_over check -- this shouldn't normally
            # happen because GameState.is_game_over already covers
            # mate and stalemate, but we handle it defensively.
            self._last_engine_info = None
            return None
        self._game.play(result.best_move)
        info = {
            "uci": result.best_move.uci(),
            "san": self._game.san_history()[-1],
            "depth": result.depth,
            "nodes": result.nodes,
            "time_ms": result.time_ms,
            "score_cp": result.score_cp,
            "mate_in": result.mate_in,
            "pv": [m.uci() for m in result.pv],
        }
        self._last_engine_info = info
        return info

    def resign(self) -> None:
        """User concedes. Flagged as game over; engine wins."""
        if self.is_game_over():
            raise ValueError("game is over")
        self._resigned = True

    # ------------------------------------------------------------------
    # serialisation for the frontend
    # ------------------------------------------------------------------

    def legal_moves_grouped(self) -> dict[str, list[str]]:
        """``{from_square: [to_square, ...], ...}`` for the user to play.

        Returns empty when it's not the user's turn (so the frontend
        can't accidentally let the user pre-move while the engine is
        thinking) or when the game is over.

        Squares are algebraic strings (``"e2"``). Promotion targets
        appear as plain destinations (``"e7"->"e8"``); the UI shows a
        chooser and posts a 5-char UCI string back. Duplicate
        destinations from the four promotion variants are collapsed
        into one entry.
        """
        if not self.is_user_turn():
            return {}
        out: dict[str, list[str]] = {}
        for m in self._game.board.legal_moves():
            out.setdefault(square_to_algebraic(m.from_sq), []).append(
                square_to_algebraic(m.to_sq)
            )
        return {k: sorted(set(v)) for k, v in out.items()}

    def status(self) -> str:
        """One-line human-readable status for the status bar."""
        if self._resigned:
            winner = (
                "Black" if self._user_color is Color.WHITE else "White"
            )
            return f"You resigned. {winner} wins."
        b = self._game.board
        if b.is_checkmate():
            winner = "Black" if b.turn is Color.WHITE else "White"
            return f"Checkmate. {winner} wins."
        if b.is_stalemate():
            return "Stalemate. Draw."
        if b.is_insufficient_material():
            return "Draw by insufficient material."
        if self._game.is_fifty_move_rule():
            return "Draw by fifty-move rule."
        if self._game.is_threefold_repetition():
            return "Draw by threefold repetition."
        side = "White" if b.turn is Color.WHITE else "Black"
        if b.is_check():
            return f"{side} is in check."
        return f"{side} to move."

    def result(self) -> str:
        """One of ``"1-0"``, ``"0-1"``, ``"1/2-1/2"``, ``"*"``."""
        if self._resigned:
            return "1-0" if self._user_color is Color.BLACK else "0-1"
        return self._game.result()

    def state_dict(self) -> dict:
        """Everything the frontend needs to render the page.

        Stable shape; new fields may be added but existing ones
        should not be removed without bumping a UI version.
        """
        b = self._game.board
        return {
            "fen": b.fen(),
            "turn": _COLOR_NAMES[b.turn],
            "user_color": _COLOR_NAMES[self._user_color],
            "elo": self._elo,
            "history_uci": [m.uci() for m in self._game.history()],
            "history_san": list(self._game.san_history()),
            "legal_moves": self.legal_moves_grouped(),
            "status": self.status(),
            "result": self.result(),
            "game_over": self.is_game_over(),
            "is_user_turn": self.is_user_turn(),
            "is_engine_turn": self.is_engine_turn(),
            "in_check": b.is_check(),
            "resigned": self._resigned,
            "last_engine_info": self._last_engine_info,
            "elo_range": {
                "min": MIN_ELO,
                "max": MAX_ELO,
                "default": DEFAULT_ELO,
            },
        }

    def pgn(self) -> str:
        """Render the current game as a PGN string.

        If the user resigned, override the Result tag accordingly.
        """
        headers = {}
        if self._resigned:
            headers["Result"] = self.result()
            headers["Termination"] = "User resigned"
        return self._game.pgn(headers=headers if headers else None)


# Re-exports the HTTP layer wants without re-importing core.
__all__ = ["Session", "_color_from_name", "_resolve_move"]
