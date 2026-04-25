"""Shared helpers for benchmark-facing classical engine tests."""

import io
import os
import re
import select
import subprocess
import sys
import time
import unittest

from engines.oneshot_nocontext.core.board import Board, STARTING_FEN
from engines.oneshot_nocontext.core.types import Move
from engines.oneshot_nocontext.uci.protocol import UCIProtocol


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENGINE_CMD = [sys.executable, "-m", "engines.oneshot_nocontext", "--uci"]
UCI_MOVE_RE = re.compile(r"^(?:[a-h][1-8][a-h][1-8][qrbn]?|0000)$")


def legal_uci_moves(board: Board) -> set[str]:
    return {move.uci() for move in board.legal_moves()}


def find_legal_move(board: Board, uci: str) -> Move:
    requested = Move.from_uci(uci)
    for move in board.legal_moves():
        if (
            move.from_sq == requested.from_sq
            and move.to_sq == requested.to_sq
            and (requested.promotion is None or move.promotion == requested.promotion)
        ):
            return move
    raise AssertionError(f"{uci} not legal in {board.to_fen()}")


def play_uci_moves(board: Board, moves: list[str]) -> Board:
    for uci in moves:
        move = find_legal_move(board, uci)
        made = board.make_move(move)
        if not made:
            raise AssertionError(f"failed to make legal move {uci}")
    return board


def run_in_memory_uci(commands: list[str], timeout: float = 2.0) -> str:
    input_stream = io.StringIO("\n".join(commands) + "\n")
    output_stream = io.StringIO()
    protocol = UCIProtocol(input_stream=input_stream, output_stream=output_stream)
    protocol.run()
    if protocol.search_thread:
        protocol.search_thread.join(timeout)
    return output_stream.getvalue()


class UCISubprocess:
    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout
        self.process = subprocess.Popen(
            ENGINE_CMD,
            cwd=ROOT_DIR,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.lines: list[str] = []

    def send(self, command: str) -> None:
        if self.process.stdin is None:
            raise RuntimeError("UCI process stdin is closed")
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def read_until(self, needle: str) -> str:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            if self.process.stdout is None:
                break
            ready, _, _ = select.select([self.process.stdout], [], [], 0.05)
            if not ready:
                if self.process.poll() is not None:
                    break
                continue
            line = self.process.stdout.readline()
            if not line:
                continue
            line = line.rstrip("\n")
            self.lines.append(line)
            if needle in line:
                return "\n".join(self.lines)
        raise AssertionError(f"timed out waiting for {needle!r}; saw {self.lines!r}")

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.send("quit")
                self.process.wait(timeout=1.0)
            except Exception:
                self.process.kill()
                self.process.wait(timeout=1.0)

    def __enter__(self) -> "UCISubprocess":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def run_uci_subprocess_commands(commands: list[str], timeout: float = 3.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        ENGINE_CMD,
        cwd=ROOT_DIR,
        input="\n".join(commands) + "\n",
        text=True,
        capture_output=True,
        timeout=timeout,
    )


class ClassicalTestCase(unittest.TestCase):
    maxDiff = None

    def assertLegalUci(self, move: str) -> None:
        self.assertRegex(move, UCI_MOVE_RE)

    def assertFenRoundTrip(self, fen: str) -> None:
        self.assertEqual(Board(fen).to_fen(), fen)


__all__ = [
    "Board",
    "ClassicalTestCase",
    "STARTING_FEN",
    "UCISubprocess",
    "find_legal_move",
    "legal_uci_moves",
    "play_uci_moves",
    "run_in_memory_uci",
    "run_uci_subprocess_commands",
]
