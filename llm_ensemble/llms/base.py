"""Base class and shared utilities for LLM chess voting clients."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class VoteResult:
    """The outcome of asking one LLM to vote on the best move."""

    llm_name: str
    chosen_move: Optional[str]   # UCI notation (e.g. "e2e4"), None if failed
    explanation: str             # LLM's raw text or error message
    raw_response: str            # Unmodified API response
    success: bool                # False if the API call failed or parse failed
    latency_ms: int              # Wall-clock time for the API call


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class LLMClient(ABC):
    """Abstract base for all LLM voting clients."""

    name: str = "UnknownLLM"

    @abstractmethod
    def vote(
        self,
        fen: str,
        candidates: List[str],
        side_to_move: str,
        move_number: int,
    ) -> VoteResult:
        """Ask the LLM to pick the best move from the candidate list.

        Args:
            fen:           Current position in FEN notation.
            candidates:    Legal candidate moves in UCI notation.
            side_to_move:  "White" or "Black".
            move_number:   Current full-move number.

        Returns:
            VoteResult with ``chosen_move`` set to a UCI string that appears
            in ``candidates``, or ``None`` if the LLM failed/timed-out.
        """
        ...


# ---------------------------------------------------------------------------
# Shared prompt builder
# ---------------------------------------------------------------------------

_FILES = "abcdefgh"
_RANKS = "87654321"

_PIECE_SYMBOLS = {
    ("WHITE", "KING"):   "K",
    ("WHITE", "QUEEN"):  "Q",
    ("WHITE", "ROOK"):   "R",
    ("WHITE", "BISHOP"): "B",
    ("WHITE", "KNIGHT"): "N",
    ("WHITE", "PAWN"):   "P",
    ("BLACK", "KING"):   "k",
    ("BLACK", "QUEEN"):  "q",
    ("BLACK", "ROOK"):   "r",
    ("BLACK", "BISHOP"): "b",
    ("BLACK", "KNIGHT"): "n",
    ("BLACK", "PAWN"):   "p",
}

_UCI_PIECE_NAMES = {
    "p": "pawn",
    "n": "knight",
    "b": "bishop",
    "r": "rook",
    "q": "queen",
    "k": "king",
}


def _fen_to_ascii(fen: str) -> str:
    """Render the board part of a FEN as an ASCII grid."""
    board_part = fen.split()[0]
    rows = board_part.split("/")
    lines: List[str] = ["  a b c d e f g h"]
    for rank_idx, row in enumerate(rows):
        rank_label = 8 - rank_idx
        expanded = ""
        for ch in row:
            if ch.isdigit():
                expanded += "." * int(ch)
            else:
                expanded += ch
        lines.append(f"{rank_label} {' '.join(expanded)}")
    return "\n".join(lines)


def _describe_candidate(uci: str) -> str:
    """Produce a human-readable description of a UCI move string."""
    if len(uci) < 4:
        return uci
    frm = uci[:2]
    to = uci[2:4]
    promo = uci[4:].lower() if len(uci) > 4 else ""
    desc = f"{frm} -> {to}"
    if promo:
        piece_name = _UCI_PIECE_NAMES.get(promo, promo)
        desc += f" (promote to {piece_name})"
    return desc


def build_prompt(
    fen: str,
    candidates: List[str],
    side_to_move: str,
    move_number: int,
) -> str:
    """Build a chess voting prompt for any LLM.

    The prompt is deliberately concise: FEN, ASCII board, ranked candidate
    list, and a strict output instruction.
    """
    ascii_board = _fen_to_ascii(fen)
    numbered = "\n".join(
        f"  {i+1}. {mv}  ({_describe_candidate(mv)})"
        for i, mv in enumerate(candidates)
    )

    return (
        f"You are a grandmaster-strength chess engine.\n"
        f"\n"
        f"Position (FEN): {fen}\n"
        f"\n"
        f"Board ({side_to_move} to move, move {move_number}):\n"
        f"{ascii_board}\n"
        f"\n"
        f"Candidate moves (UCI notation):\n"
        f"{numbered}\n"
        f"\n"
        f"Choose the single best move from the candidates above.\n"
        f"Reply with ONLY the UCI move string (e.g., e2e4 or g1f3). "
        f"No other text, no punctuation, no explanation."
    )


# ---------------------------------------------------------------------------
# Shared move parser
# ---------------------------------------------------------------------------

_UCI_RE = re.compile(r"\b([a-h][1-8][a-h][1-8][qrbnQRBN]?)\b")


def parse_move(raw: str, candidates: List[str]) -> Optional[str]:
    """Extract a legal UCI move from an LLM's raw response.

    Strategy:
    1. Find all UCI-shaped tokens in the response.
    2. Return the first one that appears in ``candidates`` (case-insensitive).
    3. If none match, try stripping whitespace from the whole response.
    4. Return None if nothing valid is found.
    """
    # Normalize candidates to lower-case for matching
    cand_lower = {c.lower(): c for c in candidates}

    # Try regex matches in the response
    for m in _UCI_RE.finditer(raw):
        token = m.group(1).lower()
        if token in cand_lower:
            return cand_lower[token]

    # Try treating the whole stripped response as a move
    stripped = raw.strip().lower().replace(".", "").split()[0] if raw.strip() else ""
    if stripped in cand_lower:
        return cand_lower[stripped]

    return None
