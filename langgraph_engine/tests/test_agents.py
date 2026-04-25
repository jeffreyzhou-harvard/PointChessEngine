"""Tests for the agent JSON parser and state-excerpt builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from langgraph_engine.agents import _parse_agent_json, _state_excerpt, run_role
from langgraph_engine.state import AgentLog, FileEntry, OrchestratorState


_GOOD_JSON = """\
Here's my plan.
```json
{
  "assumptions": ["a1", "a2"],
  "decisions": ["d1"],
  "files_changed": ["core/board.py"],
  "tests_added": ["tests/test_board.py"],
  "risks": [],
  "notes": "first cut, FEN parsing only"
}
```
"""


class TestParseAgentJSON:
    def test_well_formed_block(self) -> None:
        log = _parse_agent_json(_GOOD_JSON, role="rules_engineer", stage="s")
        assert log["role"] == "rules_engineer"
        assert log["assumptions"] == ["a1", "a2"]
        assert log["files_changed"] == ["core/board.py"]
        assert "FEN parsing" in log["notes"]

    def test_missing_block_falls_back_with_risk(self) -> None:
        log = _parse_agent_json("no json here", role="r", stage="s")
        assert log["files_changed"] == []
        assert any("no JSON block" in r for r in log["risks"])
        assert "no json here" in log["notes"]

    def test_malformed_json_recorded_as_risk(self) -> None:
        bad = "```json\n{not json}\n```"
        log = _parse_agent_json(bad, role="r", stage="s")
        assert any("failed to parse" in r for r in log["risks"])

    def test_last_block_wins(self) -> None:
        text = (
            "```json\n{\"assumptions\":[\"draft\"], \"decisions\":[], "
            "\"files_changed\":[], \"tests_added\":[], \"risks\":[], "
            "\"notes\":\"draft\"}\n```\n"
            "After more thought:\n"
            "```json\n{\"assumptions\":[\"final\"], \"decisions\":[], "
            "\"files_changed\":[], \"tests_added\":[], \"risks\":[], "
            "\"notes\":\"final\"}\n```"
        )
        log = _parse_agent_json(text, role="r", stage="s")
        assert log["assumptions"] == ["final"]

    def test_scalar_fields_are_coerced_to_lists(self) -> None:
        text = (
            "```json\n{\"assumptions\":\"single\",\"decisions\":null,"
            "\"files_changed\":[],\"tests_added\":[],\"risks\":[],"
            "\"notes\":\"x\"}\n```"
        )
        log = _parse_agent_json(text, role="r", stage="s")
        assert log["assumptions"] == ["single"]
        assert log["decisions"] == []


class TestStateExcerpt:
    def test_excerpt_handles_empty_state(self) -> None:
        s: OrchestratorState = OrchestratorState(
            architecture={}, files_written=[], agent_logs=[],
            errors=[], stages_complete=[], current_stage="",
            revision_pass=0, max_revision_passes=2,
        )
        text = _state_excerpt(s)
        assert "ARCHITECTURE DECISION: (none yet" in text
        assert "FILE LEDGER: (empty)" in text
        assert "REVISION PASS: 0 / 2" in text

    def test_excerpt_includes_recent_logs_and_errors(self) -> None:
        s: OrchestratorState = OrchestratorState(
            architecture={"decisions": ["use python"]},
            files_written=[FileEntry(path="core/board.py", summary="board",
                                      role="rules_engineer", stage="3-4")],
            agent_logs=[AgentLog(role="rules_engineer", stage="3-4",
                                  assumptions=[], decisions=[],
                                  files_changed=["core/board.py"],
                                  tests_added=[], risks=["movegen flaky"],
                                  notes="")],
            errors=["[rules_engineer] movegen flaky"],
            stages_complete=["3-4"], current_stage="3-4",
            revision_pass=0, max_revision_passes=1,
        )
        text = _state_excerpt(s)
        assert "use python" in text
        assert "core/board.py" in text
        assert "rules_engineer @ 3-4" in text
        assert "movegen flaky" in text


class TestRunRoleFakeLLM:
    """End-to-end run_role with the fake chat model from conftest."""

    def test_run_role_returns_log_and_no_files_when_agent_writes_nothing(
        self, tmp_path: Path, fake_llm,
    ) -> None:
        state = OrchestratorState(
            output_dir=str(tmp_path), files_written=[], agent_logs=[],
            errors=[], stages_complete=[], current_stage="",
            architecture={}, revision_pass=0, max_revision_passes=1,
        )
        log, new_files, recorder = run_role(
            state=state, role="architect", stage="2. Architecture",
            llm=fake_llm, output_dir=tmp_path,
        )
        assert log["role"] == "architect"
        assert log["stage"] == "2. Architecture"
        assert new_files == []
        assert recorder.writes == []

    def test_run_role_rejects_unknown_role(self, tmp_path: Path, fake_llm) -> None:
        state = OrchestratorState(output_dir=str(tmp_path))
        with pytest.raises(KeyError):
            run_role(state=state, role="ghost", stage="s",
                     llm=fake_llm, output_dir=tmp_path)
