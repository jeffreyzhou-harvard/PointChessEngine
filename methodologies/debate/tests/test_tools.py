"""Sandbox tool dispatcher tests (no LLM required)."""
from __future__ import annotations

from pathlib import Path

import pytest

from methodologies.debate.tools import make_dispatch


def test_write_then_read_then_list(tmp_path: Path):
    dispatch, rec = make_dispatch(tmp_path)
    out = dispatch("write_file", {"path": "core/board.py", "content": "X = 1\n", "summary": "stub"})
    assert "wrote" in out
    assert rec.writes == [("core/board.py", "stub")]
    assert dispatch("read_file", {"path": "core/board.py"}).strip() == "X = 1"
    listing = dispatch("list_files", {})
    assert "core/board.py" in listing


def test_path_traversal_is_refused(tmp_path: Path):
    dispatch, _ = make_dispatch(tmp_path)
    out = dispatch("write_file", {"path": "../escape.py", "content": "bad"})
    assert "ERROR" in out and "escape" in out


def test_unknown_tool_returns_error(tmp_path: Path):
    dispatch, _ = make_dispatch(tmp_path)
    assert "unknown tool" in dispatch("not_a_tool", {})


def test_delete_file(tmp_path: Path):
    dispatch, rec = make_dispatch(tmp_path)
    dispatch("write_file", {"path": "x.txt", "content": "hi"})
    out = dispatch("delete_file", {"path": "x.txt"})
    assert "deleted" in out
    assert rec.deletes == ["x.txt"]
    assert "ERROR" in dispatch("read_file", {"path": "x.txt"})
