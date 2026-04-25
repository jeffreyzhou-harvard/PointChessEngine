"""Council orchestration test with provider calls patched out."""
from __future__ import annotations

import os

import pytest

from methodologies.debate import council as council_mod
from methodologies.debate.council import Advisor, render_design_contract, run_council
from methodologies.debate.prompts import TOPICS


def _fake_chat(provider, model, system, user, *, max_tokens=2048, temperature=0.4, retries=2):
    # Identify which phase we're in by looking for distinctive prompt text.
    if "PROPOSAL phase" in system:
        return f"[proposal/{provider}] {user[:40]}..."
    if "CRITIQUE phase" in system:
        return f"[critique/{provider}] rebuttal."
    if "LEAD ARCHITECT" in system:
        return (
            "## Decision\nfake decision for " + provider + "\n\n"
            "## Reasoning\nfake reasoning.\n\n"
            "## Implementation directive\nfake directive.\n"
        )
    return "ok"


@pytest.fixture
def patch_chat(monkeypatch):
    monkeypatch.setattr(council_mod, "chat", _fake_chat)
    monkeypatch.setattr(council_mod, "have_key", lambda name: True)
    yield


def test_council_runs_all_phases_for_each_topic(patch_chat):
    advisors = [
        Advisor("openai", "gpt-4.1", "OpenAI"),
        Advisor("xai", "grok-4", "Grok"),
    ]
    result = run_council(advisors=advisors, lead_provider="anthropic", lead_model="claude-x")
    assert len(result.topics) == len(TOPICS)
    for tr in result.topics:
        assert set(tr.proposals.keys()) == {"OpenAI", "Grok"}
        assert set(tr.critiques.keys()) == {"OpenAI", "Grok"}
        assert "Decision" in tr.verdict
        assert "Implementation directive" in tr.verdict


def test_design_contract_includes_all_topics(patch_chat):
    advisors = [Advisor("openai", "gpt-4.1", "OpenAI")]
    result = run_council(advisors=advisors, lead_provider="anthropic")
    contract = render_design_contract(result)
    for topic in TOPICS:
        assert topic["title"] in contract
    assert "Lead architect: **Claude**" in contract
    assert "OpenAI" in contract  # advisor list line


def test_council_refuses_when_no_advisors(monkeypatch):
    monkeypatch.setattr(council_mod, "have_key", lambda name: False)
    with pytest.raises(RuntimeError, match="no advisor API keys"):
        run_council(advisors=None)
