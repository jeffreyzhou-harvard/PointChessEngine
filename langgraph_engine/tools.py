"""Sandboxed tools the specialist agents call via tool-use.

Every tool is bound to a single ``output_dir`` (the per-run workspace
the agents are allowed to write). The factory closes over that path
and returns LangChain ``BaseTool`` instances; they refuse to operate
outside the sandbox even if the model supplies a ``..`` traversal.

Why a factory instead of module-level @tool functions?
------------------------------------------------------
* The graph can be invoked multiple times in one process (e.g. tests
  with ``tmp_path``). Module-level state would leak between runs.
* Each run gets a fresh ledger ``recorder`` so the graph can later
  reconcile the agent's claimed file changes against what actually
  hit disk.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from langchain_core.tools import BaseTool, StructuredTool


MAX_READ_BYTES = 64 * 1024  # 64 KiB cap so a single tool call can't blow up the prompt
MAX_WRITE_BYTES = 256 * 1024  # 256 KiB per write; agents can chunk
MAX_LIST_ENTRIES = 500
PYTEST_TIMEOUT_SEC = 180


@dataclass
class ToolRecorder:
    """Captures every successful write so the graph can reconcile.

    Each entry is ``(relpath, summary)`` where summary is whatever the
    agent passed via the ``summary`` argument of ``write_file`` (or an
    empty string if omitted). The graph uses this to build the durable
    ``files_written`` ledger in :class:`~langgraph_engine.state.OrchestratorState`.
    """

    writes: list[tuple[str, str]] = field(default_factory=list)
    deletes: list[str] = field(default_factory=list)
    pytest_runs: list[dict] = field(default_factory=list)

    def reset(self) -> None:
        self.writes.clear()
        self.deletes.clear()
        self.pytest_runs.clear()


class SandboxError(RuntimeError):
    """Raised when an agent tries to escape the output_dir sandbox."""


def _resolve_inside(root: Path, candidate: str) -> Path:
    """Resolve ``candidate`` relative to ``root`` and refuse traversal.

    We resolve symlinks and ``..`` segments, then check the resolved
    path is a descendant of ``root.resolve()``. The output dir itself
    is allowed (e.g. for ``list_files(".")``).
    """
    if not isinstance(candidate, str) or not candidate:
        raise SandboxError("path must be a non-empty string")
    # Strip a leading slash so the agent can't accidentally hop out of
    # the sandbox by writing absolute paths.
    cleaned = candidate.lstrip("/")
    abs_path = (root / cleaned).resolve()
    root_resolved = root.resolve()
    try:
        abs_path.relative_to(root_resolved)
    except ValueError as exc:  # pragma: no cover - defensive
        raise SandboxError(f"path escapes sandbox: {candidate!r}") from exc
    return abs_path


def make_tools(
    output_dir: Path | str,
    recorder: ToolRecorder | None = None,
) -> tuple[list[BaseTool], ToolRecorder]:
    """Return ``(tools, recorder)`` bound to ``output_dir``.

    The directory is created if it does not exist. The returned
    recorder is the same instance the tools write into, so the caller
    can read it after the agent returns.
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    rec = recorder if recorder is not None else ToolRecorder()

    def write_file(path: str, content: str, summary: str = "") -> str:
        """Write a file under the project sandbox.

        Args:
            path: Relative path inside the project (e.g. ``"core/board.py"``).
                  Absolute paths and ``..`` traversal are rejected.
            content: Full file contents. Existing files are overwritten.
            summary: One-line description of the file's purpose. Recorded
                     in the orchestrator state for downstream agents.

        Returns a short confirmation including byte count.
        """
        if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
            return (
                f"ERROR: refused write -- file is larger than "
                f"{MAX_WRITE_BYTES} bytes; split it into multiple files"
            )
        target = _resolve_inside(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rel = str(target.relative_to(root.resolve()))
        rec.writes.append((rel, summary or ""))
        return f"wrote {rel} ({len(content)} chars)"

    def read_file(path: str) -> str:
        """Read a file from the project sandbox.

        Returns the file contents (truncated with a marker if larger
        than the read cap). Use this to inspect work done by other
        agents before making changes.
        """
        target = _resolve_inside(root, path)
        if not target.exists():
            return f"ERROR: no such file: {path}"
        if not target.is_file():
            return f"ERROR: not a file: {path}"
        data = target.read_bytes()
        if len(data) > MAX_READ_BYTES:
            head = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
            return head + f"\n\n... [truncated, file is {len(data)} bytes]"
        return data.decode("utf-8", errors="replace")

    def list_files(path: str = ".") -> str:
        """List files in a directory under the sandbox (recursive, capped).

        Returns one path per line, sorted, relative to ``output_dir``.
        Useful at the start of every stage so the agent knows what
        already exists.
        """
        target = _resolve_inside(root, path) if path not in ("", ".") else root.resolve()
        if not target.exists():
            return f"ERROR: no such directory: {path}"
        if target.is_file():
            return str(target.relative_to(root.resolve()))
        out: list[str] = []
        for p in sorted(target.rglob("*")):
            if p.is_dir():
                continue
            # Hide pytest cache and __pycache__ noise from the agent.
            rel = p.relative_to(root.resolve())
            parts = rel.parts
            if any(seg in {"__pycache__", ".pytest_cache"} for seg in parts):
                continue
            out.append(str(rel))
            if len(out) >= MAX_LIST_ENTRIES:
                out.append(f"... [truncated at {MAX_LIST_ENTRIES} entries]")
                break
        if not out:
            return "(empty)"
        return "\n".join(out)

    def delete_file(path: str) -> str:
        """Delete a single file from the sandbox.

        Refuses to delete directories. Recorded in the run ledger.
        """
        target = _resolve_inside(root, path)
        if not target.exists():
            return f"ERROR: no such file: {path}"
        if target.is_dir():
            return f"ERROR: refusing to delete directory: {path}"
        target.unlink()
        rel = str(target.relative_to(root.resolve()))
        rec.deletes.append(rel)
        return f"deleted {rel}"

    def run_pytest(target: str = "") -> str:
        """Run ``pytest`` inside the sandbox.

        Args:
            target: Optional pytest target (e.g. ``"tests/test_board.py"``
                    or ``"-k legal_moves"``). Empty runs the full suite.

        Returns combined stdout/stderr (truncated). The tool times out
        after a few minutes to keep cycles bounded.
        """
        argv = [sys.executable, "-m", "pytest", "-q"]
        if target.strip():
            # Allow the agent to pass either a path or a flag fragment.
            argv.extend(target.split())
        try:
            proc = subprocess.run(
                argv,
                cwd=str(root.resolve()),
                capture_output=True,
                text=True,
                timeout=PYTEST_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            rec.pytest_runs.append(
                {"argv": argv, "returncode": None, "timed_out": True}
            )
            return f"ERROR: pytest timed out after {PYTEST_TIMEOUT_SEC}s"
        except FileNotFoundError as exc:
            return f"ERROR: could not invoke pytest: {exc}"
        out = (proc.stdout + ("\n" + proc.stderr if proc.stderr else "")).strip()
        if len(out) > MAX_READ_BYTES:
            out = out[:MAX_READ_BYTES] + "\n... [truncated]"
        rec.pytest_runs.append(
            {"argv": argv, "returncode": proc.returncode, "timed_out": False}
        )
        return f"[pytest exit={proc.returncode}]\n{out}"

    tools: list[BaseTool] = [
        StructuredTool.from_function(write_file),
        StructuredTool.from_function(read_file),
        StructuredTool.from_function(list_files),
        StructuredTool.from_function(delete_file),
        StructuredTool.from_function(run_pytest),
    ]
    return tools, rec


# ---------------------------------------------------------------------------
# In-process helpers (used by the graph itself, never exposed to the LLM)
# ---------------------------------------------------------------------------


def snapshot_files(output_dir: Path | str, max_entries: int = 200) -> list[str]:
    """Return the current set of project files (relative paths).

    Used by the graph to reconcile the agent's self-reported writes
    against what's really on disk.
    """
    root = Path(output_dir).resolve()
    if not root.exists():
        return []
    out: list[str] = []
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(root)
        if any(seg in {"__pycache__", ".pytest_cache"} for seg in rel.parts):
            continue
        out.append(str(rel))
        if len(out) >= max_entries:
            break
    return out
