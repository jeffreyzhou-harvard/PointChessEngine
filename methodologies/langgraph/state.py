"""Shared state schema for the orchestrator graph.

LangGraph passes a mutable ``OrchestratorState`` between nodes. We keep
the schema flat and JSON-serializable so it can be inspected, dumped
between runs, and replayed under a fake LLM in tests.

Design notes
------------
* ``messages`` is *not* used as a chat transcript -- each specialist
  agent maintains its own ReAct transcript inside ``create_react_agent``.
  The graph-level state holds only durable artifacts: file ledger,
  per-agent structured logs, the architecture decision, and an error
  queue the integrator works through.
* ``agent_logs`` is append-only. Every specialist invocation pushes
  exactly one ``AgentLog`` entry. Re-visits during integration push a
  new entry rather than mutating the old one (so we can audit the run).
* ``files_written`` is a *summary* of the on-disk project, not its
  contents. Agents read full contents back via the ``read_file`` tool.
  Keeping the in-state ledger tiny prevents prompt bloat.
"""

from __future__ import annotations

from typing import Any, TypedDict


class FileEntry(TypedDict):
    """One row of the file ledger."""

    path: str
    summary: str
    role: str
    stage: str


class AgentLog(TypedDict):
    """Structured output every specialist must produce.

    The ReAct agent emits a final assistant message; ``agents.run_role``
    parses it into this schema. Free-form prose lives in ``notes`` and
    is shown to subsequent agents only as a short excerpt.
    """

    role: str
    stage: str
    assumptions: list[str]
    decisions: list[str]
    files_changed: list[str]
    tests_added: list[str]
    risks: list[str]
    notes: str


class OrchestratorState(TypedDict, total=False):
    """Top-level graph state. ``total=False`` so partial updates merge cleanly."""

    project_brief: str
    context_inputs: list[str]
    output_dir: str

    architecture: dict[str, Any]
    files_written: list[FileEntry]
    agent_logs: list[AgentLog]
    errors: list[str]
    stages_complete: list[str]

    current_stage: str
    revision_pass: int
    max_revision_passes: int
    done: bool
