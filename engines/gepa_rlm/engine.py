"""GEPA-RLM engine artifact.

The first GEPA-RLM uploadable artifact intentionally reuses the RLM runtime.
The GEPA-RLM methodology layer is responsible for evolving prompts and
producing future distinct patches; this package gives Champion mode a UCI
engine target without adding separate chess logic.
"""

from __future__ import annotations

from engines.rlm.engine import (
    DEFAULT_MOVETIME_MS,
    MATE_SCORE,
    PIECE_VALUES,
    RLMChessEngine,
    RecursiveEvaluationTrace,
    SearchLimits,
    SearchResult,
)


class GEPARLMChessEngine(RLMChessEngine):
    """Bootstrap GEPA-RLM engine, backed by the RLM decomposed runtime."""


__all__ = [
    "DEFAULT_MOVETIME_MS",
    "GEPARLMChessEngine",
    "MATE_SCORE",
    "PIECE_VALUES",
    "RecursiveEvaluationTrace",
    "SearchLimits",
    "SearchResult",
]
