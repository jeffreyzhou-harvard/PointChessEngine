"""Sandboxed file/test tools the lead architect calls during the build.

Same shape as ``methodologies.langgraph.tools`` but exposed as the raw
Anthropic tool-use schema (we don't depend on LangChain here). Every
tool is bound to a single ``output_dir``; path traversal outside that
directory is refused.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

MAX_READ_BYTES = 64 * 1024
MAX_WRITE_BYTES = 256 * 1024
MAX_LIST_ENTRIES = 500
PYTEST_TIMEOUT_SEC = 240


class SandboxError(RuntimeError):
    pass


@dataclass
class ToolRecorder:
    writes: list[tuple[str, str]] = field(default_factory=list)
    deletes: list[str] = field(default_factory=list)
    pytest_runs: list[dict] = field(default_factory=list)


def _resolve_inside(root: Path, candidate: str) -> Path:
    if not isinstance(candidate, str) or not candidate:
        raise SandboxError("path must be a non-empty string")
    cleaned = candidate.lstrip("/")
    abs_path = (root / cleaned).resolve()
    root_resolved = root.resolve()
    try:
        abs_path.relative_to(root_resolved)
    except ValueError as exc:
        raise SandboxError(f"path escapes sandbox: {candidate!r}") from exc
    return abs_path


# Anthropic tool schemas (input_schema is JSON Schema).
TOOL_SCHEMAS: list[dict] = [
    {
        "name": "write_file",
        "description": "Write or overwrite a file under the project sandbox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path inside the project (e.g. core/board.py)."},
                "content": {"type": "string"},
                "summary": {"type": "string", "description": "One-line note recorded in the run ledger."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a file from the project sandbox.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_files",
        "description": "Recursively list project files (capped, sorted).",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a single file (refuses directories).",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "run_pytest",
        "description": "Run pytest inside the sandbox. Optional `target` is a path or flag fragment.",
        "input_schema": {
            "type": "object",
            "properties": {"target": {"type": "string"}},
        },
    },
]


def make_dispatch(output_dir: Path | str,
                  recorder: ToolRecorder | None = None
                  ) -> tuple[Callable[[str, dict], str], ToolRecorder]:
    """Return ``(dispatch, recorder)`` where dispatch(name, args) -> str."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    rec = recorder or ToolRecorder()

    def write_file(path: str, content: str, summary: str = "") -> str:
        if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
            return f"ERROR: refused write -- file is larger than {MAX_WRITE_BYTES} bytes"
        target = _resolve_inside(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rel = str(target.relative_to(root.resolve()))
        rec.writes.append((rel, summary or ""))
        return f"wrote {rel} ({len(content)} chars)"

    def read_file(path: str) -> str:
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
        target = _resolve_inside(root, path) if path not in ("", ".") else root.resolve()
        if not target.exists():
            return f"ERROR: no such directory: {path}"
        if target.is_file():
            return str(target.relative_to(root.resolve()))
        out: list[str] = []
        for p in sorted(target.rglob("*")):
            if p.is_dir():
                continue
            rel = p.relative_to(root.resolve())
            if any(seg in {"__pycache__", ".pytest_cache"} for seg in rel.parts):
                continue
            out.append(str(rel))
            if len(out) >= MAX_LIST_ENTRIES:
                out.append(f"... [truncated at {MAX_LIST_ENTRIES} entries]")
                break
        return "\n".join(out) if out else "(empty)"

    def delete_file(path: str) -> str:
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
        argv = [sys.executable, "-m", "pytest", "-q"]
        if target.strip():
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
            rec.pytest_runs.append({"argv": argv, "returncode": None, "timed_out": True})
            return f"ERROR: pytest timed out after {PYTEST_TIMEOUT_SEC}s"
        except FileNotFoundError as exc:
            return f"ERROR: could not invoke pytest: {exc}"
        out = (proc.stdout + ("\n" + proc.stderr if proc.stderr else "")).strip()
        if len(out) > MAX_READ_BYTES:
            out = out[:MAX_READ_BYTES] + "\n... [truncated]"
        rec.pytest_runs.append({"argv": argv, "returncode": proc.returncode, "timed_out": False})
        return f"[pytest exit={proc.returncode}]\n{out}"

    handlers = {
        "write_file":  lambda a: write_file(a.get("path", ""), a.get("content", ""), a.get("summary", "")),
        "read_file":   lambda a: read_file(a.get("path", "")),
        "list_files":  lambda a: list_files(a.get("path", ".")),
        "delete_file": lambda a: delete_file(a.get("path", "")),
        "run_pytest":  lambda a: run_pytest(a.get("target", "")),
    }

    def dispatch(name: str, args: dict[str, Any]) -> str:
        h = handlers.get(name)
        if h is None:
            return f"ERROR: unknown tool {name!r}"
        try:
            return h(args)
        except SandboxError as exc:
            return f"ERROR: {exc}"
        except Exception as exc:  # don't crash the loop on a tool failure
            return f"ERROR: {type(exc).__name__}: {exc}"

    return dispatch, rec
