"""Tests for the sandboxed file/test toolset."""

from __future__ import annotations

from pathlib import Path

import pytest

from langgraph_engine.tools import (
    MAX_WRITE_BYTES,
    SandboxError,
    ToolRecorder,
    _resolve_inside,
    make_tools,
    snapshot_files,
)


def _tool_by_name(tools, name):
    for t in tools:
        if t.name == name:
            return t
    raise KeyError(name)


class TestSandboxResolution:
    def test_normal_relative_path_allowed(self, tmp_path: Path) -> None:
        target = _resolve_inside(tmp_path, "core/board.py")
        assert target == (tmp_path / "core/board.py").resolve()

    def test_leading_slash_treated_as_relative(self, tmp_path: Path) -> None:
        target = _resolve_inside(tmp_path, "/core/board.py")
        assert target == (tmp_path / "core/board.py").resolve()

    def test_traversal_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(SandboxError):
            _resolve_inside(tmp_path, "../escape.py")

    def test_empty_path_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(SandboxError):
            _resolve_inside(tmp_path, "")


class TestWriteRead:
    def test_write_then_read_roundtrip(self, tmp_path: Path) -> None:
        tools, rec = make_tools(tmp_path)
        write = _tool_by_name(tools, "write_file")
        read = _tool_by_name(tools, "read_file")
        msg = write.invoke({"path": "core/board.py",
                             "content": "print('hi')\n",
                             "summary": "stub"})
        assert "wrote" in msg
        assert (tmp_path / "core/board.py").exists()
        assert read.invoke({"path": "core/board.py"}) == "print('hi')\n"
        assert rec.writes == [("core/board.py", "stub")]

    def test_oversized_write_rejected(self, tmp_path: Path) -> None:
        tools, _ = make_tools(tmp_path)
        write = _tool_by_name(tools, "write_file")
        big = "x" * (MAX_WRITE_BYTES + 1)
        msg = write.invoke({"path": "huge.txt", "content": big})
        assert msg.startswith("ERROR")
        assert not (tmp_path / "huge.txt").exists()

    def test_read_missing_returns_error_string(self, tmp_path: Path) -> None:
        tools, _ = make_tools(tmp_path)
        read = _tool_by_name(tools, "read_file")
        assert read.invoke({"path": "no/such.py"}).startswith("ERROR")

    def test_traversal_via_tool_rejected(self, tmp_path: Path) -> None:
        tools, _ = make_tools(tmp_path)
        write = _tool_by_name(tools, "write_file")
        with pytest.raises(SandboxError):
            write.invoke({"path": "../escape.py", "content": "x"})


class TestListAndDelete:
    def test_list_recursive(self, tmp_path: Path) -> None:
        tools, _ = make_tools(tmp_path)
        write = _tool_by_name(tools, "write_file")
        write.invoke({"path": "a.py", "content": "1"})
        write.invoke({"path": "core/b.py", "content": "2"})
        listed = _tool_by_name(tools, "list_files").invoke({"path": "."})
        assert "a.py" in listed
        assert "core/b.py" in listed

    def test_list_filters_pycache(self, tmp_path: Path) -> None:
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "x.pyc").write_text("noise")
        (tmp_path / "real.py").write_text("ok")
        tools, _ = make_tools(tmp_path)
        listed = _tool_by_name(tools, "list_files").invoke({"path": "."})
        assert "real.py" in listed
        assert "__pycache__" not in listed

    def test_delete_records(self, tmp_path: Path) -> None:
        tools, rec = make_tools(tmp_path)
        write = _tool_by_name(tools, "write_file")
        write.invoke({"path": "a.py", "content": "1"})
        deleted = _tool_by_name(tools, "delete_file").invoke({"path": "a.py"})
        assert "deleted" in deleted
        assert not (tmp_path / "a.py").exists()
        assert rec.deletes == ["a.py"]

    def test_delete_directory_refused(self, tmp_path: Path) -> None:
        (tmp_path / "subdir").mkdir()
        tools, _ = make_tools(tmp_path)
        msg = _tool_by_name(tools, "delete_file").invoke({"path": "subdir"})
        assert msg.startswith("ERROR")


class TestSnapshot:
    def test_snapshot_lists_only_real_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("1")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.py").write_text("2")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "noise.pyc").write_text("x")
        snap = snapshot_files(tmp_path)
        assert "a.py" in snap
        assert "sub/b.py" in snap
        assert all("__pycache__" not in p for p in snap)


class TestRecorderReset:
    def test_recorder_reset(self) -> None:
        r = ToolRecorder()
        r.writes.append(("x.py", ""))
        r.deletes.append("y.py")
        r.pytest_runs.append({"x": 1})
        r.reset()
        assert r.writes == [] and r.deletes == [] and r.pytest_runs == []
