"""High-level entry point: load env, build LLM + graph, invoke."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel

from langgraph_engine.graph import _initial_state, build_graph
from langgraph_engine.state import OrchestratorState


# Default model. Sonnet is the cost/quality sweet spot for this kind of
# multi-stage tool-use loop. Users can override via CLI.
DEFAULT_MODEL = "claude-sonnet-4-5"
DEFAULT_OUTPUT_DIR = "./langgraph_output"


def default_brief() -> str:
    """Return the user-supplied master charter as a single string.

    Centralised so tests and CLI can share the same canonical wording.
    """
    return (
        "Build a complete chess engine application that "
        "(a) lets a human play against the engine, "
        "(b) supports UCI, "
        "(c) exposes an adjustable ELO strength slider 400-2400, "
        "(d) implements full legal chess rules including draws, "
        "(e) ships with tests, documentation, and a playable interface."
    )


def _load_env_key() -> None:
    """Map the user's ``ANTHROPIC_KEY`` to the SDK's ``ANTHROPIC_API_KEY``.

    The Anthropic Python SDK and ``langchain-anthropic`` both read
    ``ANTHROPIC_API_KEY`` by default. The user's .env uses the
    short name ``ANTHROPIC_KEY``, so we bridge the gap here without
    mutating the .env file.
    """
    try:
        from dotenv import load_dotenv  # local import keeps test deps minimal
    except ImportError:  # pragma: no cover - dotenv is in requirements
        return
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        alt = os.environ.get("ANTHROPIC_KEY")
        if alt:
            os.environ["ANTHROPIC_API_KEY"] = alt


def _make_llm(model_name: str, temperature: float = 0.2,
              max_tokens: int = 8192) -> BaseChatModel:
    """Construct the Claude chat model used for every specialist."""
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=120,
    )


def run(
    brief: str | None = None,
    context_inputs: list[str] | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    model: str = DEFAULT_MODEL,
    max_revision_passes: int = 1,
    llm: BaseChatModel | None = None,
    print_progress: bool = True,
) -> OrchestratorState:
    """Run the orchestrator end-to-end and return the final state.

    Args:
        brief: Project brief shown to every agent. Defaults to
            :func:`default_brief`.
        context_inputs: Optional list of repos / links / notes the
            Context Analyst should review.
        output_dir: Where the agents are allowed to write code.
        model: Anthropic model name (e.g. ``"claude-sonnet-4-5"``).
        max_revision_passes: How many times the Integrator may route
            work back to a specialist.
        llm: Optional pre-built chat model (used by tests with a fake
            model). When provided, ``model`` is ignored.
        print_progress: Whether to print a one-line summary per stage.
    """
    _load_env_key()
    chat = llm if llm is not None else _make_llm(model)
    graph = build_graph(chat)

    initial = _initial_state(
        project_brief=brief or default_brief(),
        context_inputs=context_inputs or [],
        output_dir=output_dir,
        max_revision_passes=max_revision_passes,
    )

    if print_progress:
        # Use streaming so the user sees each stage as it completes.
        last_log_count = 0
        final_state: dict[str, Any] = dict(initial)
        for chunk in graph.stream(initial, stream_mode="values"):
            final_state = chunk
            logs = chunk.get("agent_logs") or []
            while last_log_count < len(logs):
                lg = logs[last_log_count]
                print(
                    f"  [{lg['role']:18s}] stage={lg['stage']:36s} "
                    f"files={len(lg['files_changed'])} "
                    f"tests={len(lg['tests_added'])} "
                    f"risks={len(lg['risks'])}"
                )
                last_log_count += 1
        return OrchestratorState(**final_state)
    else:
        result = graph.invoke(initial)
        return OrchestratorState(**result)


def summarize(state: OrchestratorState) -> str:
    """Pretty-print a compact end-of-run summary."""
    lines: list[str] = []
    lines.append(f"output_dir: {state.get('output_dir')}")
    lines.append(f"stages_complete: {len(state.get('stages_complete') or [])}")
    lines.append(f"files_written:   {len(state.get('files_written') or [])}")
    lines.append(f"agent_logs:      {len(state.get('agent_logs') or [])}")
    lines.append(f"open_errors:     {len(state.get('errors') or [])}")
    lines.append(f"revision_pass:   {state.get('revision_pass', 0)}")
    return "\n".join(lines)
