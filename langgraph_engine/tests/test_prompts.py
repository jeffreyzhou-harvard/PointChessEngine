"""Sanity tests for the prompt registry and the master brief."""

from __future__ import annotations

from langgraph_engine.graph import STAGE_ORDER
from langgraph_engine.prompts import (
    MASTER_BRIEF,
    ROLE_PROMPTS,
    stage_user_prompt,
)


class TestRoleCoverage:
    def test_every_pipeline_role_has_a_prompt(self) -> None:
        missing = [name for name, _ in STAGE_ORDER if name not in ROLE_PROMPTS]
        assert missing == [], f"missing role prompts for: {missing}"

    def test_every_role_prompt_mentions_json_contract(self) -> None:
        for role, prompt in ROLE_PROMPTS.items():
            assert "JSON" in prompt or "json" in prompt, (
                f"role {role!r} prompt is missing the JSON contract reminder"
            )


class TestMasterBrief:
    def test_brief_lists_the_hard_requirements(self) -> None:
        for token in (
            "UCI", "ELO", "checkmate", "stalemate", "castling",
            "en passant", "promotion", "pinned", "repetition",
            "fifty-move", "insufficient material",
        ):
            assert token in MASTER_BRIEF, f"master brief missing requirement: {token}"

    def test_brief_specifies_json_keys(self) -> None:
        for key in ("assumptions", "decisions", "files_changed",
                    "tests_added", "risks", "notes"):
            assert key in MASTER_BRIEF


class TestStagePrompt:
    def test_stage_prompt_includes_stage_label_and_excerpt(self) -> None:
        msg = stage_user_prompt("3-4. Chess rules", "ARCH: foo\nFILES: bar")
        assert "stage: 3-4. Chess rules" in msg
        assert "ARCH: foo" in msg
        assert "FILES: bar" in msg
