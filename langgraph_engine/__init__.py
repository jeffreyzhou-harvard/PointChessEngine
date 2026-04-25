"""LangGraph-orchestrated multi-agent chess-engine builder.

This package contains *no* chess code. It contains an orchestrator that
spawns specialist Claude agents (Anthropic SDK via ``langchain-anthropic``)
through a LangGraph ``StateGraph``. The agents jointly produce a chess
engine project under a sandboxed output directory.

Public surface:

    from langgraph_engine import build_graph, run, OrchestratorState
"""

from __future__ import annotations

__version__ = "0.1.0"

from langgraph_engine.state import OrchestratorState, AgentLog, FileEntry
from langgraph_engine.graph import build_graph, STAGE_ORDER
from langgraph_engine.runner import run, default_brief

__all__ = [
    "__version__",
    "OrchestratorState",
    "AgentLog",
    "FileEntry",
    "build_graph",
    "STAGE_ORDER",
    "run",
    "default_brief",
]
