"""Tests for vote aggregation strategies."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from llm_ensemble.llms.base import VoteResult
from llm_ensemble.ensemble.voter import VotingSession
from llm_ensemble.ensemble.aggregator import aggregate, VoteTally
from llm_ensemble.config import (
    VOTING_METHOD_PLURALITY,
    VOTING_METHOD_SCORE_WEIGHTED,
    VOTING_METHOD_CONSENSUS,
)


FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
CANDIDATES = ["e2e4", "d2d4", "g1f3", "c2c4", "b1c3"]
AB_SCORES  = [   50,     45,     30,     40,     25]


def _make_session(votes_dict: dict) -> VotingSession:
    """Build a VotingSession from {llm_name: chosen_move} dict."""
    votes = []
    for name, move in votes_dict.items():
        success = move in CANDIDATES if move else False
        votes.append(VoteResult(
            llm_name=name,
            chosen_move=move if success else None,
            explanation=move or "failed",
            raw_response=move or "",
            success=success,
            latency_ms=20,
        ))
    return VotingSession(
        fen=FEN,
        candidates=CANDIDATES,
        side_to_move="White",
        move_number=1,
        votes=votes,
    )


class TestPluralityAggregation(unittest.TestCase):
    def _agg(self, votes_dict):
        return aggregate(
            _make_session(votes_dict),
            CANDIDATES,
            AB_SCORES,
            method=VOTING_METHOD_PLURALITY,
        )

    def test_clear_majority_wins(self):
        votes = {"A": "e2e4", "B": "e2e4", "C": "e2e4", "D": "d2d4", "E": "g1f3"}
        t = self._agg(votes)
        self.assertEqual(t.winner, "e2e4")

    def test_two_way_tie_broken_by_ab_rank(self):
        # e2e4 and d2d4 both get 2 votes; e2e4 is first in CANDIDATES (best AB score)
        votes = {"A": "e2e4", "B": "e2e4", "C": "d2d4", "D": "d2d4", "E": None}
        t = self._agg(votes)
        self.assertEqual(t.winner, "e2e4")

    def test_all_failed_falls_back_to_ab_best(self):
        votes = {"A": None, "B": None}
        t = self._agg(votes)
        self.assertTrue(t.fallback_used)
        self.assertEqual(t.winner, CANDIDATES[0])

    def test_single_vote_wins(self):
        votes = {"A": "g1f3"}
        t = self._agg(votes)
        self.assertEqual(t.winner, "g1f3")
        self.assertFalse(t.fallback_used)

    def test_vote_counts_populated(self):
        votes = {"A": "e2e4", "B": "d2d4", "C": "e2e4"}
        t = self._agg(votes)
        self.assertEqual(t.vote_counts["e2e4"], 2)
        self.assertEqual(t.vote_counts["d2d4"], 1)

    def test_winner_is_none_only_if_no_candidates(self):
        session = VotingSession(FEN, [], "White", 1)
        t = aggregate(session, [], None, method=VOTING_METHOD_PLURALITY)
        # No candidates at all → winner should still be None (or fallback gives None)
        self.assertIsNone(t.winner)


class TestScoreWeightedAggregation(unittest.TestCase):
    def _agg(self, votes_dict):
        return aggregate(
            _make_session(votes_dict),
            CANDIDATES,
            AB_SCORES,
            method=VOTING_METHOD_SCORE_WEIGHTED,
        )

    def test_higher_ab_score_breaks_tie(self):
        # Both e2e4 (score=50) and d2d4 (score=45) get 1 vote each.
        # Score-weighted should prefer e2e4 since it has a higher AB score.
        votes = {"A": "e2e4", "B": "d2d4"}
        t = self._agg(votes)
        self.assertEqual(t.winner, "e2e4")

    def test_more_votes_beats_higher_score(self):
        # g1f3 (score=30) gets 3 votes vs e2e4 (score=50) with 1 vote.
        # 3 * (1 + 0.2) = 3.6 vs 1 * (1 + 1.0) = 2.0 → g1f3 wins
        votes = {"A": "g1f3", "B": "g1f3", "C": "g1f3", "D": "e2e4"}
        t = self._agg(votes)
        self.assertEqual(t.winner, "g1f3")


class TestConsensusAggregation(unittest.TestCase):
    def _agg(self, votes_dict, threshold=3):
        return aggregate(
            _make_session(votes_dict),
            CANDIDATES,
            AB_SCORES,
            method=VOTING_METHOD_CONSENSUS,
            consensus_threshold=threshold,
        )

    def test_consensus_reached(self):
        votes = {"A": "e2e4", "B": "e2e4", "C": "e2e4", "D": "d2d4", "E": "g1f3"}
        t = self._agg(votes, threshold=3)
        self.assertEqual(t.winner, "e2e4")
        self.assertFalse(t.fallback_used)

    def test_no_consensus_falls_back_to_plurality(self):
        votes = {"A": "e2e4", "B": "d2d4", "C": "g1f3", "D": "e2e4", "E": "g1f3"}
        # e2e4=2, d2d4=1, g1f3=2 — no 3-vote consensus
        t = self._agg(votes, threshold=3)
        self.assertTrue(t.fallback_used)
        # Plurality picks e2e4 (tied with g1f3, e2e4 is first in CANDIDATES)
        self.assertIn(t.winner, ["e2e4", "g1f3"])

    def test_consensus_threshold_one_always_succeeds(self):
        votes = {"A": "d2d4"}
        t = self._agg(votes, threshold=1)
        self.assertFalse(t.fallback_used)
        self.assertEqual(t.winner, "d2d4")


class TestVoteTallyFields(unittest.TestCase):
    def test_tally_has_all_fields(self):
        votes = {"A": "e2e4", "B": "d2d4"}
        t = aggregate(_make_session(votes), CANDIDATES, AB_SCORES, VOTING_METHOD_PLURALITY)
        self.assertIsInstance(t.winner, str)
        self.assertIsInstance(t.vote_counts, dict)
        self.assertIsInstance(t.weighted_scores, dict)
        self.assertIsInstance(t.fallback_used, bool)
        self.assertIsInstance(t.fallback_reason, str)
        self.assertIsInstance(t.method, str)


if __name__ == "__main__":
    unittest.main()
