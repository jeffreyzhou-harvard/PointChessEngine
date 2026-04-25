"""Vote aggregation strategies.

Three methods are provided:

1. **Plurality** (default): the move with the most votes wins.
   Ties broken by alpha-beta score (highest score wins).

2. **Score-weighted**: each vote is worth (1 + alpha_beta_score_fraction).
   Combines engine knowledge with LLM preferences.

3. **Consensus**: only accept a move if at least 3 of 5 LLMs agree.
   Falls back to plurality if no consensus is reached.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .voter import VotingSession
from ..config import VOTING_METHOD_PLURALITY, VOTING_METHOD_SCORE_WEIGHTED, VOTING_METHOD_CONSENSUS

logger = logging.getLogger(__name__)


@dataclass
class VoteTally:
    """Aggregation result for one voting session."""

    winner: Optional[str]            # UCI move that won, or None if all failed
    method: str                      # Which aggregation method was used
    vote_counts: Dict[str, int]      # {move: raw_vote_count}
    weighted_scores: Dict[str, float]  # {move: aggregated_score}
    fallback_used: bool              # True if we fell back to alpha-beta
    fallback_reason: str             # Why we fell back (empty if not)


def aggregate(
    session: VotingSession,
    candidates: List[str],                     # in alpha-beta rank order (best first)
    ab_scores: Optional[List[int]] = None,     # alpha-beta scores, same order as candidates
    method: str = VOTING_METHOD_PLURALITY,
    consensus_threshold: int = 3,
) -> VoteTally:
    """Select the best move from a VotingSession.

    Args:
        session:              The completed voting session.
        candidates:           Candidate moves in alpha-beta score order (best first).
        ab_scores:            Alpha-beta centipawn scores, aligned with candidates.
        method:               One of VOTING_METHOD_* constants.
        consensus_threshold:  Minimum votes required for consensus method.

    Returns:
        VoteTally with the winner and diagnostics.
    """
    vote_counts = session.vote_tally()
    fallback_used = False
    fallback_reason = ""

    # Normalize alpha-beta scores into [0, 1] fractions for weighting
    score_fractions: Dict[str, float] = {}
    if ab_scores and candidates:
        min_s = min(ab_scores)
        max_s = max(ab_scores)
        span = max_s - min_s if max_s != min_s else 1
        for mv, sc in zip(candidates, ab_scores):
            score_fractions[mv] = (sc - min_s) / span  # 0=worst, 1=best

    if method == VOTING_METHOD_PLURALITY:
        winner, weighted_scores = _plurality(vote_counts, candidates, score_fractions)

    elif method == VOTING_METHOD_SCORE_WEIGHTED:
        winner, weighted_scores = _score_weighted(vote_counts, candidates, score_fractions)

    elif method == VOTING_METHOD_CONSENSUS:
        winner, weighted_scores, fallback_used, fallback_reason = _consensus(
            vote_counts, candidates, score_fractions, consensus_threshold
        )

    else:
        logger.warning("Unknown voting method %r; falling back to plurality", method)
        winner, weighted_scores = _plurality(vote_counts, candidates, score_fractions)

    # If still no winner (all LLMs failed), fall back to alpha-beta best
    if winner is None and candidates:
        winner = candidates[0]
        fallback_used = True
        fallback_reason = fallback_reason or "all LLM votes failed"

    return VoteTally(
        winner=winner,
        method=method,
        vote_counts=vote_counts,
        weighted_scores=weighted_scores,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
    )


# ---------------------------------------------------------------------------
# Internal aggregation helpers
# ---------------------------------------------------------------------------


def _plurality(
    vote_counts: Dict[str, int],
    candidates: List[str],
    score_fractions: Dict[str, float],
) -> Tuple[Optional[str], Dict[str, float]]:
    """Most votes wins; ties broken by alpha-beta rank (lower index = better)."""
    weighted = {mv: float(cnt) for mv, cnt in vote_counts.items()}

    if not weighted:
        return None, weighted

    max_votes = max(weighted.values())
    tied = [mv for mv, cnt in weighted.items() if cnt == max_votes]

    if len(tied) == 1:
        return tied[0], weighted

    # Break ties by candidate rank (candidates is already in best-first order)
    for cand in candidates:
        if cand in tied:
            return cand, weighted

    return tied[0], weighted


def _score_weighted(
    vote_counts: Dict[str, int],
    candidates: List[str],
    score_fractions: Dict[str, float],
) -> Tuple[Optional[str], Dict[str, float]]:
    """Weighted score = vote_count * (1 + alpha_beta_fraction).

    A move that gets 2 LLM votes and has a high engine score beats
    a move with 2 LLM votes and a low engine score.
    """
    weighted: Dict[str, float] = {}
    for mv, cnt in vote_counts.items():
        frac = score_fractions.get(mv, 0.5)  # unknown moves get neutral weight
        weighted[mv] = cnt * (1.0 + frac)

    if not weighted:
        return None, weighted

    winner = max(weighted, key=weighted.__getitem__)
    return winner, weighted


def _consensus(
    vote_counts: Dict[str, int],
    candidates: List[str],
    score_fractions: Dict[str, float],
    threshold: int,
) -> Tuple[Optional[str], Dict[str, float], bool, str]:
    """Require >= threshold votes for consensus; else fall back to plurality."""
    weighted = {mv: float(cnt) for mv, cnt in vote_counts.items()}
    fallback_used = False
    fallback_reason = ""

    consensus_moves = [mv for mv, cnt in vote_counts.items() if cnt >= threshold]

    if consensus_moves:
        # Among consensus moves, pick the one with the best alpha-beta rank
        winner = None
        for cand in candidates:
            if cand in consensus_moves:
                winner = cand
                break
        if winner is None:
            winner = consensus_moves[0]
        return winner, weighted, fallback_used, fallback_reason

    # No consensus: fall back to plurality
    fallback_used = True
    fallback_reason = f"no move reached {threshold}-vote consensus (falling back to plurality)"
    winner, weighted = _plurality(vote_counts, candidates, score_fractions)
    return winner, weighted, fallback_used, fallback_reason
