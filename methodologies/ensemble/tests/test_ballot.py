"""Ballot orchestration tests with provider calls patched out."""
from __future__ import annotations

import pytest

from methodologies.ensemble import ballot as ballot_mod
from methodologies.ensemble.ballot import (
    Voter,
    render_design_contract,
    render_full_transcript,
    run_ensemble,
)
from methodologies.ensemble.prompts import TOPICS, parse_vote


# --------------------------------------------------------------------------- #
# parse_vote: pure parsing                                                    #
# --------------------------------------------------------------------------- #

class TestParseVote:
    def test_extracts_simple_vote(self):
        text = "## Reasoning\nclear & defensible.\n\n## Vote\nOpenAI"
        assert parse_vote(text, ["OpenAI", "Grok", "Gemini"]) == "OpenAI"

    def test_strips_quotes_and_bullets(self):
        text = '## Reasoning\nbecause.\n\n## Vote\n- "Grok"'
        assert parse_vote(text, ["OpenAI", "Grok"]) == "Grok"

    def test_substring_match(self):
        text = "## Vote\nI vote for Gemini, definitively."
        assert parse_vote(text, ["OpenAI", "Grok", "Gemini"]) == "Gemini"

    def test_returns_none_if_unmatched(self):
        text = "## Vote\nClaudette"
        assert parse_vote(text, ["OpenAI", "Grok"]) is None

    def test_returns_none_on_empty_text(self):
        assert parse_vote("", ["OpenAI"]) is None


# --------------------------------------------------------------------------- #
# Ballot orchestration with chat() patched out                                #
# --------------------------------------------------------------------------- #

def _proposal_text(label: str) -> str:
    return f"[proposal/{label}] focused recommendation."


def _ballot_text(vote_for: str) -> str:
    return f"## Reasoning\nstrongest case.\n\n## Vote\n{vote_for}\n"


@pytest.fixture
def two_voters_majority(monkeypatch):
    """3 voters, 2 always vote 'OpenAI', 1 votes 'Grok' -> OpenAI wins."""
    def fake_chat(provider, model, system, user, *, max_tokens=2048,
                  temperature=0.4, retries=2):
        if "PROPOSAL phase" in system:
            return _proposal_text(_label_from_system(system))
        if "VOTE phase" in system:
            voter = _label_from_system(system)
            target = "OpenAI" if voter in {"OpenAI", "Grok"} else "Grok"
            return _ballot_text(target)
        return ""

    monkeypatch.setattr(ballot_mod, "chat", fake_chat)
    monkeypatch.setattr(ballot_mod, "have_key", lambda name: True)


def _label_from_system(system_msg: str) -> str:
    """The prompt contains 'speaking as <Label>' or 'voting as <Label>'."""
    for marker in ("speaking as ", "voting as "):
        if marker in system_msg:
            tail = system_msg.split(marker, 1)[1]
            return tail.split(".", 1)[0].strip()
    return "?"


class TestRunEnsemble:
    def test_runs_proposal_and_vote_for_each_topic(self, two_voters_majority):
        voters = [
            Voter("openai",   "gpt-x", "OpenAI"),
            Voter("xai",      "grok-x", "Grok"),
            Voter("gemini",   "gem-x", "Gemini"),
        ]
        result = run_ensemble(voters=voters)
        assert len(result.topics) == len(TOPICS)
        for tr in result.topics:
            assert set(tr.proposals.keys()) == {"OpenAI", "Grok", "Gemini"}
            assert set(tr.ballots.keys())   == {"OpenAI", "Grok", "Gemini"}
            # OpenAI receives 2 votes (OpenAI + Grok), Grok receives 1
            # (from Gemini), and OpenAI wins.
            assert tr.tally == {"OpenAI": 2, "Grok": 1}
            assert tr.winner_label == "OpenAI"
            assert "[proposal/OpenAI]" in tr.winner_proposal
            assert tr.abstentions == []

    def test_abstention_when_vote_unparseable(self, monkeypatch):
        """If a voter returns garbage, they're recorded as abstaining."""
        def fake_chat(provider, model, system, user, **kwargs):
            if "PROPOSAL phase" in system:
                return _proposal_text(_label_from_system(system))
            if "VOTE phase" in system:
                if _label_from_system(system) == "Gemini":
                    return "totally unparseable response"
                return _ballot_text("OpenAI")
            return ""

        monkeypatch.setattr(ballot_mod, "chat", fake_chat)
        monkeypatch.setattr(ballot_mod, "have_key", lambda name: True)
        voters = [
            Voter("openai",   "gpt-x", "OpenAI"),
            Voter("xai",      "grok-x", "Grok"),
            Voter("gemini",   "gem-x", "Gemini"),
        ]
        result = run_ensemble(voters=voters)
        for tr in result.topics:
            assert "Gemini" in tr.abstentions
            assert tr.tally == {"OpenAI": 2}
            assert tr.winner_label == "OpenAI"

    def test_alphabetical_tiebreak(self, monkeypatch):
        """Equal votes for OpenAI and Grok -> Grok wins (alphabetical)."""
        def fake_chat(provider, model, system, user, **kwargs):
            if "PROPOSAL phase" in system:
                return _proposal_text(_label_from_system(system))
            if "VOTE phase" in system:
                voter = _label_from_system(system)
                # OpenAI and Gemini vote OpenAI; Grok and Kimi vote Grok.
                if voter in {"OpenAI", "Gemini"}:
                    return _ballot_text("OpenAI")
                return _ballot_text("Grok")
            return ""

        monkeypatch.setattr(ballot_mod, "chat", fake_chat)
        monkeypatch.setattr(ballot_mod, "have_key", lambda name: True)
        voters = [
            Voter("openai", "x", "OpenAI"),
            Voter("xai",    "x", "Grok"),
            Voter("gemini", "x", "Gemini"),
            Voter("moonshot","x", "Kimi"),
        ]
        result = run_ensemble(voters=voters)
        for tr in result.topics:
            assert tr.tally == {"OpenAI": 2, "Grok": 2}
            # alphabetical sort -> Grok < OpenAI
            assert tr.winner_label == "Grok"

    def test_refuses_with_too_few_voters(self, monkeypatch):
        monkeypatch.setattr(ballot_mod, "have_key", lambda name: name == "openai")
        with pytest.raises(RuntimeError, match="at least 2 voters"):
            run_ensemble(voters=None)


class TestRender:
    def test_design_contract_includes_winners(self, two_voters_majority):
        voters = [
            Voter("openai", "x", "OpenAI"),
            Voter("xai",    "x", "Grok"),
            Voter("gemini", "x", "Gemini"),
        ]
        result = run_ensemble(voters=voters)
        contract = render_design_contract(result)
        for topic in TOPICS:
            assert topic["title"] in contract
        assert "winner: **OpenAI**" in contract
        # Voter line
        assert "OpenAI" in contract and "Grok" in contract

    def test_full_transcript_includes_ballots(self, two_voters_majority):
        voters = [Voter("openai", "x", "OpenAI"), Voter("xai", "x", "Grok")]
        result = run_ensemble(voters=voters)
        transcript = render_full_transcript(result)
        assert "## Ballots" in transcript
        assert "voted for: OpenAI" in transcript
