"""Tests for the runner module and the CLI entry point.

These tests never call the real Anthropic API. They cover:
* the .env -> ANTHROPIC_API_KEY remap
* the run() orchestration glue with a fake LLM
* CLI dry-run path
* CLI error path when the API key is missing
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

import langgraph_engine.__main__ as cli
from langgraph_engine.runner import _load_env_key, default_brief, run, summarize


@pytest.fixture
def clean_env(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


class TestLoadEnvKey:
    def test_promotes_short_name_to_canonical(self, clean_env, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_KEY", "sk-ant-test")
        _load_env_key()
        assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-test"

    def test_does_not_overwrite_existing(self, clean_env, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_KEY", "short")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "canonical")
        _load_env_key()
        assert os.environ["ANTHROPIC_API_KEY"] == "canonical"


class TestDefaultBrief:
    def test_brief_is_nonempty_string(self) -> None:
        b = default_brief()
        assert isinstance(b, str) and len(b) > 50
        assert "UCI" in b
        assert "ELO" in b


class TestRunWithFakeLLM:
    def test_run_returns_state_with_logs(self, tmp_path: Path, fake_llm) -> None:
        state = run(
            brief="test",
            output_dir=tmp_path,
            max_revision_passes=0,
            llm=fake_llm,
            print_progress=False,
        )
        assert len(state["agent_logs"]) == 11
        assert state["output_dir"] == str(tmp_path)

    def test_summary_compact(self, tmp_path: Path, fake_llm) -> None:
        state = run(
            brief="test", output_dir=tmp_path, max_revision_passes=0,
            llm=fake_llm, print_progress=False,
        )
        text = summarize(state)
        assert "agent_logs:" in text
        assert "files_written:" in text


class TestCli:
    def test_cli_errors_without_key(self, clean_env, capsys) -> None:
        rc = cli.main(["--dry-run"])
        captured = capsys.readouterr()
        assert rc == 2
        assert "ANTHROPIC" in captured.err

    def test_cli_dry_run_succeeds_with_key(self, clean_env, monkeypatch, capsys) -> None:
        monkeypatch.setenv("ANTHROPIC_KEY", "sk-ant-test")
        rc = cli.main(["--dry-run", "--model", "claude-sonnet-4-5"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "[dry-run]" in out
