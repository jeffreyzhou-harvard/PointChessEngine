"""Parallel LLM voting.

All five LLMs are queried simultaneously using a thread pool.
Votes are collected up to a timeout; timed-out clients contribute no vote.
"""

from __future__ import annotations

import concurrent.futures
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from ..config import VOTE_TIMEOUT_SECONDS
from ..llms.base import LLMClient, VoteResult

logger = logging.getLogger(__name__)


@dataclass
class VotingSession:
    """The complete record of one round of LLM voting."""

    fen: str
    candidates: List[str]          # UCI moves presented to the LLMs
    side_to_move: str
    move_number: int
    votes: List[VoteResult] = field(default_factory=list)
    timeout_seconds: float = VOTE_TIMEOUT_SECONDS

    @property
    def successful_votes(self) -> List[VoteResult]:
        return [v for v in self.votes if v.success and v.chosen_move is not None]

    @property
    def failed_votes(self) -> List[VoteResult]:
        return [v for v in self.votes if not v.success]

    def vote_tally(self) -> dict:
        """Return {uci_move: vote_count} for successful votes."""
        tally: dict = {}
        for v in self.successful_votes:
            tally[v.chosen_move] = tally.get(v.chosen_move, 0) + 1
        return tally

    def summary(self) -> str:
        """Human-readable summary of the voting round."""
        lines = [f"Voting session — {self.side_to_move} to move (move {self.move_number})"]
        lines.append(f"Candidates: {', '.join(self.candidates)}")
        lines.append(f"Votes ({len(self.successful_votes)}/{len(self.votes)} successful):")
        for v in self.votes:
            status = f"-> {v.chosen_move}" if v.success else "FAILED"
            lines.append(f"  {v.llm_name:12s}  {status:12s}  ({v.latency_ms}ms)")
        tally = self.vote_tally()
        if tally:
            winner = max(tally, key=tally.__getitem__)
            lines.append(f"Tally: {tally}")
            lines.append(f"Plurality winner: {winner} ({tally[winner]} votes)")
        else:
            lines.append("No successful votes.")
        return "\n".join(lines)


def vote_parallel(
    clients: List[LLMClient],
    fen: str,
    candidates: List[str],
    side_to_move: str,
    move_number: int,
    timeout: Optional[float] = None,
) -> VotingSession:
    """Ask all LLM clients to vote simultaneously.

    Uses a thread pool so all five API calls run concurrently.
    Results are collected up to ``timeout`` seconds; any client that
    exceeds the timeout contributes a failure VoteResult.

    Args:
        clients:       List of LLMClient instances (one per LLM).
        fen:           Current position FEN.
        candidates:    UCI move strings to choose from.
        side_to_move:  "White" or "Black".
        move_number:   Full-move number.
        timeout:       Seconds to wait for all clients. Defaults to config value.

    Returns:
        VotingSession with all VoteResults populated.
    """
    if timeout is None:
        timeout = VOTE_TIMEOUT_SECONDS

    session = VotingSession(
        fen=fen,
        candidates=candidates,
        side_to_move=side_to_move,
        move_number=move_number,
        timeout_seconds=timeout,
    )

    if not candidates:
        logger.warning("vote_parallel called with empty candidates list")
        return session

    import time
    start = time.monotonic()

    # Submit all votes concurrently
    futures: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(clients)) as pool:
        for client in clients:
            fut = pool.submit(
                client.vote, fen, candidates, side_to_move, move_number
            )
            futures[fut] = client.name

        done, not_done = concurrent.futures.wait(
            list(futures.keys()),
            timeout=timeout,
        )

    # Collect results from completed futures
    for fut in done:
        try:
            result = fut.result()
        except Exception as exc:  # noqa: BLE001
            name = futures[fut]
            elapsed = int((time.monotonic() - start) * 1000)
            result = VoteResult(
                llm_name=name,
                chosen_move=None,
                explanation=f"Exception: {exc}",
                raw_response=str(exc),
                success=False,
                latency_ms=elapsed,
            )
        session.votes.append(result)

    # Timed-out futures become failure votes
    for fut in not_done:
        name = futures[fut]
        fut.cancel()
        session.votes.append(
            VoteResult(
                llm_name=name,
                chosen_move=None,
                explanation=f"Timed out after {timeout}s",
                raw_response="",
                success=False,
                latency_ms=int(timeout * 1000),
            )
        )

    logger.debug(session.summary())
    return session
