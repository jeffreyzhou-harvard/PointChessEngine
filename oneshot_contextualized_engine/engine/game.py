"""Game manager.

A thin façade around `chess.Board` that adds:
    * move history with undo
    * FEN / PGN import-export
    * convenience predicates (is_over, result, status_text)

We deliberately do NOT reimplement rules. python-chess (the supplied
context) handles legal move generation, repetition detection,
fifty-move rule, insufficient-material, FEN parsing, and SAN — and is the
ground truth our tests check against.
"""

from __future__ import annotations

import datetime
import io
from dataclasses import dataclass, field
from typing import List, Optional

import chess
import chess.pgn


@dataclass
class Game:
    board: chess.Board = field(default_factory=chess.Board)
    move_history: List[chess.Move] = field(default_factory=list)
    san_history: List[str] = field(default_factory=list)
    headers: dict = field(default_factory=lambda: {
        "Event": "Casual game",
        "Site": "Local",
        "Date": datetime.date.today().strftime("%Y.%m.%d"),
        "Round": "-",
        "White": "?",
        "Black": "?",
    })

    # ---- construction ----------------------------------------------------

    @classmethod
    def from_fen(cls, fen: str) -> "Game":
        return cls(board=chess.Board(fen))

    def reset(self, fen: Optional[str] = None) -> None:
        self.board = chess.Board(fen) if fen else chess.Board()
        self.move_history.clear()
        self.san_history.clear()

    # ---- move application ------------------------------------------------

    def push_uci(self, uci: str) -> chess.Move:
        move = chess.Move.from_uci(uci)
        if move not in self.board.legal_moves:
            raise ValueError(f"illegal move: {uci} in FEN {self.board.fen()}")
        san = self.board.san(move)
        self.board.push(move)
        self.move_history.append(move)
        self.san_history.append(san)
        return move

    def push(self, move: chess.Move) -> None:
        if move not in self.board.legal_moves:
            raise ValueError(f"illegal move: {move.uci()} in FEN {self.board.fen()}")
        san = self.board.san(move)
        self.board.push(move)
        self.move_history.append(move)
        self.san_history.append(san)

    def undo(self) -> Optional[chess.Move]:
        if not self.move_history:
            return None
        self.move_history.pop()
        self.san_history.pop()
        return self.board.pop()

    # ---- queries ---------------------------------------------------------

    @property
    def fen(self) -> str:
        return self.board.fen()

    @property
    def turn(self) -> chess.Color:
        return self.board.turn

    @property
    def is_over(self) -> bool:
        return self.board.is_game_over(claim_draw=True)

    @property
    def result(self) -> str:
        return self.board.result(claim_draw=True)

    def legal_moves_uci(self) -> List[str]:
        return [m.uci() for m in self.board.legal_moves]

    def status_text(self) -> str:
        b = self.board
        if b.is_checkmate():
            winner = "Black" if b.turn == chess.WHITE else "White"
            return f"Checkmate. {winner} wins."
        if b.is_stalemate():
            return "Stalemate. Draw."
        if b.is_insufficient_material():
            return "Insufficient material. Draw."
        if b.is_seventyfive_moves():
            return "75-move rule. Draw."
        if b.is_fivefold_repetition():
            return "Fivefold repetition. Draw."
        if b.can_claim_threefold_repetition():
            return "Threefold repetition (claimable). Draw if claimed."
        if b.can_claim_fifty_moves():
            return "Fifty-move rule (claimable). Draw if claimed."
        if b.is_check():
            return f"{'White' if b.turn == chess.WHITE else 'Black'} is in check."
        return f"{'White' if b.turn == chess.WHITE else 'Black'} to move."

    # ---- export ----------------------------------------------------------

    def to_pgn(self) -> str:
        """Return the game as a PGN string (with headers)."""
        game = chess.pgn.Game()
        for k, v in self.headers.items():
            game.headers[k] = v
        # Include start FEN if non-standard.
        starting_fen = chess.Board().fen()
        # Reconstruct a starting board by undoing all our moves... but
        # easier: use a fresh board and replay; if the game *started* from
        # a non-standard FEN we set it explicitly.
        start_board = chess.Board()
        for m in self.move_history:
            try:
                start_board.push(m)
            except Exception:
                # The history must have started from a non-standard FEN.
                start_board = self.board.copy()
                break

        # Rebuild from history. To capture non-standard starts cleanly, we
        # set FEN if the inferred starting board differs from the actual
        # initial position implied by `self`.
        actual_start = self.board.copy()
        for _ in range(len(self.move_history)):
            actual_start.pop()
        if actual_start.fen() != starting_fen:
            game.headers["FEN"] = actual_start.fen()
            game.headers["SetUp"] = "1"
            node = game
            replay = actual_start.copy()
        else:
            node = game
            replay = chess.Board()

        for m in self.move_history:
            node = node.add_main_variation(m)
            replay.push(m)

        game.headers["Result"] = self.result
        out = io.StringIO()
        exporter = chess.pgn.FileExporter(out)
        game.accept(exporter)
        return out.getvalue()
