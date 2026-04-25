"""Tests for the LLM voting layer.

These tests use mock LLM clients so no real API keys are required.
"""

import sys
import os
import unittest
from typing import List
from unittest.mock import patch

# Ensure repo root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from llm_ensemble.llms.base import VoteResult, LLMClient, parse_move, build_prompt
from llm_ensemble.ensemble.voter import vote_parallel, VotingSession


# ---------------------------------------------------------------------------
# Mock LLM clients for testing
# ---------------------------------------------------------------------------

class MockClient(LLMClient):
    def __init__(self, name: str, response_move: str, success: bool = True):
        self.name = name
        self._response = response_move
        self._success = success

    def vote(self, fen, candidates, side_to_move, move_number) -> VoteResult:
        import time
        move = self._response if self._success and self._response in candidates else None
        return VoteResult(
            llm_name=self.name,
            chosen_move=move,
            explanation=self._response,
            raw_response=self._response,
            success=move is not None,
            latency_ms=10,
        )


class TimeoutClient(LLMClient):
    """Simulates a slow LLM that always times out."""
    name = "SlowLLM"

    def vote(self, fen, candidates, side_to_move, move_number) -> VoteResult:
        import time
        time.sleep(200)  # will be killed by timeout
        return VoteResult(self.name, None, "timeout", "", False, 200000)


# ---------------------------------------------------------------------------
# Tests: parse_move
# ---------------------------------------------------------------------------

class TestParseMove(unittest.TestCase):
    CANDIDATES = ["e2e4", "d2d4", "g1f3", "e7e5"]

    def test_exact_uci_in_candidates(self):
        self.assertEqual(parse_move("e2e4", self.CANDIDATES), "e2e4")

    def test_uci_embedded_in_sentence(self):
        self.assertEqual(parse_move("I would play e2e4 here.", self.CANDIDATES), "e2e4")

    def test_case_insensitive(self):
        self.assertEqual(parse_move("E2E4", self.CANDIDATES), "e2e4")

    def test_promotion_move(self):
        cands = ["e7e8q", "e7e8r"]
        self.assertEqual(parse_move("e7e8q", cands), "e7e8q")

    def test_not_in_candidates_returns_none(self):
        self.assertIsNone(parse_move("h2h4", self.CANDIDATES))

    def test_empty_response_returns_none(self):
        self.assertIsNone(parse_move("", self.CANDIDATES))

    def test_garbled_response_returns_none(self):
        self.assertIsNone(parse_move("I cannot determine the best move here.", self.CANDIDATES))


# ---------------------------------------------------------------------------
# Tests: build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt(unittest.TestCase):
    FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    CANDIDATES = ["e2e4", "d2d4", "g1f3"]

    def test_prompt_contains_fen(self):
        p = build_prompt(self.FEN, self.CANDIDATES, "White", 1)
        self.assertIn(self.FEN, p)

    def test_prompt_contains_candidates(self):
        p = build_prompt(self.FEN, self.CANDIDATES, "White", 1)
        for mv in self.CANDIDATES:
            self.assertIn(mv, p)

    def test_prompt_contains_side(self):
        p = build_prompt(self.FEN, self.CANDIDATES, "White", 1)
        self.assertIn("White", p)

    def test_prompt_contains_uci_instruction(self):
        p = build_prompt(self.FEN, self.CANDIDATES, "White", 1)
        self.assertIn("UCI", p)

    def test_prompt_has_ascii_board(self):
        p = build_prompt(self.FEN, self.CANDIDATES, "White", 1)
        self.assertIn("a b c d e f g h", p)


# ---------------------------------------------------------------------------
# Tests: vote_parallel
# ---------------------------------------------------------------------------

class TestVoteParallel(unittest.TestCase):
    CANDIDATES = ["e2e4", "d2d4", "g1f3"]
    FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    def _run(self, clients, timeout=5.0):
        return vote_parallel(
            clients=clients,
            fen=self.FEN,
            candidates=self.CANDIDATES,
            side_to_move="White",
            move_number=1,
            timeout=timeout,
        )

    def test_all_votes_collected(self):
        clients = [MockClient(f"LLM{i}", "e2e4") for i in range(5)]
        session = self._run(clients)
        self.assertEqual(len(session.votes), 5)

    def test_plurality_winner_on_agreement(self):
        clients = [
            MockClient("A", "e2e4"),
            MockClient("B", "e2e4"),
            MockClient("C", "d2d4"),
            MockClient("D", "e2e4"),
            MockClient("E", "g1f3"),
        ]
        session = self._run(clients)
        tally = session.vote_tally()
        self.assertEqual(tally.get("e2e4", 0), 3)
        self.assertEqual(max(tally, key=tally.get), "e2e4")

    def test_failed_client_counted_as_failure(self):
        clients = [
            MockClient("A", "e2e4"),
            MockClient("B", "zz99", success=False),  # will fail parse
        ]
        session = self._run(clients)
        successes = session.successful_votes
        failures = session.failed_votes
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)

    def test_empty_candidates_produces_empty_session(self):
        clients = [MockClient("A", "e2e4")]
        session = vote_parallel(
            clients=clients,
            fen=self.FEN,
            candidates=[],
            side_to_move="White",
            move_number=1,
        )
        self.assertEqual(session.votes, [])

    def test_session_summary_is_string(self):
        clients = [MockClient("A", "e2e4")]
        session = self._run(clients)
        s = session.summary()
        self.assertIsInstance(s, str)
        self.assertIn("e2e4", s)

    def test_timeout_client_recorded_as_failure(self):
        clients = [
            MockClient("Fast", "e2e4"),
            TimeoutClient(),
        ]
        session = self._run(clients, timeout=0.2)
        names = [v.llm_name for v in session.votes]
        self.assertIn("SlowLLM", names)
        slow_vote = next(v for v in session.votes if v.llm_name == "SlowLLM")
        self.assertFalse(slow_vote.success)

    def test_vote_tally_excludes_failures(self):
        clients = [
            MockClient("A", "e2e4"),
            MockClient("B", "INVALID", success=False),
        ]
        session = self._run(clients)
        tally = session.vote_tally()
        self.assertNotIn("INVALID", tally)


if __name__ == "__main__":
    unittest.main()
