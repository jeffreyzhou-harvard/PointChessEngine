"""LangGraph wiring for the multi-agent chess-engine builder.

Pipeline
--------

    START
      |
      v
    context_analyst
      |
      v
    architect
      |
      v
    rules_engineer ---+
      |               |
      v               |  Each of these "rework targets" has a
    engine_engineer   |  conditional outgoing edge: the FIRST visit
      |               |  goes forward in the pipeline, a SECOND
      v               |  visit (after integrator routed back) jumps
    strength_tuner    |  straight to the integrator instead of
      |               |  re-running the rest of the pipeline.
      v               |
    uci_engineer      |
      |               |
      v               |
    ui_engineer       |
      |               |
      v               |
    qa_engineer ------+
      |
      v
    integrator
      |
      v   conditional: rework specialist (if errors + budget remain)
      |   else doc_writer
      v
    doc_writer
      |
      v
    final_reviewer
      |
      v
    END

Why this shape?
---------------
* Mirrors the master brief's EXECUTION ORDER 1..12, so prompt readers
  can map nodes 1:1 to phases.
* The integrator loop is bounded -- agent calls are expensive and an
  unbounded loop with a real LLM is dangerous.
* Every node is shaped the same way (``run_role`` wrapper); adding a
  new specialist is just adding a prompt + a node.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from langgraph_engine.agents import run_role
from langgraph_engine.state import AgentLog, FileEntry, OrchestratorState


# Order matches the master-brief EXECUTION ORDER. The first element of
# each tuple is the node name (matches keys in ROLE_PROMPTS); the
# second is the human-readable stage label embedded in agent prompts.
STAGE_ORDER: list[tuple[str, str]] = [
    ("context_analyst", "1. Context assessment"),
    ("architect",       "2. Architecture and stack decision"),
    ("rules_engineer",  "3-4. Chess rules and move generation"),
    ("engine_engineer", "5. Evaluation and search"),
    ("strength_tuner",  "6. ELO scaling"),
    ("uci_engineer",    "7. UCI support"),
    ("ui_engineer",     "8. UI"),
    ("qa_engineer",     "9. Tests"),
    ("integrator",      "10. Integration pass"),
    ("doc_writer",      "11. Documentation"),
    ("final_reviewer",  "12. Final review"),
]

_NODES_BY_NAME: dict[str, str] = {name: stage for name, stage in STAGE_ORDER}

# Linear successor map for the "main pipeline" nodes (everything from
# the architect to the integrator). Nodes listed as keys are eligible
# rework targets when the integrator routes work back; nodes not in
# this dict have plain unconditional edges.
_LINEAR_SUCCESSOR: dict[str, str] = {
    "rules_engineer":  "engine_engineer",
    "engine_engineer": "strength_tuner",
    "strength_tuner":  "uci_engineer",
    "uci_engineer":    "ui_engineer",
    "ui_engineer":     "qa_engineer",
    "qa_engineer":     "integrator",
}

# Roles the integrator can hand work back to.
_REWORK_TARGETS: tuple[str, ...] = tuple(_LINEAR_SUCCESSOR.keys())


# ---------------------------------------------------------------------------
# State merging helpers
# ---------------------------------------------------------------------------


def _initial_state(
    project_brief: str = "",
    context_inputs: list[str] | None = None,
    output_dir: str | Path = "./langgraph_output",
    max_revision_passes: int = 1,
) -> OrchestratorState:
    """Build the starting state for a graph run."""
    return OrchestratorState(
        project_brief=project_brief,
        context_inputs=list(context_inputs or []),
        output_dir=str(output_dir),
        architecture={},
        files_written=[],
        agent_logs=[],
        errors=[],
        stages_complete=[],
        current_stage="",
        revision_pass=0,
        max_revision_passes=int(max_revision_passes),
        done=False,
    )


def _merge_log(state: OrchestratorState, log: AgentLog,
               new_files: list[FileEntry]) -> dict[str, Any]:
    """Compute the partial-state update for one agent turn.

    LangGraph node functions return a *partial* mapping that gets
    merged into state. We never mutate the incoming state dict.
    """
    update: dict[str, Any] = {
        "agent_logs": list(state.get("agent_logs") or []) + [log],
        "files_written": list(state.get("files_written") or []) + new_files,
        "stages_complete": list(state.get("stages_complete") or []) + [log["stage"]],
        "current_stage": log["stage"],
    }
    # Architect's decisions are promoted into the structured
    # `architecture` field so downstream agents see them prominently.
    if log["role"] == "architect" and log["decisions"]:
        arch = dict(state.get("architecture") or {})
        prior = list(arch.get("decisions", []))
        arch["decisions"] = prior + list(log["decisions"])
        if log["notes"]:
            arch["notes"] = log["notes"]
        update["architecture"] = arch
    if log["risks"]:
        update["errors"] = list(state.get("errors") or []) + [
            f"[{log['role']}] {r}" for r in log["risks"]
        ]
    return update


# ---------------------------------------------------------------------------
# Node factories
# ---------------------------------------------------------------------------


def _make_specialist_node(role: str, stage: str, llm: BaseChatModel) -> Callable[
    [OrchestratorState], dict[str, Any]
]:
    """Build the LangGraph callable for a specialist node."""

    def node(state: OrchestratorState) -> dict[str, Any]:
        log, new_files, _ = run_role(
            state=state, role=role, stage=stage, llm=llm,
            output_dir=state["output_dir"],
        )
        return _merge_log(state, log, new_files)

    node.__name__ = f"node_{role}"
    return node


def _make_integrator_node(llm: BaseChatModel) -> Callable[
    [OrchestratorState], dict[str, Any]
]:
    """Integrator runs its role then decides whether to loop back.

    Routing decision is encoded into ``current_stage`` -- the
    conditional edge below reads it.
    """
    role = "integrator"
    stage = _NODES_BY_NAME[role]

    def node(state: OrchestratorState) -> dict[str, Any]:
        log, new_files, _ = run_role(
            state=state, role=role, stage=stage, llm=llm,
            output_dir=state["output_dir"],
        )
        update = _merge_log(state, log, new_files)

        revision_pass = int(state.get("revision_pass", 0))
        max_passes = int(state.get("max_revision_passes", 0))
        # Inspect the integrator's own risks AND any pre-existing errors.
        candidate_risks = list(log["risks"]) + list(state.get("errors") or [])
        next_target = _pick_rework_target(candidate_risks)

        if next_target and revision_pass < max_passes:
            update["current_stage"] = f"REWORK -> {next_target}"
            update["revision_pass"] = revision_pass + 1
        else:
            # Either everything is clean or we ran out of revision
            # budget; clear the queue and advance.
            update["errors"] = []
            update["current_stage"] = stage
        return update

    node.__name__ = "node_integrator"
    return node


def _pick_rework_target(risks: list[str]) -> str | None:
    """Map a risk string to a rework specialist, if any.

    Heuristic: if the risk text mentions a known module
    (``core/``, ``search/``, ``uci/``, ``ui/``, etc.) route to its
    owner. Otherwise return ``None`` so the integrator advances.
    """
    # Two priority tiers: module-path slash-keys are more specific and
    # are checked first; bare-noun keywords are a fuzzy fallback.
    primary = [
        ("core/", "rules_engineer"),
        ("search/", "engine_engineer"),
        ("uci/", "uci_engineer"),
        ("ui/", "ui_engineer"),
    ]
    fallback = [
        ("uci", "uci_engineer"),
        ("perft", "qa_engineer"),
        ("movegen", "rules_engineer"),
        ("fen", "rules_engineer"),
        ("rules", "rules_engineer"),
        ("evaluation", "engine_engineer"),
        ("minimax", "engine_engineer"),
        ("alpha-beta", "engine_engineer"),
        ("elo", "strength_tuner"),
        ("blunder", "strength_tuner"),
        ("browser", "ui_engineer"),
        ("test", "qa_engineer"),
    ]
    for tier in (primary, fallback):
        for risk in risks:
            lower = risk.lower()
            for kw, role in tier:
                if kw in lower:
                    return role
    return None


def _route_after_integrator(state: OrchestratorState) -> str:
    """Conditional edge: send back to a specialist or advance to docs."""
    cs = state.get("current_stage", "")
    if cs.startswith("REWORK -> "):
        return cs.removeprefix("REWORK -> ")
    return "doc_writer"


def _make_pipeline_router(role: str, forward: str) -> Callable[
    [OrchestratorState], str
]:
    """Conditional outgoing edge for a pipeline node.

    First visit: go forward. Subsequent visits (rework): jump straight
    to the integrator without redoing the rest of the pipeline.
    """

    def router(state: OrchestratorState) -> str:
        logs = state.get("agent_logs") or []
        visits = sum(1 for lg in logs if lg["role"] == role)
        return "integrator" if visits > 1 else forward

    router.__name__ = f"route_{role}"
    return router


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------


def build_graph(llm: BaseChatModel) -> Any:
    """Compile the orchestrator StateGraph for a given chat model.

    The returned object is a compiled LangGraph runnable. Call
    ``.invoke(initial_state)`` to execute end-to-end, or use
    ``langgraph_engine.runner.run`` for the typical CLI flow with
    config defaults and progress logging.
    """
    g: StateGraph = StateGraph(OrchestratorState)

    # Add all nodes.
    for role, stage in STAGE_ORDER:
        if role == "integrator":
            g.add_node(role, _make_integrator_node(llm))
        else:
            g.add_node(role, _make_specialist_node(role, stage, llm))

    # Pre-pipeline (no rework eligibility, plain edges).
    g.add_edge(START, "context_analyst")
    g.add_edge("context_analyst", "architect")
    g.add_edge("architect", "rules_engineer")

    # Pipeline body: each node has a conditional outgoing edge so we can
    # short-circuit straight to the integrator on a rework visit.
    for role, fwd in _LINEAR_SUCCESSOR.items():
        g.add_conditional_edges(
            role,
            _make_pipeline_router(role, fwd),
            {fwd: fwd, "integrator": "integrator"},
        )

    # Integrator: either route back to a specialist or advance to docs.
    g.add_conditional_edges(
        "integrator",
        _route_after_integrator,
        {"doc_writer": "doc_writer", **{r: r for r in _REWORK_TARGETS}},
    )

    g.add_edge("doc_writer", "final_reviewer")
    g.add_edge("final_reviewer", END)

    return g.compile()
