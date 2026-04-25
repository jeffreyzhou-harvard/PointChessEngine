"""Tests for graph wiring + integrator routing heuristics."""

from __future__ import annotations

from pathlib import Path

import pytest

from methodologies.langgraph.graph import (
    STAGE_ORDER,
    _initial_state,
    _merge_log,
    _pick_rework_target,
    _route_after_integrator,
    build_graph,
)
from methodologies.langgraph.state import AgentLog, OrchestratorState


class TestInitialState:
    def test_defaults(self) -> None:
        s = _initial_state()
        assert s["files_written"] == []
        assert s["agent_logs"] == []
        assert s["errors"] == []
        assert s["revision_pass"] == 0
        assert s["max_revision_passes"] == 1
        assert s["done"] is False

    def test_overrides(self) -> None:
        s = _initial_state(
            project_brief="hello",
            context_inputs=["repo://a"],
            output_dir="/tmp/x",
            max_revision_passes=3,
        )
        assert s["project_brief"] == "hello"
        assert s["context_inputs"] == ["repo://a"]
        assert s["output_dir"] == "/tmp/x"
        assert s["max_revision_passes"] == 3


class TestPickReworkTarget:
    @pytest.mark.parametrize(
        "risk,expected",
        [
            ("FEN parsing breaks on en passant", "rules_engineer"),
            ("search/engine.py blows up at depth 5", "engine_engineer"),
            ("ELO 400 still picks the best move", "strength_tuner"),
            ("uci position fen handling drops moves", "uci_engineer"),
            ("ui/server.py 500s on /api/move", "ui_engineer"),
            ("perft startpos d=3 mismatch", "qa_engineer"),
            ("unrelated documentation typo", None),
        ],
    )
    def test_keyword_routing(self, risk: str, expected: str | None) -> None:
        assert _pick_rework_target([risk]) == expected

    def test_no_risks_returns_none(self) -> None:
        assert _pick_rework_target([]) is None


class TestRouteAfterIntegrator:
    def test_route_to_specialist_on_rework_marker(self) -> None:
        s: OrchestratorState = OrchestratorState(current_stage="REWORK -> rules_engineer")
        assert _route_after_integrator(s) == "rules_engineer"

    def test_route_to_doc_writer_otherwise(self) -> None:
        s: OrchestratorState = OrchestratorState(current_stage="10. Integration pass")
        assert _route_after_integrator(s) == "doc_writer"


class TestMergeLog:
    def test_files_and_log_appended(self) -> None:
        state: OrchestratorState = OrchestratorState(
            agent_logs=[], files_written=[], stages_complete=[],
            architecture={}, errors=[],
        )
        log = AgentLog(role="rules_engineer", stage="3-4",
                       assumptions=[], decisions=[],
                       files_changed=["core/board.py"], tests_added=[],
                       risks=[], notes="")
        update = _merge_log(state, log, [])
        assert len(update["agent_logs"]) == 1
        assert update["stages_complete"] == ["3-4"]
        assert update["current_stage"] == "3-4"

    def test_architect_decisions_promoted(self) -> None:
        state: OrchestratorState = OrchestratorState(
            agent_logs=[], files_written=[], stages_complete=[],
            architecture={}, errors=[],
        )
        log = AgentLog(role="architect", stage="2",
                       assumptions=[], decisions=["use python"],
                       files_changed=[], tests_added=[], risks=[],
                       notes="rationale")
        update = _merge_log(state, log, [])
        assert update["architecture"]["decisions"] == ["use python"]
        assert update["architecture"]["notes"] == "rationale"

    def test_risks_promoted_to_errors_queue(self) -> None:
        state: OrchestratorState = OrchestratorState(
            agent_logs=[], files_written=[], stages_complete=[],
            architecture={}, errors=[],
        )
        log = AgentLog(role="rules_engineer", stage="3-4",
                       assumptions=[], decisions=[], files_changed=[],
                       tests_added=[], risks=["movegen flaky"], notes="")
        update = _merge_log(state, log, [])
        assert update["errors"] == ["[rules_engineer] movegen flaky"]


class TestGraphCompile:
    def test_build_graph_compiles_with_fake_llm(self, fake_llm) -> None:
        graph = build_graph(fake_llm)
        # The compiled graph should expose the public method we use.
        assert hasattr(graph, "invoke")
        assert hasattr(graph, "stream")

    def test_stage_order_covers_master_brief_phases(self) -> None:
        labels = [stage for _, stage in STAGE_ORDER]
        # Spot-check that the linear ordering matches the user's
        # EXECUTION ORDER 1..12 from the master brief.
        assert labels[0].startswith("1.")
        assert any("Architecture" in s for s in labels)
        assert any("UCI" in s for s in labels)
        assert any("Documentation" in s for s in labels)
        assert labels[-1].startswith("12.")


class TestSmokeRunWithFakeLLM:
    """Drive the full graph end-to-end using the fake chat model.

    The fake model emits a response with no tool calls and the empty
    JSON contract, so every node terminates after one turn and writes
    nothing. We're verifying the wiring (all nodes run, in order,
    without raising).
    """

    def test_full_pipeline_runs(self, tmp_path: Path, fake_llm) -> None:
        graph = build_graph(fake_llm)
        initial = _initial_state(
            project_brief="test brief",
            output_dir=tmp_path,
            max_revision_passes=0,  # force linear traversal
        )
        result = graph.invoke(initial)
        # Eleven nodes exist, but a clean run only logs:
        #   context_analyst, architect, rules_engineer, engine_engineer,
        #   strength_tuner, uci_engineer, ui_engineer, qa_engineer,
        #   integrator, doc_writer, final_reviewer
        # = 11 entries.
        roles = [lg["role"] for lg in result["agent_logs"]]
        assert roles == [
            "context_analyst", "architect", "rules_engineer",
            "engine_engineer", "strength_tuner", "uci_engineer",
            "ui_engineer", "qa_engineer", "integrator", "doc_writer",
            "final_reviewer",
        ]
