"""EnsembleEngine: alpha-beta search + parallel LLM voting.

Flow for each move decision:
  1. Run alpha-beta search (depth/time from ELO settings) to rank candidates.
  2. Present the top-K candidates to all five LLMs simultaneously.
  3. Collect votes and aggregate them with the chosen method.
  4. Return the winning move plus full diagnostics.
  5. Fall back to the alpha-beta best if all LLMs fail.

ELO mapping (400-2400):
  Lower ELO -> shallower search, more candidates (wider pool of "okay" moves),
               higher eval noise, potential blunder pick from non-voted candidates.
  Higher ELO -> deeper search, fewer candidates (only the strong ones shown),
               lower noise, best move almost always wins.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ..llms.base import LLMClient
from .voter import VotingSession, vote_parallel
from .aggregator import VoteTally, aggregate
from ..config import (
    DEFAULT_ELO,
    DEFAULT_CANDIDATES,
    DEFAULT_VOTING_METHOD,
    VOTE_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ELO parameter mapping
# ---------------------------------------------------------------------------


@dataclass
class EloSettings:
    """Search and voting parameters derived from the ELO slider."""

    elo: int
    max_depth: int
    movetime_ms: int         # soft time budget for alpha-beta
    num_candidates: int      # how many top AB moves to show LLMs
    noise_cp: int            # centipawn noise added to AB scores
    blunder_pct: float       # chance of picking from the LLM-non-winners pool


# ELO brackets: (min_elo, max_elo) -> EloSettings fields
_BRACKETS: List[Tuple[int, int, int, int, int, int, float]] = [
    # min   max  depth  ms     cands  noise  blunder%
    (400,   800,  1,    500,    8,    250,    25.0),
    (800,   1200, 2,    1000,   7,    120,    15.0),
    (1200,  1600, 3,    2000,   6,     60,     8.0),
    (1600,  2000, 4,    4000,   5,     25,     3.0),
    (2000,  2400, 6,    8000,   3,      0,     0.5),
]


def elo_settings(elo: int) -> EloSettings:
    """Interpolate ELO settings from the bracket table."""
    elo = max(400, min(2400, elo))

    for min_e, max_e, d1, ms1, c1, n1, b1 in _BRACKETS:
        if min_e <= elo <= max_e:
            # Linear interpolation within bracket
            t = (elo - min_e) / (max_e - min_e) if max_e > min_e else 1.0
            bracket_idx = _BRACKETS.index((min_e, max_e, d1, ms1, c1, n1, b1))
            if bracket_idx + 1 < len(_BRACKETS):
                _, _, d2, ms2, c2, n2, b2 = _BRACKETS[bracket_idx + 1]
            else:
                d2, ms2, c2, n2, b2 = d1, ms1, c1, n1, b1

            return EloSettings(
                elo=elo,
                max_depth=round(d1 + t * (d2 - d1)),
                movetime_ms=round(ms1 + t * (ms2 - ms1)),
                num_candidates=round(c1 + t * (c2 - c1)),
                noise_cp=round(n1 + t * (n2 - n1)),
                blunder_pct=b1 + t * (b2 - b1),
            )

    # Fallback (shouldn't reach here)
    return EloSettings(elo=elo, max_depth=3, movetime_ms=2000, num_candidates=5, noise_cp=60, blunder_pct=8.0)


# ---------------------------------------------------------------------------
# EnsembleResult
# ---------------------------------------------------------------------------


@dataclass
class EnsembleResult:
    """Full diagnostics from one EnsembleEngine move decision."""

    chosen_move: str            # UCI move the engine will play
    ab_best_move: str           # Alpha-beta's top pick (may differ)
    ab_score_cp: int            # Alpha-beta score for its best move
    ab_depth: int
    ab_nodes: int
    ab_elapsed_ms: int
    candidates: List[str]       # UCI moves shown to LLMs (ranked by AB score)
    ab_scores: List[int]        # AB scores for each candidate
    voting_session: VotingSession
    vote_tally: VoteTally
    settings: EloSettings
    blunder_applied: bool = False


# ---------------------------------------------------------------------------
# EnsembleEngine
# ---------------------------------------------------------------------------


class EnsembleEngine:
    """Combines alpha-beta search with parallel LLM voting.

    Usage::

        engine = EnsembleEngine(clients=[...], elo=1500)
        move = engine.choose_move(board)
    """

    def __init__(
        self,
        clients: Optional[List[LLMClient]] = None,
        elo: int = DEFAULT_ELO,
        voting_method: str = DEFAULT_VOTING_METHOD,
        vote_timeout: float = VOTE_TIMEOUT_SECONDS,
        rng: Optional[random.Random] = None,
    ) -> None:
        self._elo = elo
        self._settings = elo_settings(elo)
        self._voting_method = voting_method
        self._vote_timeout = vote_timeout
        self._rng = rng or random.Random()

        # Import here to avoid circular dependencies at module level
        if clients is None:
            from ..llms import all_clients
            self._clients = all_clients()
        else:
            self._clients = clients

        # Lazy-import the alpha-beta engine from the react engine
        from oneshot_react_engine.engine.search import Engine as ABEngine
        from oneshot_react_engine.engine.strength import settings_for_elo
        self._ab_engine = ABEngine(strength=settings_for_elo(elo), rng=self._rng)

    def set_elo(self, elo: int) -> None:
        self._elo = elo
        self._settings = elo_settings(elo)
        from oneshot_react_engine.engine.strength import settings_for_elo
        self._ab_engine.set_strength(settings_for_elo(elo))

    def reset(self) -> None:
        self._ab_engine.reset()

    def request_stop(self) -> None:
        self._ab_engine.request_stop()

    def choose_move(
        self,
        board,
        movetime_ms: Optional[int] = None,
        max_depth: Optional[int] = None,
        on_info: Optional[Callable] = None,
    ) -> str:
        """High-level entry point: return the UCI string of the chosen move."""
        result = self.search_and_choose(
            board,
            movetime_ms=movetime_ms,
            max_depth=max_depth,
            on_info=on_info,
        )
        return result.chosen_move

    def search_and_choose(
        self,
        board,
        movetime_ms: Optional[int] = None,
        max_depth: Optional[int] = None,
        on_info: Optional[Callable] = None,
    ) -> EnsembleResult:
        """Full search + voting pipeline. Returns EnsembleResult with all diagnostics."""
        settings = self._settings
        depth_cap = max_depth if max_depth is not None else settings.max_depth
        budget_ms = movetime_ms if movetime_ms is not None else settings.movetime_ms

        # 1. Run alpha-beta to get ranked candidates
        from oneshot_react_engine.engine.search import SearchInfo
        ab_result = self._ab_engine.search(
            board,
            movetime_ms=budget_ms,
            max_depth=depth_cap,
            on_info=on_info,
        )

        if ab_result.best_move is None:
            # No legal moves — game over
            raise RuntimeError("no legal moves available")

        # 2. Build candidate list (top-K from alpha-beta, score-ordered)
        # ab_result.candidates is sorted best-first with (Move, score) pairs
        all_candidates: List[Tuple] = ab_result.candidates or [(ab_result.best_move, ab_result.score_cp)]
        k = settings.num_candidates
        top_k = all_candidates[:k]

        # Apply noise to candidate scores (for lower ELO realism)
        if settings.noise_cp > 0:
            top_k = [
                (mv, sc + int(self._rng.gauss(0, settings.noise_cp)))
                for mv, sc in top_k
            ]
            top_k.sort(key=lambda x: -x[1])

        candidate_moves = [mv.uci() for mv, _ in top_k]
        candidate_scores = [sc for _, sc in top_k]

        ab_best_uci = ab_result.best_move.uci()
        if ab_best_uci not in candidate_moves:
            candidate_moves.insert(0, ab_best_uci)
            candidate_scores.insert(0, ab_result.score_cp)

        # 3. Parallel LLM voting
        side_name = "White" if board.turn.name == "WHITE" else "Black"
        session = vote_parallel(
            clients=self._clients,
            fen=board.to_fen(),
            candidates=candidate_moves,
            side_to_move=side_name,
            move_number=board.fullmove_number,
            timeout=self._vote_timeout,
        )

        # 4. Aggregate votes
        tally = aggregate(
            session=session,
            candidates=candidate_moves,
            ab_scores=candidate_scores,
            method=self._voting_method,
        )

        # 5. Potentially apply blunder (pick a non-winner from pool)
        chosen_uci = tally.winner or ab_best_uci
        blunder_applied = False

        if (
            settings.blunder_pct > 0
            and len(candidate_moves) > 1
            and self._rng.random() * 100 < settings.blunder_pct
        ):
            # Pick from the non-winning candidates (lower-quality moves)
            losers = [mv for mv in candidate_moves if mv != chosen_uci]
            if losers:
                weights = [max(1, len(losers) - i) for i in range(len(losers))]
                chosen_uci = self._rng.choices(losers, weights=weights, k=1)[0]
                blunder_applied = True

        return EnsembleResult(
            chosen_move=chosen_uci,
            ab_best_move=ab_best_uci,
            ab_score_cp=ab_result.score_cp,
            ab_depth=ab_result.depth_reached,
            ab_nodes=ab_result.nodes,
            ab_elapsed_ms=ab_result.elapsed_ms,
            candidates=candidate_moves,
            ab_scores=candidate_scores,
            voting_session=session,
            vote_tally=tally,
            settings=settings,
            blunder_applied=blunder_applied,
        )
