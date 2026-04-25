"""UCI adapter for the GEPA-RLM engine artifact."""

from __future__ import annotations

import sys
from typing import TextIO

import chess

from .engine import DEFAULT_MOVETIME_MS, GEPARLMChessEngine, SearchLimits


class GEPARLMUCI:
    def __init__(self) -> None:
        self.board = chess.Board()
        self.engine = GEPARLMChessEngine()
        self.skill = 20

    def run(self, input_stream: TextIO = sys.stdin, output_stream: TextIO = sys.stdout) -> None:
        for raw_line in input_stream:
            line = raw_line.strip()
            if not line:
                continue
            if line == "uci":
                self._write(output_stream, "id name PointChess GEPA-RLM")
                self._write(output_stream, "id author PointChessEngine")
                self._write(output_stream, "option name Skill type spin default 20 min 1 max 20")
                self._write(output_stream, "uciok")
            elif line == "isready":
                self._write(output_stream, "readyok")
            elif line == "ucinewgame":
                self.board = chess.Board()
            elif line.startswith("setoption"):
                self._handle_setoption(line)
            elif line.startswith("position"):
                self._handle_position(line.split()[1:])
            elif line.startswith("go"):
                self._handle_go(line.split()[1:], output_stream)
            elif line == "stop":
                continue
            elif line == "quit":
                break
            else:
                self._write(output_stream, f"info string ignored unknown command: {line}")

    def _handle_setoption(self, line: str) -> None:
        parts = line.split()
        if "Skill" not in parts or "value" not in parts:
            return
        try:
            value_index = parts.index("value") + 1
            self.skill = max(1, min(20, int(parts[value_index])))
        except (ValueError, IndexError):
            return

    def _handle_position(self, tokens: list[str]) -> None:
        if not tokens:
            return
        try:
            if tokens[0] == "startpos":
                board = chess.Board()
                index = 1
            elif tokens[0] == "fen":
                index = 1
                fen_parts: list[str] = []
                while index < len(tokens) and tokens[index] != "moves":
                    fen_parts.append(tokens[index])
                    index += 1
                board = chess.Board(" ".join(fen_parts))
            else:
                return

            if index < len(tokens) and tokens[index] == "moves":
                for move_text in tokens[index + 1 :]:
                    board.push_uci(move_text)
            self.board = board
        except ValueError:
            return

    def _handle_go(self, tokens: list[str], output_stream: TextIO) -> None:
        depth = self._parse_int_after(tokens, "depth") or self._depth_from_skill()
        movetime = self._parse_int_after(tokens, "movetime")
        if movetime is None and "depth" not in tokens:
            movetime = DEFAULT_MOVETIME_MS

        result = self.engine.choose_move(self.board.copy(stack=False), SearchLimits(depth=depth, movetime_ms=movetime))
        pv = " ".join(result.diagnostics.get("pv", []))
        self._write(
            output_stream,
            f"info depth {result.depth} score cp {result.score_cp} nodes {result.nodes} time {result.time_ms} pv {pv}".rstrip(),
        )
        if result.bestmove is None:
            self._write(output_stream, "bestmove 0000")
        else:
            self._write(output_stream, f"bestmove {result.bestmove.uci()}")

    def _depth_from_skill(self) -> int:
        if self.skill >= 18:
            return 3
        if self.skill >= 9:
            return 2
        return 1

    @staticmethod
    def _parse_int_after(tokens: list[str], key: str) -> int | None:
        if key not in tokens:
            return None
        try:
            return int(tokens[tokens.index(key) + 1])
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _write(output_stream: TextIO, text: str) -> None:
        output_stream.write(text + "\n")
        output_stream.flush()


def run_uci(input_stream: TextIO = sys.stdin, output_stream: TextIO = sys.stdout) -> None:
    GEPARLMUCI().run(input_stream=input_stream, output_stream=output_stream)
