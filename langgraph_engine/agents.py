"""Specialist-agent runner.

A specialist is a ReAct loop wrapped around Anthropic Claude:

    LangGraph node  ->  agents.run_role(state, role, llm, output_dir)
                       |
                       v
                 create_react_agent(model, tools, prompt)
                       |
                       v
                 Claude tool-use loop (read/write files, run pytest)
                       |
                       v
                 final assistant message
                       |
                       v
                 _parse_agent_json -> AgentLog (appended to state)

We keep this thin: build the role-specific system prompt, hand the
agent a fresh tool sandbox, invoke, parse, return. The graph layer is
responsible for state-shape updates.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from langgraph_engine.prompts import (
    MASTER_BRIEF,
    ROLE_PROMPTS,
    stage_user_prompt,
)
from langgraph_engine.state import AgentLog, FileEntry, OrchestratorState
from langgraph_engine.tools import ToolRecorder, make_tools, snapshot_files


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

# Greedy match for the LAST ```json ... ``` fence in a message. Agents are
# explicitly told the orchestrator parses the LAST block, so anything they
# scratch out earlier as drafts can be ignored.
_JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n(?P<body>\{.*?\})\s*\n```",
    re.DOTALL,
)

_REQUIRED_KEYS = (
    "assumptions",
    "decisions",
    "files_changed",
    "tests_added",
    "risks",
    "notes",
)


def _parse_agent_json(text: str, role: str, stage: str) -> AgentLog:
    """Extract the structured JSON contract from a free-form response.

    Falls back to an empty log with the raw text in ``notes`` if no
    parseable block is found. The orchestrator notices empty logs and
    can re-route the stage.
    """
    matches = list(_JSON_FENCE_RE.finditer(text))
    if not matches:
        return AgentLog(
            role=role,
            stage=stage,
            assumptions=[],
            decisions=[],
            files_changed=[],
            tests_added=[],
            risks=[f"agent emitted no JSON block; raw response retained in notes"],
            notes=text[:2000],
        )
    body = matches[-1].group("body")
    try:
        data: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError as exc:
        return AgentLog(
            role=role,
            stage=stage,
            assumptions=[],
            decisions=[],
            files_changed=[],
            tests_added=[],
            risks=[f"agent JSON failed to parse: {exc}"],
            notes=body[:2000],
        )

    def _as_str_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(v) for v in value]
        if value in (None, ""):
            return []
        return [str(value)]

    return AgentLog(
        role=role,
        stage=stage,
        assumptions=_as_str_list(data.get("assumptions")),
        decisions=_as_str_list(data.get("decisions")),
        files_changed=_as_str_list(data.get("files_changed")),
        tests_added=_as_str_list(data.get("tests_added")),
        risks=_as_str_list(data.get("risks")),
        notes=str(data.get("notes", ""))[:4000],
    )


# ---------------------------------------------------------------------------
# State excerpt fed to each specialist
# ---------------------------------------------------------------------------


def _state_excerpt(state: OrchestratorState, max_logs: int = 6) -> str:
    """Render a compact, human-readable slice of state for the agent.

    We do NOT pass the full state -- it grows large quickly. Each
    specialist sees: the architecture decision, a file ledger, the last
    few agent logs, and the current open-error queue.
    """
    parts: list[str] = []

    arch = state.get("architecture") or {}
    if arch:
        parts.append("ARCHITECTURE DECISION:\n" + json.dumps(arch, indent=2))
    else:
        parts.append("ARCHITECTURE DECISION: (none yet -- Architect has not run)")

    files = state.get("files_written") or []
    if files:
        ledger_lines = [f"  - {f['path']}  ({f['role']}/{f['stage']}): {f['summary']}"
                        for f in files[-50:]]
        parts.append("FILE LEDGER (last 50):\n" + "\n".join(ledger_lines))
    else:
        parts.append("FILE LEDGER: (empty)")

    logs = state.get("agent_logs") or []
    if logs:
        recent = logs[-max_logs:]
        log_lines = []
        for lg in recent:
            log_lines.append(
                f"  * {lg['role']} @ {lg['stage']}: "
                f"{len(lg['files_changed'])} files, "
                f"{len(lg['tests_added'])} tests, "
                f"{len(lg['risks'])} risks"
            )
            for r in lg["risks"][:3]:
                log_lines.append(f"      risk: {r}")
        parts.append(f"RECENT AGENT LOGS (last {len(recent)}):\n" + "\n".join(log_lines))

    errors = state.get("errors") or []
    if errors:
        parts.append("OPEN ERRORS (Integrator queue):\n" + "\n".join(f"  - {e}" for e in errors))

    parts.append(f"REVISION PASS: {state.get('revision_pass', 0)} / "
                 f"{state.get('max_revision_passes', 0)}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Role runner
# ---------------------------------------------------------------------------


def _final_text(messages: list[BaseMessage]) -> str:
    """Pull the text of the final AIMessage, joining content blocks if needed."""
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            content = m.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                pieces: list[str] = []
                for block in content:
                    if isinstance(block, str):
                        pieces.append(block)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        pieces.append(str(block.get("text", "")))
                return "\n".join(pieces)
    return ""


def run_role(
    state: OrchestratorState,
    role: str,
    stage: str,
    llm: BaseChatModel,
    output_dir: str | Path,
    recursion_limit: int = 60,
) -> tuple[AgentLog, list[FileEntry], ToolRecorder]:
    """Run one specialist agent. Returns its log + new file ledger entries.

    The graph node calls this and merges the returned values into state.
    Errors raised by the underlying tool calls are converted into a risk
    entry on the AgentLog so the run never crashes the graph.
    """
    if role not in ROLE_PROMPTS:
        raise KeyError(f"unknown role: {role!r}")

    tools, recorder = make_tools(output_dir)

    system_prompt = MASTER_BRIEF + "\n\n" + ROLE_PROMPTS[role]
    agent = create_react_agent(model=llm, tools=tools, prompt=system_prompt)

    user_msg = HumanMessage(content=stage_user_prompt(stage, _state_excerpt(state)))

    try:
        result = agent.invoke(
            {"messages": [user_msg]},
            config={"recursion_limit": recursion_limit},
        )
    except Exception as exc:  # pragma: no cover - defensive net
        log = AgentLog(
            role=role,
            stage=stage,
            assumptions=[],
            decisions=[],
            files_changed=[],
            tests_added=[],
            risks=[f"agent invocation raised {type(exc).__name__}: {exc}"],
            notes="",
        )
        return log, [], recorder

    final_text = _final_text(result.get("messages", []))
    log = _parse_agent_json(final_text, role=role, stage=stage)

    # Reconcile claimed writes against the recorder. If the agent forgot
    # to list a file in 'files_changed', we still add it to the ledger
    # using the recorder's record (downstream agents need to know it
    # exists). Conversely, claims with no on-disk file get flagged as a
    # risk.
    on_disk = set(snapshot_files(output_dir))
    actual_writes = {rel: summary for rel, summary in recorder.writes}
    new_entries: list[FileEntry] = []
    seen_paths: set[str] = set()

    for rel, summary in recorder.writes:
        if rel in seen_paths:
            continue
        seen_paths.add(rel)
        new_entries.append(FileEntry(
            path=rel, summary=summary or "(no summary)",
            role=role, stage=stage,
        ))

    for claimed in log["files_changed"]:
        norm = claimed.lstrip("./")
        if norm in seen_paths:
            continue
        if norm in on_disk:
            seen_paths.add(norm)
            new_entries.append(FileEntry(
                path=norm,
                summary="(claimed by agent; not written this turn)",
                role=role, stage=stage,
            ))
        else:
            log["risks"].append(
                f"agent claimed file {claimed!r} but it is not on disk"
            )

    return log, new_entries, recorder
