"""GEPA-RLM methodology runner.

Audit mode is deterministic and does not call model APIs. It writes the same
classes of artifacts that a future live GEPA-RLM loop will produce: traces,
prompt mutations, candidate result, and selection report.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from methodologies.gepa_rlm.prompts import EVENT_SEQUENCE, PROMPTS


ROOT = Path(__file__).resolve().parents[2]


def load_local_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


@dataclass
class GEPARLMRecord:
    task_id: str
    candidate_id: str
    mode: str
    methodology: str
    base_orchestration: str
    run_id: str
    prompt_path: str
    response_path: str
    trace_path: str
    result_path: str
    report_path: str
    mutation_log_path: str
    selection_report_path: str
    trajectory_log_dir: str | None
    status: str
    live_model_used: bool
    duration_seconds: float
    notes: str


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def resolve_path(path_text: str | None) -> Path:
    path = Path(path_text or ".")
    return path if path.is_absolute() else ROOT / path


def load_config(path: Path) -> dict:
    if yaml is None:
        raise SystemExit("PyYAML is required. Run: pip install -r requirements.txt")
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def find_task_file(task_id: str, task_root: Path | None = None) -> Path | None:
    task_root = task_root or ROOT / "infra" / "tasks"
    exact = f"{task_id}.md"
    for path in task_root.rglob("*.md"):
        if path.name == exact:
            return path
    prefix = task_id.split("_", 1)[0]
    for path in task_root.rglob("*.md"):
        if path.name.startswith(prefix + "_"):
            return path
    return None


def build_prompt(config: dict, task_file: Path | None, task_text: str) -> str:
    prompt_sections = [
        "# GEPA-RLM PointChess Orchestration Prompt",
        f"Candidate: `{config['candidate_id']}`",
        f"Task: `{config['task_id']}`",
        f"Task file: `{display_path(task_file) if task_file else 'task file not found'}`",
        "",
        "## Methodology",
        "",
        "Run RLM-style recursive decomposition, then add GEPA-style reflective prompt evolution.",
        "Do not change the task spec, weaken tests, bypass interface contracts, or hardcode benchmark answers.",
        "",
        "## Seed Agent Prompts",
    ]
    for role, prompt in PROMPTS.items():
        prompt_sections.extend([f"### {role}", prompt.strip(), ""])
    prompt_sections.extend(
        [
            "## Task Spec",
            task_text,
            "",
            "## Required Output",
            "- decompose the task into focused subcalls",
            "- identify public interfaces and interface-change risk",
            "- propose tests before implementation",
            "- identify chess and software edge cases",
            "- propose implementation and review plan",
            "- identify likely failure modes and prompt mutations",
            "- produce candidate-report content with cost/time limitations",
        ]
    )
    return "\n".join(prompt_sections)


def audit_response(config: dict, task_file: Path | None) -> str:
    return "\n".join(
        [
            "# GEPA-RLM Audit Response",
            "",
            f"Candidate: `{config['candidate_id']}`",
            f"Task: `{config['task_id']}`",
            f"Task file: `{display_path(task_file) if task_file else 'task file not found'}`",
            "",
            "This deterministic audit run did not call model APIs and did not edit engine code.",
            "",
            "## Recursive Work Units",
            "",
            "1. Root decomposition: split milestone into interface, test, edge-case, planning, and review work.",
            "2. Interface inspection: preserve public engine, board, move, evaluator, search, and UCI contracts.",
            "3. Test design: map acceptance criteria to unit, contract, and Champion tier checks.",
            "4. Edge-case analysis: identify chess-specific failure modes before implementation.",
            "5. Implementation planning: produce a narrow patch plan for a future builder.",
            "6. Reflection: map test/review failures into prompt mutations without weakening the rubric.",
            "",
            "## Live Mode",
            "",
            "Run with `--mode live` plus provider credentials to execute a live RLM-backed GEPA-RLM planning call.",
        ]
    )


def live_response(prompt: str, backend: str, model_name: str, verbose: bool, trajectory_log_dir: Path) -> str:
    try:
        from rlm import RLM
    except ImportError as exc:  # pragma: no cover - optional external package
        raise SystemExit(
            "Live GEPA-RLM mode requires the optional package from https://github.com/alexzhang13/rlm. "
            "Install with `pip install rlms`."
        ) from exc

    logger = None
    try:  # pragma: no cover - depends on optional external package internals
        from rlm.logger import RLMLogger

        trajectory_log_dir.mkdir(parents=True, exist_ok=True)
        logger = RLMLogger(log_dir=str(trajectory_log_dir))
    except Exception:
        logger = None

    kwargs = {
        "backend": backend,
        "backend_kwargs": {"model_name": model_name},
        "verbose": verbose,
    }
    if logger is not None:
        kwargs["logger"] = logger
    rlm = RLM(**kwargs)
    completion = rlm.completion(prompt)
    return getattr(completion, "response", str(completion))


def build_trace_event(config: dict, run_id: str, round_index: int, event_type: str, role: str, started: float) -> dict:
    task_id = config["task_id"]
    model_assignments = config.get("model_assignments") or {}
    return {
        "run_id": run_id,
        "task_id": task_id,
        "candidate_id": config["candidate_id"],
        "round": round_index,
        "event_type": event_type,
        "agent_role": role,
        "model": model_assignments.get(role, ""),
        "prompt_path": f"methodologies/gepa_rlm/prompts.py::{role}",
        "input_summary": f"Dry-run GEPA-RLM input for {task_id}",
        "output_summary": summarize_event(event_type, role),
        "file_refs": [display_path(find_task_file(task_id)) if find_task_file(task_id) else ""],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latency_ms": int((time.monotonic() - started) * 1000),
        "token_estimate": 0,
        "cost_estimate_usd": 0.0,
        "notes": "Audit-mode scaffold event; no model API was called.",
    }


def summarize_event(event_type: str, role: str) -> str:
    summaries = {
        "root_decomposition": "Root decomposes task into interface, test, edge-case, planning, and review subcalls.",
        "subcall_interface_inspection": "Interface inspector identifies public contracts and forbidden interface drift.",
        "subcall_test_design": "Test designer maps task acceptance criteria to tests before implementation.",
        "subcall_edge_case_analysis": "Edge-case analyst lists chess and integration failure modes.",
        "subcall_implementation_planning": "Implementation planner creates a narrow patch plan without editing engine code.",
        "subcall_review": "Reviewer checks task fit, interface safety, testing evidence, and benchmark-cheating risk.",
        "synthesized_plan": "Root synthesizes candidate plan and GEPA-RLM report scaffold.",
        "reflection": "Reflector diagnoses prompt gaps from trace and placeholder feedback.",
        "prompt_mutation": "Reflector writes task-grounded prompt mutations for the next round.",
        "candidate_selection": "Selector ranks seed and evolved candidates without promotion.",
    }
    return summaries.get(event_type, f"{role} completed {event_type}.")


def write_trace(path: Path, config: dict, run_id: str, round_index: int, started: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for event_type, role in EVENT_SEQUENCE:
            f.write(json.dumps(build_trace_event(config, run_id, round_index, event_type, role, started), sort_keys=True) + "\n")


def write_mutations(path: Path, config: dict, round_index: int) -> list[dict]:
    path.parent.mkdir(parents=True, exist_ok=True)
    mutations = []
    for role in config.get("allowed_mutations") or []:
        prompt = PROMPTS.get(role, "")
        mutations.append(
            {
                "role": role,
                "round": round_index,
                "evidence": "Dry-run trace showed the need to connect role output to task requirements, interface contracts, and tests.",
                "mutation": "Require every recommendation to cite task objective, interface risk, and test/review evidence.",
                "seed_prompt_preview": prompt[:160],
            }
        )
    path.write_text(json.dumps({"mutations": mutations}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return mutations


def write_result(path: Path, config: dict, run_id: str, round_index: int, mutations: list[dict], started: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "candidate_id": config["candidate_id"],
        "task_id": config["task_id"],
        "methodology": "gepa_rlm",
        "base_orchestration": config.get("base_orchestration", "rlm_lite"),
        "round": round_index,
        "tests_passed": 0,
        "tests_total": 0,
        "contract_tests_passed": False,
        "review_score": 0,
        "benchmark_score": 0,
        "champion_score": 0,
        "cost_estimate_usd": 0.0,
        "latency_minutes": round((time.monotonic() - started) / 60, 3),
        "prompt_mutations": mutations,
        "bugs_caught_before_implementation": [],
        "promotion_recommendation": "rerun",
        "run_id": run_id,
        "notes": "Audit-mode placeholder result; not promotable.",
    }
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_report(path: Path, config: dict, run_id: str, trace_path: Path, mutation_path: Path, result_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# GEPA-RLM Report: {config['task_id']}",
        "",
        f"- Candidate: `{config['candidate_id']}`",
        f"- Run ID: `{run_id}`",
        "- Mode: `audit`",
        "- Live model used: `false`",
        "",
        "## Methodology",
        "",
        "GEPA-RLM starts from RLM-lite recursive decomposition, then adds trace-driven reflection and prompt mutation before selecting an evolved candidate.",
        "",
        "## Artifacts",
        "",
        f"- Trace: `{display_path(trace_path)}`",
        f"- Mutation log: `{display_path(mutation_path)}`",
        f"- Result: `{display_path(result_path)}`",
        "",
        "## Recommendation",
        "",
        "Rerun with live implementation before Champion promotion. This audit run is scaffolding only.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_selection(path: Path, config: dict, result_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# GEPA-RLM Selection: {config['task_id']}",
        "",
        "| Candidate | Round | Score | Recommendation | Source |",
        "|---|---:|---:|---|---|",
        f"| `{config['candidate_id']}` | 0 | 0 | rerun | `{display_path(result_path)}` |",
        "",
        "No promotion was performed.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def default_config(task_id: str, candidate_id: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "task_id": task_id,
        "methodology": "gepa_rlm",
        "base_orchestration": "rlm_lite",
        "allowed_mutations": ["root", "interface_inspector", "test_designer", "edge_case_analyst", "implementation_planner", "reviewer"],
        "model_assignments": {
            "root": "claude",
            "interface_inspector": "gpt",
            "test_designer": "claude",
            "edge_case_analyst": "gemini",
            "implementation_planner": "gpt",
            "reviewer": "claude",
            "reflector": "gemini",
            "selector": "claude",
        },
    }


def main() -> int:
    load_local_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="methodologies/gepa_rlm/gepa_rlm_config.yaml.example")
    parser.add_argument("--task", default="C3_STATIC_EVALUATION")
    parser.add_argument("--candidate-id", default="C3_gepa_rlm_claude_gpt_gemini")
    parser.add_argument("--mode", default="audit", choices=["audit", "live"])
    parser.add_argument("--task-root", default="infra/tasks")
    parser.add_argument("--output-root", default="reports/gepa_rlm")
    parser.add_argument("--round", type=int, default=0)
    parser.add_argument("--backend", default=os.environ.get("GEPA_RLM_BACKEND", os.environ.get("RLM_BACKEND", "openai")))
    parser.add_argument("--model", default=os.environ.get("GEPA_RLM_MODEL", os.environ.get("RLM_MODEL", "gpt-5-nano")))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    started = time.monotonic()
    config = default_config(args.task, args.candidate_id)
    config.update(load_config(resolve_path(args.config)))
    config["task_id"] = args.task or config["task_id"]
    config["candidate_id"] = args.candidate_id or config["candidate_id"]

    task_root = resolve_path(args.task_root)
    task_file = find_task_file(config["task_id"], task_root)
    task_text = task_file.read_text(encoding="utf-8") if task_file else f"No task file found for {config['task_id']}."
    run_id = f"{config['task_id']}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    output_dir = resolve_path(args.output_root) / config["task_id"] / config["candidate_id"]
    prompt_path = output_dir / "prompt.md"
    response_path = output_dir / "response.md"
    trace_path = output_dir / "trace.jsonl"
    mutation_path = output_dir / "prompt_mutations.json"
    result_path = output_dir / "result.json"
    report_path = output_dir / "report.md"
    selection_path = output_dir / "selection.md"
    trajectory_log_dir = output_dir / "trajectory"

    output_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(config, task_file, task_text)
    prompt_path.write_text(prompt, encoding="utf-8")
    if args.mode == "live":
        response = live_response(prompt, args.backend, args.model, args.verbose, trajectory_log_dir)
        status = "live_completed"
        live_model_used = True
        notes = "Live GEPA-RLM completion ran. Review response, traces, and prompt mutations before applying or promoting."
    else:
        response = audit_response(config, task_file)
        status = "audit_completed"
        live_model_used = False
        notes = "Audit mode wrote GEPA-RLM methodology artifacts without model calls or engine edits."
    response_path.write_text(response, encoding="utf-8")

    write_trace(trace_path, config, run_id, args.round, started)
    mutations = write_mutations(mutation_path, config, args.round)
    write_result(result_path, config, run_id, args.round, mutations, started)
    write_report(report_path, config, run_id, trace_path, mutation_path, result_path)
    write_selection(selection_path, config, result_path)

    record = GEPARLMRecord(
        task_id=config["task_id"],
        candidate_id=config["candidate_id"],
        mode=args.mode,
        methodology="gepa_rlm",
        base_orchestration=config.get("base_orchestration", "rlm_lite"),
        run_id=run_id,
        prompt_path=display_path(prompt_path),
        response_path=display_path(response_path),
        trace_path=display_path(trace_path),
        result_path=display_path(result_path),
        report_path=display_path(report_path),
        mutation_log_path=display_path(mutation_path),
        selection_report_path=display_path(selection_path),
        trajectory_log_dir=display_path(trajectory_log_dir) if args.mode == "live" and trajectory_log_dir.exists() else None,
        status=status,
        live_model_used=live_model_used,
        duration_seconds=round(time.monotonic() - started, 3),
        notes=notes,
    )
    (output_dir / "orchestration.json").write_text(json.dumps(asdict(record), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(asdict(record), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
